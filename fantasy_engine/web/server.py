"""Flask backend for the Fantasy Engine web UI.

Two surfaces live here:

    1. The legacy procedural-world viewer (`/api/world/...`) — kept for
       backwards compatibility. Static, just a colored map.

    2. The live simulation surface (`/api/sim/...`) — a single in-process
       `SimulationSession` that owns a real `World` + `SimulationController`,
       ticks in the background, and exposes JSON state plus a political map
       overlay (provinces colored by their owning civilization).

The session is global (one process, one running world). `/api/sim/new`
tears down the previous session and starts a new one for the given seed.
"""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass

import numpy as np
from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from PIL import Image

from fantasy_engine.visual.cartographer import CartographyOptions, RenderInputs, render_world
from fantasy_engine.web.simulation_session import SimulationSession
from fantasy_engine.world.geography import GeographyConfig, GeographyResult, generate_geography
from fantasy_engine.world.provinces import ProvinceMap, build_province_map


# ---------------------------------------------------------------------------
# Legacy procedural-world cache (unchanged behaviour)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorldKey:
    seed: int
    width: int
    height: int
    land_fraction: float


@dataclass(slots=True)
class CachedWorld:
    key: WorldKey
    geography: GeographyResult
    provinces: ProvinceMap
    image_bytes: bytes
    pickmap_bytes: bytes


class WorldCache:
    def __init__(self, max_entries: int = 8) -> None:
        self._lock = threading.Lock()
        self._entries: dict[WorldKey, CachedWorld] = {}
        self._max_entries = max_entries

    def get_or_build(self, key: WorldKey) -> CachedWorld:
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                return cached
        built = _build_world(key)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                return cached
            if len(self._entries) >= self._max_entries:
                oldest_key = next(iter(self._entries))
                del self._entries[oldest_key]
            self._entries[key] = built
            return built


def _build_world(key: WorldKey) -> CachedWorld:
    config = GeographyConfig(width=key.width, height=key.height, seed=key.seed, land_fraction=key.land_fraction)
    geography = generate_geography(config)
    provinces = build_province_map(geography)
    rgb = render_world(RenderInputs(geography=geography, provinces=provinces, options=CartographyOptions()))
    return CachedWorld(
        key=key,
        geography=geography,
        provinces=provinces,
        image_bytes=_encode_png(rgb),
        pickmap_bytes=_encode_png(_build_pickmap_rgb(geography, provinces)),
    )


def _encode_png(rgb: np.ndarray) -> bytes:
    image = Image.fromarray(rgb, mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def _build_pickmap_rgb(geography: GeographyResult, provinces: ProvinceMap) -> np.ndarray:
    height, width = geography.elevation.shape
    pickmap = np.zeros((height, width, 3), dtype=np.uint8)
    province_ids = provinces.province_id_grid
    has_province = province_ids >= 0
    pickmap[..., 0] = np.where(has_province, province_ids & 0xFF, 0).astype(np.uint8)
    pickmap[..., 1] = np.where(has_province, (province_ids >> 8) & 0xFF, 0).astype(np.uint8)
    pickmap[..., 2] = np.where(geography.land_mask, 0, 255).astype(np.uint8)
    return pickmap


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(*, default_size: tuple[int, int] = (384, 240), default_land_fraction: float = 0.42) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    cache = WorldCache(max_entries=8)

    # Single global simulation session. Lazily created on first /api/sim/new
    # (or first state poll, falling back to a default seed).
    sim_lock = threading.Lock()
    sim_box: dict[str, SimulationSession | None] = {"session": None}

    def get_or_create_sim(seed: int | None = None) -> SimulationSession:
        with sim_lock:
            session = sim_box["session"]
            if session is not None and (seed is None or session.seed == seed):
                return session
            if session is not None:
                session.shutdown()
            new_seed = seed if seed is not None else 909
            session = SimulationSession(
                seed=new_seed,
                width=default_size[0],
                height=default_size[1],
                land_fraction=default_land_fraction,
                num_civilizations=4,
            )
            sim_box["session"] = session
            return session

    # ------------------ shell ------------------

    @app.route("/")
    def index() -> str:
        return render_template(
            "index.html",
            default_seed=909,
            default_width=default_size[0],
            default_height=default_size[1],
        )

    # ------------------ legacy procedural-world API ------------------

    @app.route("/api/world/<int:seed>")
    def world_metadata(seed: int) -> Response:
        key = _build_key_from_request(seed, default_size, default_land_fraction)
        world = cache.get_or_build(key)
        return jsonify(_world_payload(world))

    @app.route("/api/world/<int:seed>/image.png")
    def world_image(seed: int) -> Response:
        key = _build_key_from_request(seed, default_size, default_land_fraction)
        world = cache.get_or_build(key)
        return send_file(io.BytesIO(world.image_bytes), mimetype="image/png", max_age=3600)

    @app.route("/api/world/<int:seed>/pickmap.png")
    def world_pickmap(seed: int) -> Response:
        key = _build_key_from_request(seed, default_size, default_land_fraction)
        world = cache.get_or_build(key)
        return send_file(io.BytesIO(world.pickmap_bytes), mimetype="image/png", max_age=3600)

    # ------------------ live simulation API ------------------

    @app.route("/api/sim/new", methods=["POST"])
    def sim_new() -> Response:
        body = request.get_json(silent=True) or {}
        seed = int(body.get("seed", 909))
        with sim_lock:
            existing = sim_box["session"]
            if existing is not None:
                existing.shutdown()
            session = SimulationSession(
                seed=seed,
                width=default_size[0],
                height=default_size[1],
                land_fraction=default_land_fraction,
                num_civilizations=4,
            )
            sim_box["session"] = session
        return jsonify(session.initial_payload())

    @app.route("/api/sim/state")
    def sim_state() -> Response:
        session = get_or_create_sim()
        return jsonify(session.state_payload())

    @app.route("/api/sim/initial")
    def sim_initial() -> Response:
        session = get_or_create_sim()
        return jsonify(session.initial_payload())

    @app.route("/api/sim/control", methods=["POST"])
    def sim_control() -> Response:
        body = request.get_json(silent=True) or {}
        action = str(body.get("action", ""))
        value = body.get("value")
        session = get_or_create_sim()
        try:
            payload = session.control(action, int(value) if value is not None else None)
        except ValueError as e:
            abort(400, str(e))
        return jsonify(payload)

    @app.route("/api/sim/civ/<civ_name>")
    def sim_civ(civ_name: str) -> Response:
        session = get_or_create_sim()
        payload = session.civ_payload(civ_name)
        if payload is None:
            abort(404)
        return jsonify(payload)

    @app.route("/api/sim/pause-rules", methods=["POST"])
    def sim_pause_rules() -> Response:
        body = request.get_json(silent=True) or {}
        rules = body.get("rules") or {}
        if not isinstance(rules, dict):
            abort(400, "rules must be an object")
        session = get_or_create_sim()
        return jsonify({"rules": session.set_pause_rules(rules)})

    @app.route("/api/sim/political.png")
    def sim_political_png() -> Response:
        session = get_or_create_sim()
        return send_file(io.BytesIO(session.political_image()), mimetype="image/png", max_age=3600)

    @app.route("/api/sim/base.png")
    def sim_base_png() -> Response:
        session = get_or_create_sim()
        return send_file(io.BytesIO(session.base_image()), mimetype="image/png", max_age=3600)

    @app.route("/api/sim/pickmap.png")
    def sim_pickmap_png() -> Response:
        session = get_or_create_sim()
        return send_file(io.BytesIO(session.pickmap_image()), mimetype="image/png", max_age=3600)

    @app.errorhandler(400)
    def bad_request(error) -> Response:
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error) -> Response:
        return jsonify({"error": "not found"}), 404

    return app


def _build_key_from_request(seed: int, default_size: tuple[int, int], default_land_fraction: float) -> WorldKey:
    width = _query_int("width", default_size[0], minimum=64, maximum=1024)
    height = _query_int("height", default_size[1], minimum=64, maximum=768)
    land_fraction = _query_float("land_fraction", default_land_fraction, minimum=0.1, maximum=0.85)
    return WorldKey(seed=int(seed), width=width, height=height, land_fraction=land_fraction)


def _query_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        abort(400, f"{name} must be an integer")
    if not (minimum <= value <= maximum):
        abort(400, f"{name} must be between {minimum} and {maximum}")
    return value


def _query_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        abort(400, f"{name} must be a number")
    if not (minimum <= value <= maximum):
        abort(400, f"{name} must be between {minimum} and {maximum}")
    return value


def _world_payload(world: CachedWorld) -> dict:
    geography = world.geography
    provinces = world.provinces
    return {
        "seed": world.key.seed,
        "width": world.key.width,
        "height": world.key.height,
        "land_fraction": world.key.land_fraction,
        "sea_level": geography.sea_level,
        "actual_land_fraction": float(geography.land_mask.mean()),
        "image_url": f"/api/world/{world.key.seed}/image.png?width={world.key.width}&height={world.key.height}",
        "pickmap_url": f"/api/world/{world.key.seed}/pickmap.png?width={world.key.width}&height={world.key.height}",
        "landmasses": [
            {
                "landmass_id": landmass.landmass_id,
                "cell_count": landmass.cell_count,
                "centroid_x": landmass.centroid_x,
                "centroid_y": landmass.centroid_y,
                "is_continent": landmass.is_continent,
            }
            for landmass in geography.landmasses
        ],
        "provinces": [_province_payload(province) for province in provinces.provinces],
    }


def _province_payload(province) -> dict:
    return {
        "province_id": province.province_id,
        "landmass_id": province.landmass_id,
        "name": province.name or f"Province #{province.province_id}",
        "cell_count": province.cell_count,
        "centroid_x": province.centroid_x,
        "centroid_y": province.centroid_y,
        "bounds": province.bounds,
        "dominant_biome": province.dominant_biome,
        "biome_mix": province.biome_mix,
        "mean_elevation": province.mean_elevation,
        "mean_temperature": province.mean_temperature,
        "mean_moisture": province.mean_moisture,
        "has_river": province.has_river,
        "is_coastal": province.is_coastal,
        "neighbor_ids": list(province.neighbor_ids),
    }

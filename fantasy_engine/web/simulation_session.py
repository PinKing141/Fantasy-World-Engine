"""Live simulation session for the web frontend.

Wraps a `World` + `SimulationController` with:
    * A background tick thread that advances the simulation when not paused.
    * Province → civilization assignment, so the procedural map can be colored
      by political ownership instead of biome alone.
    * A serializer that flattens the engine's snapshot dataclasses into JSON
      payloads the browser can poll.
    * Date math that maps engine ticks (seasonal) to a CK3-style calendar
      starting 15 September 867 AD.

This is the missing bridge described in the prior design conversation:
the engine's `World` already produces rich snapshots, the procedural
geography already produces clickable provinces, but they had never been
connected.

Threading:
    The session uses a single RLock for all mutating operations and snapshot
    reads. Flask's dev server is multi-threaded, so the lock is required
    even for read endpoints — they may race against the tick thread.
"""
from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from PIL import Image

from fantasy_engine.runner.controller import SimulationController
from fantasy_engine.visual.cartographer import CartographyOptions, RenderInputs, render_world
from fantasy_engine.world.geography import GeographyConfig, GeographyResult, generate_geography
from fantasy_engine.world.provinces import ProvinceMap, build_province_map
from fantasy_engine.world.world import World


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

START_DATE = date(867, 9, 15)
DAYS_PER_TICK = 91  # ~ one season

# Web-exposed speeds (paused = 0). Values are seconds-of-real-time per tick.
SPEED_INTERVALS_SEC = {1: 4.0, 2: 2.0, 3: 1.0, 4: 0.5, 5: 0.25}
DEFAULT_SPEED = 3

# Civilization color palette. Six visually distinct, CK3-flavoured paints.
CIV_COLORS: list[tuple[int, int, int]] = [
    (60, 105, 175),    # Sylgard — deep blue
    (60, 130, 80),     # Quor-Thal — forest green
    (170, 60, 50),     # Arador — oxblood
    (210, 160, 60),    # Zanthar — saffron
    (130, 70, 160),    # Velis — violet
    (50, 150, 150),    # Dunmere — teal
]

# Recent-events ring kept by the session so the UI ticker doesn't have to
# re-walk the whole archive each poll.
EVENT_RING_LIMIT = 80

# Default pause rules. True = autopause when an event of that type fires.
# Keys map to engine `event_type` strings on `HistoryEvent`/`EventSnapshot`.
DEFAULT_PAUSE_RULES: dict[str, bool] = {
    "famine":          True,
    "faction_coup":    True,
    "war_declaration": True,
    "route_severed":   True,
    "succession":      False,
    "battle":          False,
    "culture_split":   False,
    "migration":       False,
}

# Pretty labels for the pause-rule UI popover.
PAUSE_RULE_LABELS: dict[str, str] = {
    "famine":          "Famine",
    "faction_coup":    "Coup",
    "war_declaration": "War Declared",
    "route_severed":   "Trade Severed",
    "succession":      "Succession",
    "battle":          "Battle",
    "culture_split":   "Culture Split",
    "migration":       "Migration",
}

# When a war ends in diplomatic peace, fraction of the loser's border-with-
# winner provinces that change hands.
PEACE_TRANSFER_FRACTION = 0.32


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CivAssignment:
    """Owner index + cached spatial info for one civilization."""

    civ_index: int
    name: str
    color: tuple[int, int, int]
    province_ids: list[int]
    capital_province_id: int
    capital_xy: tuple[float, float]


class SimulationSession:
    def __init__(
        self,
        seed: int,
        *,
        width: int = 384,
        height: int = 240,
        land_fraction: float = 0.42,
        num_civilizations: int = 4,
    ) -> None:
        self._lock = threading.RLock()
        self.seed = seed
        self.num_civilizations = num_civilizations
        self._event_ring: list[dict] = []
        self._cached_step_result = None
        # War / map-mutation state (web-only; engine doesn't model conquest).
        self._active_war_pairs: set[tuple[str, str]] = set()
        self._political_image_version: int = 0
        self._pause_reason: str = ""
        self.pause_rules: dict[str, bool] = dict(DEFAULT_PAUSE_RULES)
        # Civs that have already been redistributed because they collapsed.
        self._collapsed_civs: set[str] = set()

        # --- procedural geography for the map ---
        geography_config = GeographyConfig(
            width=width, height=height, seed=seed, land_fraction=land_fraction,
        )
        self.geography: GeographyResult = generate_geography(geography_config)
        self.provinces: ProvinceMap = build_province_map(self.geography)

        # --- engine simulation ---
        self.world = World(seed=seed, num_civilizations=num_civilizations)
        self.controller = SimulationController(self.world, initial_speed=1.0)

        # --- province → civ ownership ---
        self.assignments: list[CivAssignment] = self._assign_provinces_to_civs()
        self.province_owner: np.ndarray = self._build_province_owner_grid()

        # --- pre-rendered map images ---
        # Render the biome base once and cache the RGB array so repeated
        # political-overlay rebuilds (after province transfers) don't re-run
        # the cartographer.
        self._base_rgb: np.ndarray = render_world(RenderInputs(
            geography=self.geography,
            provinces=self.provinces,
            options=CartographyOptions(),
        ))
        self.base_image_bytes: bytes = _encode_png(self._base_rgb)
        self.political_image_bytes: bytes = self._render_political_overlay()
        self.pickmap_bytes: bytes = self._render_pickmap()

        # --- clock / control ---
        self.paused: bool = True
        self.speed_level: int = DEFAULT_SPEED
        self._stop_event = threading.Event()
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()

    # -- public control API --------------------------------------------------

    def shutdown(self) -> None:
        self._stop_event.set()
        self._tick_thread.join(timeout=2.0)

    def control(self, action: str, value: int | None = None) -> dict:
        with self._lock:
            if action == "pause":
                self.paused = True
            elif action == "resume":
                self.paused = False
                self._pause_reason = ""
            elif action == "toggle":
                self.paused = not self.paused
                if not self.paused:
                    self._pause_reason = ""
            elif action == "speed":
                if value is None or value < 1 or value > 5:
                    raise ValueError("speed must be 1..5")
                self.speed_level = int(value)
                self.paused = False
                self._pause_reason = ""
            elif action == "step":
                # Force one tick even when paused.
                self._tick_once_locked()
            else:
                raise ValueError(f"unknown action {action!r}")
            return self._control_payload_locked()

    def set_pause_rules(self, rules: dict) -> dict:
        """Merge `rules` into the current pause rules (only known keys). Returns
        the resulting full rule set."""
        with self._lock:
            for key, val in rules.items():
                if key in self.pause_rules:
                    self.pause_rules[key] = bool(val)
            return dict(self.pause_rules)

    # -- payloads ------------------------------------------------------------

    def state_payload(self) -> dict:
        with self._lock:
            return self._state_payload_locked()

    def civ_payload(self, name: str) -> dict | None:
        with self._lock:
            for civ_snap in self._cached_civ_snapshots():
                if civ_snap.name == name:
                    return self._serialize_civ_full(civ_snap)
            return None

    def base_image(self) -> bytes:
        return self.base_image_bytes

    def political_image(self) -> bytes:
        return self.political_image_bytes

    def pickmap_image(self) -> bytes:
        return self.pickmap_bytes

    def initial_payload(self) -> dict:
        """One-time payload sent to the browser on session start: includes
        static geometry that never changes for a given seed."""
        with self._lock:
            assignments = [
                {
                    "civ_index": a.civ_index,
                    "name": a.name,
                    "color": "#{:02x}{:02x}{:02x}".format(*a.color),
                    "capital_xy": a.capital_xy,
                    "province_count": len(a.province_ids),
                }
                for a in self.assignments
            ]
            return {
                "seed": self.seed,
                "width": self.geography.config.width,
                "height": self.geography.config.height,
                "civilizations": assignments,
                "province_owners": self._province_owner_names_locked(),
                "image_url": f"/api/sim/political.png?v={self._political_image_version}",
                "base_image_url": "/api/sim/base.png",
                "pickmap_url": "/api/sim/pickmap.png",
                "state": self._state_payload_locked(),
            }

    # -- province lookup -----------------------------------------------------

    def civ_for_province(self, province_id: int) -> str | None:
        if province_id < 0 or province_id >= len(self.provinces.provinces):
            return None
        owner_idx = int(self.province_owner.flat[province_id])
        if owner_idx < 0 or owner_idx >= len(self.assignments):
            return None
        return self.assignments[owner_idx].name

    # =========================================================================
    # Internal: ticking
    # =========================================================================

    def _tick_loop(self) -> None:
        next_tick_time = time.monotonic()
        while not self._stop_event.is_set():
            with self._lock:
                paused = self.paused
                interval = SPEED_INTERVALS_SEC[self.speed_level]

            if paused:
                # While paused, hold next_tick_time at "now" so resume fires
                # the next tick immediately instead of waiting out the leftover
                # interval from before the pause.
                time.sleep(0.05)
                next_tick_time = time.monotonic()
                continue

            now = time.monotonic()
            if now < next_tick_time:
                time.sleep(min(0.05, next_tick_time - now))
                continue

            with self._lock:
                self._tick_once_locked()
            next_tick_time = time.monotonic() + interval

    def _tick_once_locked(self) -> None:
        result = self.controller.step()
        self._cached_step_result = result
        for ev in result.event_snapshots:
            self._event_ring.append({
                "year": result.year,
                "season": result.season,
                "date": _format_date(self.world.total_ticks - 1),
                "type": ev.event_type,
                "label": ev.label,
                "civilization": ev.civilization,
                "other_civilization": ev.other_civilization,
                "details": ev.details,
                "severity": ev.severity,
            })
        if len(self._event_ring) > EVENT_RING_LIMIT:
            self._event_ring[:] = self._event_ring[-EVENT_RING_LIMIT:]

        # Map-mutation passes: react to war declarations + peace + collapses.
        # Engine knows nothing about provinces; this is the bridge.
        self._handle_war_events(result.events)
        self._check_collapses()

        # Configurable autopause. Walk the new events and pause on the first
        # match in our enabled rule set.
        autopause_event = self._find_autopause_event(result.events)
        if autopause_event is not None:
            self.paused = True
            label = autopause_event.label or autopause_event.event_type
            self._pause_reason = f"{label} · {autopause_event.civilization}"

    # =========================================================================
    # Internal: payloads
    # =========================================================================

    def _control_payload_locked(self) -> dict:
        return {
            "paused": self.paused,
            "speed": self.speed_level,
            "date": _format_date(self.world.total_ticks),
        }

    def _state_payload_locked(self) -> dict:
        snap = self.controller.current_result()
        date_str = _format_date(self.world.total_ticks)
        return {
            "date": date_str,
            "year": self.world.year,
            "season": self.world.current_season,
            "tick": self.world.total_ticks,
            "paused": self.paused,
            "speed": self.speed_level,
            "active_wars": [list(w) for w in snap.active_wars],
            "active_war_borders": self._compute_active_war_borders(),
            "civilizations": [
                self._serialize_civ_summary(c) for c in snap.civilization_snapshots
            ],
            "events": list(self._event_ring[-30:]),
            "legends": list(self.world.recent_legend_summaries(limit=3)),
            "pause_reason": self._pause_reason or snap.pause_reason or "",
            "pause_rules": dict(self.pause_rules),
            "pause_rule_labels": dict(PAUSE_RULE_LABELS),
            "province_owners": self._province_owner_names_locked(),
            "political_image_url": f"/api/sim/political.png?v={self._political_image_version}",
            "political_image_version": self._political_image_version,
        }

    def _province_owner_names_locked(self) -> list[str]:
        province_owners: list[str] = ["" for _ in self.provinces.provinces]
        for assignment in self.assignments:
            for province_id in assignment.province_ids:
                if 0 <= province_id < len(province_owners):
                    province_owners[province_id] = assignment.name
        return province_owners

    def _cached_civ_snapshots(self) -> list:
        return self.controller.current_result().civilization_snapshots

    def _serialize_civ_summary(self, civ_snap) -> dict:
        assign = self._assignment_for(civ_snap.name)
        ruler = civ_snap.court
        return {
            "name": civ_snap.name,
            "color": "#{:02x}{:02x}{:02x}".format(*assign.color) if assign else "#888888",
            "ruler": ruler.ruler_name,
            "ruler_dynasty": ruler.ruler_dynasty,
            "heir": ruler.heir_name,
            "culture": civ_snap.culture_id,
            "region": civ_snap.region_name,
            "terrain": civ_snap.terrain_name,
            "population": civ_snap.population,
            "stability": round(civ_snap.stability, 3),
            "legitimacy": round(civ_snap.legitimacy, 3),
            "unrest": round(civ_snap.unrest, 3),
            "grain_stores": civ_snap.grain_stores,
            "food_stores": civ_snap.food_stores,
            "weapons": civ_snap.weapons_stockpile,
            "supply": civ_snap.supply_stockpile,
            "at_war_with": list(civ_snap.at_war_with),
            "contested_routes": civ_snap.contested_routes,
            "severed_routes": civ_snap.severed_routes,
            "faction_count": len(civ_snap.factions),
        }

    def _serialize_civ_full(self, civ_snap) -> dict:
        summary = self._serialize_civ_summary(civ_snap)
        court = civ_snap.court
        realm_name = civ_snap.name
        realm_color = summary["color"]
        summary["court"] = {
            "ruler": _bio_dict(court.ruler_bio, civilization=realm_name, realm_color=realm_color) if court.ruler_bio else _name_only(court.ruler_name, court.ruler_dynasty, civilization=realm_name, realm_color=realm_color),
            "heir": _bio_dict(court.heir_bio, civilization=realm_name, realm_color=realm_color) if court.heir_bio else _name_only(court.heir_name or "—", "", civilization=realm_name, realm_color=realm_color),
            "general": _bio_dict(court.general_bio, civilization=realm_name, realm_color=realm_color) if court.general_bio else _name_only(court.general_name, "", civilization=realm_name, realm_color=realm_color),
            "diplomat": _bio_dict(court.diplomat_bio, civilization=realm_name, realm_color=realm_color) if court.diplomat_bio else _name_only(court.diplomat_name, "", civilization=realm_name, realm_color=realm_color),
            "consort": _bio_dict(court.consort_bio, civilization=realm_name, realm_color=realm_color) if court.consort_bio else None,
            "steward": _bio_dict(court.steward_bio, civilization=realm_name, realm_color=realm_color) if court.steward_bio else None,
        }
        summary["factions"] = [
            {
                "name": f.name,
                "agenda": f.agenda,
                "leader_name": f.leader_name,
                "dynasty": f.dynasty_name,
                "pressure": round(f.pressure, 3),
                "leader_bio": _bio_dict(f.leader_bio, civilization=realm_name, realm_color=realm_color) if f.leader_bio else None,
            }
            for f in civ_snap.factions
        ]
        # Diplomatic relations from the live Civilization object.
        live = self.world.get_civilization(civ_snap.name)
        if live:
            summary["relations"] = [
                {"with": other, "value": round(value, 1)}
                for other, value in sorted(live.relations.items(), key=lambda x: -x[1])
            ]
            summary["faith"] = live.faith_id
            summary["faith_origin"] = live.faith_origin_id or live.faith_id
            summary["schism_pressure"] = round(live.schism_pressure, 3)
            summary["treasury"] = live.treasury
            summary["war_exhaustion"] = round(live.war_exhaustion, 3)
        # Province count and sample names from assignment.
        assign = self._assignment_for(civ_snap.name)
        if assign:
            sample = []
            for pid in assign.province_ids[:8]:
                p = self.provinces.provinces[pid]
                sample.append({"id": p.province_id, "name": p.name or f"Province #{p.province_id}", "biome": p.dominant_biome})
            summary["provinces"] = sample
            summary["province_count"] = len(assign.province_ids)
            summary["capital_province_id"] = assign.capital_province_id
        # Owned holdings list — derive from province count buckets.
        return summary

    def _assignment_for(self, civ_name: str) -> CivAssignment | None:
        for a in self.assignments:
            if a.name == civ_name:
                return a
        return None

    # =========================================================================
    # Internal: province → civ assignment
    # =========================================================================

    def _assign_provinces_to_civs(self) -> list[CivAssignment]:
        """Distribute civilizations across the largest landmasses, then
        hand each remaining province to its nearest civilization seed.

        The result is contiguous-ish per civ without forcing all civs onto
        one continent — mirrors the CK3 "regional starting position" feel.
        """
        provinces = self.provinces.provinces
        if not provinces:
            return []

        civs = self.world.civilizations
        num_civs = len(civs)
        rng = np.random.default_rng(self.seed * 31 + 7)

        # 1. Sort landmasses by size; spread civ seed points across them.
        landmasses = sorted(self.geography.landmasses, key=lambda lm: -lm.cell_count)
        seed_points: list[tuple[float, float]] = []
        # Distribute civs round-robin across the top N landmasses (or fewer if not enough).
        target_landmasses = landmasses[: max(1, min(num_civs, max(1, len(landmasses))))]
        # Place at least one seed on each of the largest landmasses, then top up.
        used_per_landmass: dict[int, int] = {}
        for i in range(num_civs):
            lm = target_landmasses[i % len(target_landmasses)]
            count = used_per_landmass.get(lm.landmass_id, 0)
            # Place seed offset from the centroid for variety; on second+ seed of
            # the same landmass, spread across its bounds.
            min_x, min_y, max_x, max_y = lm.bounds
            jitter_x = rng.uniform(-0.25, 0.25) * (max_x - min_x + 1)
            jitter_y = rng.uniform(-0.25, 0.25) * (max_y - min_y + 1)
            sx = float(np.clip(lm.centroid_x + jitter_x, min_x, max_x))
            sy = float(np.clip(lm.centroid_y + jitter_y, min_y, max_y))
            if count > 0:
                # Push further out for second seeds on the same landmass.
                sx = float(np.clip(lm.centroid_x + (count * 0.6 - 0.3) * (max_x - min_x + 1), min_x, max_x))
                sy = float(np.clip(lm.centroid_y + (rng.uniform(-0.4, 0.4)) * (max_y - min_y + 1), min_y, max_y))
            seed_points.append((sx, sy))
            used_per_landmass[lm.landmass_id] = count + 1

        # 2. Assign each province to its nearest seed.
        owner_for_province = [0] * len(provinces)
        for pid, prov in enumerate(provinces):
            best_idx = 0
            best_dist = float("inf")
            for ci, (sx, sy) in enumerate(seed_points):
                dx = prov.centroid_x - sx
                dy = prov.centroid_y - sy
                d2 = dx * dx + dy * dy
                if d2 < best_dist:
                    best_dist = d2
                    best_idx = ci
            owner_for_province[pid] = best_idx

        # 3. Build assignment records, finding each civ's capital province
        #    (the province nearest to that civ's seed point).
        assignments: list[CivAssignment] = []
        for ci, civ in enumerate(civs):
            province_ids = [pid for pid, owner in enumerate(owner_for_province) if owner == ci]
            if not province_ids:
                # Pick the nearest province to the seed even if it's already taken.
                sx, sy = seed_points[ci]
                pid = min(
                    range(len(provinces)),
                    key=lambda p: (provinces[p].centroid_x - sx) ** 2 + (provinces[p].centroid_y - sy) ** 2,
                )
                province_ids = [pid]
            sx, sy = seed_points[ci]
            capital_pid = min(
                province_ids,
                key=lambda p: (provinces[p].centroid_x - sx) ** 2 + (provinces[p].centroid_y - sy) ** 2,
            )
            cap = provinces[capital_pid]
            assignments.append(CivAssignment(
                civ_index=ci,
                name=civ.name,
                color=CIV_COLORS[ci % len(CIV_COLORS)],
                province_ids=province_ids,
                capital_province_id=capital_pid,
                capital_xy=(cap.centroid_x, cap.centroid_y),
            ))
        return assignments

    def _build_province_owner_grid(self) -> np.ndarray:
        """Flat array: index = province_id, value = civ_index (or -1)."""
        owner = np.full((len(self.provinces.provinces),), -1, dtype=np.int32)
        for a in self.assignments:
            for pid in a.province_ids:
                owner[pid] = a.civ_index
        return owner

    # =========================================================================
    # Internal: war handling, collapse, province transfer
    # =========================================================================

    def _handle_war_events(self, events) -> None:
        """Maintain `_active_war_pairs` from declarations and execute partial
        annexations when peace is signed.

        Engine events carry actor/target IDs in `event.data`; we resolve those
        back to civilizations because the engine itself never says "civ X
        defeated civ Y" — only "general A's force broke general B's force"."""
        if not events:
            return
        for event in events:
            etype = event.event_type
            if etype == "war_declaration":
                pair = self._civ_pair_from_event(event)
                if pair is not None:
                    self._active_war_pairs.add(pair)
            elif etype == "diplomatic_peace":
                winner, loser = self._winner_loser_from_event(event)
                if winner and loser:
                    self._discard_pair(winner, loser)
                    if winner != loser:
                        self._transfer_provinces(loser, winner, PEACE_TRANSFER_FRACTION)
                else:
                    # We can at least drop any pair containing the event's
                    # civilizations so stale active wars don't linger.
                    pair = self._civ_pair_from_event(event)
                    if pair:
                        self._active_war_pairs.discard(tuple(sorted(pair)))

    def _check_collapses(self) -> None:
        """If any civ now has population <= 0, redistribute its provinces among
        the closest surviving neighbors. Each civ is collapsed at most once."""
        for civ in self.world.civilizations:
            if civ.name in self._collapsed_civs:
                continue
            if civ.population <= 0:
                self._collapsed_civs.add(civ.name)
                self._distribute_collapsed(civ.name)
                # Drop any active war pairs the now-extinct civ was in.
                self._active_war_pairs = {p for p in self._active_war_pairs if civ.name not in p}

    def _distribute_collapsed(self, loser_name: str) -> None:
        """When a civilization dies, hand its provinces to whichever surviving
        civ is geographically nearest (by centroid distance). Each province is
        decided independently so the splinter is geographic, not political."""
        loser = self._assignment_for(loser_name)
        if loser is None or not loser.province_ids:
            return
        survivors = [a for a in self.assignments if a.name != loser_name and a.province_ids]
        if not survivors:
            return

        provinces = self.provinces.provinces
        new_owner_for: dict[int, str] = {}
        for pid in loser.province_ids:
            cx, cy = provinces[pid].centroid_x, provinces[pid].centroid_y
            best = min(
                survivors,
                key=lambda a: (
                    (provinces[a.capital_province_id].centroid_x - cx) ** 2
                    + (provinces[a.capital_province_id].centroid_y - cy) ** 2
                ),
            )
            new_owner_for[pid] = best.name

        # Apply transfers.
        for pid, target_name in new_owner_for.items():
            self._reassign_province(pid, loser_name, target_name)
        loser.province_ids = []
        self._finalize_ownership_change()

    def _transfer_provinces(self, loser_name: str, winner_name: str, fraction: float) -> None:
        """Hand `fraction` of the loser's border-with-winner provinces to the
        winner. Border = any province in `loser` with at least one neighbor
        owned by `winner`. Always transfers at least one province if any
        border exists, so a peace event is never silent."""
        loser = self._assignment_for(loser_name)
        winner = self._assignment_for(winner_name)
        if loser is None or winner is None:
            return
        if not loser.province_ids:
            return
        winner_set = set(winner.province_ids)
        border = []
        for pid in loser.province_ids:
            province = self.provinces.provinces[pid]
            if any(neighbor in winner_set for neighbor in province.neighbor_ids):
                border.append(pid)
        if not border:
            return  # not adjacent — nothing to flip
        n_transfer = max(1, int(len(border) * fraction))
        # Prefer border provinces whose neighbors are MOST winner-owned, so
        # the flip looks coherent and doesn't carve random cells.
        def winner_neighbour_count(pid: int) -> int:
            return sum(1 for n in self.provinces.provinces[pid].neighbor_ids if n in winner_set)
        border.sort(key=winner_neighbour_count, reverse=True)
        for pid in border[:n_transfer]:
            self._reassign_province(pid, loser_name, winner_name)
        self._absorb_single_enclaves()
        self._finalize_ownership_change()

    def _reassign_province(self, province_id: int, from_name: str, to_name: str) -> None:
        from_assign = self._assignment_for(from_name)
        to_assign = self._assignment_for(to_name)
        if from_assign is None or to_assign is None:
            return
        if province_id in from_assign.province_ids:
            from_assign.province_ids.remove(province_id)
        if province_id not in to_assign.province_ids:
            to_assign.province_ids.append(province_id)

    def _absorb_single_enclaves(self) -> None:
        """Any province whose every neighbor belongs to a single different civ
        flips to that neighbor — kills 1-cell speckle after a transfer."""
        provinces = self.provinces.provinces
        province_owner_name: dict[int, str] = {}
        for a in self.assignments:
            for pid in a.province_ids:
                province_owner_name[pid] = a.name
        flips: list[tuple[int, str, str]] = []
        for pid, current_owner in province_owner_name.items():
            neighbors = provinces[pid].neighbor_ids
            if not neighbors:
                continue
            neighbor_owners = {province_owner_name.get(n) for n in neighbors if n in province_owner_name}
            neighbor_owners.discard(None)
            if len(neighbor_owners) == 1:
                only = next(iter(neighbor_owners))
                if only != current_owner:
                    flips.append((pid, current_owner, only))
        for pid, from_name, to_name in flips:
            self._reassign_province(pid, from_name, to_name)

    def _finalize_ownership_change(self) -> None:
        """Rebuild caches after any province transfer."""
        self.province_owner = self._build_province_owner_grid()
        self.political_image_bytes = self._render_political_overlay()
        self._political_image_version += 1
        # Update each civ's capital province if its previous capital is now
        # owned by someone else (e.g. on collapse).
        for assign in self.assignments:
            if not assign.province_ids:
                continue
            if assign.capital_province_id not in assign.province_ids:
                # Pick the province closest to the original capital coords.
                cx, cy = assign.capital_xy
                provinces = self.provinces.provinces
                new_capital = min(
                    assign.province_ids,
                    key=lambda p: (provinces[p].centroid_x - cx) ** 2 + (provinces[p].centroid_y - cy) ** 2,
                )
                assign.capital_province_id = new_capital

    def _civ_pair_from_event(self, event) -> tuple[str, str] | None:
        a = event.civilization
        b = event.other_civilization
        if not a or not b:
            return None
        if a == b:
            return None
        return tuple(sorted((a, b)))

    def _discard_pair(self, civ_a: str, civ_b: str) -> None:
        self._active_war_pairs.discard(tuple(sorted((civ_a, civ_b))))

    def _winner_loser_from_event(self, event) -> tuple[str | None, str | None]:
        """Resolve diplomatic_peace event payload → (winner_name, loser_name).
        Engine encodes the call with `winner_general_id` and `loser_general_id`
        on the data dict."""
        winner_id = event.data.get("winner_general_id")
        loser_id = event.data.get("loser_general_id")
        winner_name = self._civ_name_for_general(winner_id) if winner_id else None
        loser_name = self._civ_name_for_general(loser_id) if loser_id else None
        # Fallback: the event's own civ + other_civ; in peace events the actor
        # is the diplomat of the winning side per the engine's convention.
        if not winner_name and event.civilization:
            winner_name = event.civilization
        if not loser_name and event.other_civilization:
            loser_name = event.other_civilization
        return winner_name, loser_name

    def _civ_name_for_general(self, general_id) -> str | None:
        for civ in self.world.civilizations:
            if civ.court.general.agent_id == general_id:
                return civ.name
        return None

    def _find_autopause_event(self, events):
        """Return the first event whose type is enabled in pause_rules, else
        None. Honors the user-configurable rule set instead of the controller's
        hardcoded freezesets."""
        for event in events:
            if self.pause_rules.get(event.event_type, False):
                return event
        return None

    def _compute_active_war_borders(self) -> list[dict]:
        """For each active war pair, return the union of belligerents' border
        provinces (each side's provinces that touch the other side). The JS
        canvas paints a hatched red overlay over these cells.

        Active war pairs come from `_active_war_pairs`; we cross-check with the
        engine's `civ.active_wars` because the engine may end a war via routes
        or collapse without firing a `diplomatic_peace` event."""
        live_pairs: set[tuple[str, str]] = set()
        for civ in self.world.civilizations:
            for target in civ.active_wars:
                live_pairs.add(tuple(sorted((civ.name, target))))
        pairs = self._active_war_pairs & live_pairs if self._active_war_pairs else live_pairs
        # Keep `_active_war_pairs` in sync so it doesn't accumulate stale data.
        self._active_war_pairs = set(live_pairs)

        results: list[dict] = []
        for civ_a, civ_b in pairs:
            assign_a = self._assignment_for(civ_a)
            assign_b = self._assignment_for(civ_b)
            if assign_a is None or assign_b is None:
                continue
            set_a, set_b = set(assign_a.province_ids), set(assign_b.province_ids)
            border_ids: list[int] = []
            for pid in assign_a.province_ids:
                if any(n in set_b for n in self.provinces.provinces[pid].neighbor_ids):
                    border_ids.append(pid)
            for pid in assign_b.province_ids:
                if any(n in set_a for n in self.provinces.provinces[pid].neighbor_ids):
                    border_ids.append(pid)
            if border_ids:
                results.append({
                    "civ_a": civ_a,
                    "civ_b": civ_b,
                    "province_ids": border_ids,
                })
        return results

    # =========================================================================
    # Internal: image rendering
    # =========================================================================

    def _render_political_overlay(self) -> bytes:
        """Tint each land province with its owner civilization's color while
        keeping a hint of the underlying biome lightness so terrain still
        reads through. Water cells stay biome-blue (CK3-style). """
        geography = self.geography
        provinces = self.provinces
        height, width = geography.elevation.shape

        # Use the cached biome base instead of re-rendering — big win when
        # this method is called repeatedly after province transfers.
        base_rgb = self._base_rgb.astype(np.float32)

        # Build a per-pixel civ color grid (default = base color → unchanged).
        province_grid = provinces.province_id_grid
        land_mask = geography.land_mask

        owner_color = np.zeros((height, width, 3), dtype=np.float32)
        owned_mask = np.zeros((height, width), dtype=bool)
        for assign in self.assignments:
            cr, cg, cb = assign.color
            for pid in assign.province_ids:
                pixels = province_grid == pid
                owner_color[pixels] = (cr, cg, cb)
                owned_mask |= pixels

        # Blend: 55% civ color + 45% biome shading on owned land. Lerp so
        # mountains stay darker than plains within the same realm.
        blend = np.where(
            owned_mask[..., None],
            owner_color * 0.55 + base_rgb * 0.45,
            base_rgb,
        )

        # Boost civ-color saturation slightly on plains so the political color
        # is the dominant signal. Keep ocean fully untouched.
        result = np.clip(blend, 0, 255).astype(np.uint8)
        # Re-apply ocean from base so we don't tint water.
        water_mask = ~land_mask
        result[water_mask] = base_rgb[water_mask].astype(np.uint8)
        return _encode_png(result)

    def _render_pickmap(self) -> bytes:
        """Same encoding as the original viewer: province id in R+G, water in B."""
        geography = self.geography
        provinces = self.provinces
        height, width = geography.elevation.shape
        pickmap = np.zeros((height, width, 3), dtype=np.uint8)
        province_ids = provinces.province_id_grid
        has_province = province_ids >= 0
        pickmap[..., 0] = np.where(has_province, province_ids & 0xFF, 0).astype(np.uint8)
        pickmap[..., 1] = np.where(has_province, (province_ids >> 8) & 0xFF, 0).astype(np.uint8)
        pickmap[..., 2] = np.where(geography.land_mask, 0, 255).astype(np.uint8)
        return _encode_png(pickmap)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_png(rgb: np.ndarray) -> bytes:
    image = Image.fromarray(rgb, mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def _format_date(total_ticks: int) -> str:
    """Engine ticks are seasons (~91 days). Map to DD/MM/YYYY starting 867."""
    d = START_DATE + timedelta(days=total_ticks * DAYS_PER_TICK)
    return f"{d.day:02d}/{d.month:02d}/{d.year:04d}"


def _bio_dict(bio, *, civilization: str = "", realm_color: str = "") -> dict:
    return {
        "agent_id": bio.agent_id,
        "name": bio.name,
        "role": bio.role,
        "dynasty": bio.dynasty_name,
        "civilization": civilization,
        "realm_color": realm_color,
        "culture": bio.culture_id,
        "age": bio.age,
        "birth_year": bio.estimated_birth_year,
        "gender": getattr(bio, "gender", "") or "",
        "profession": getattr(bio, "profession", "") or "",
        "alive": bool(getattr(bio, "alive", True)),
        "heroic_title": getattr(bio, "heroic_title", None),
        "health": round(bio.health, 3),
        "loyalty": round(bio.loyalty, 3),
        "authority": round(bio.authority, 3),
        "grievance": round(bio.grievance, 3),
        "fatigue": round(bio.fatigue, 3),
        "relation_to_ruler": bio.relation_to_ruler,
        "parents": list(bio.parent_names),
        "grudges": list(bio.grudge_targets),
        "needs": {
            "food": round(bio.needs.food, 3),
            "safety": round(bio.needs.safety, 3),
            "belonging": round(bio.needs.belonging, 3),
            "esteem": round(bio.needs.esteem, 3),
        },
        "recent_events": list(bio.recent_events),
    }


def _name_only(name: str, dynasty: str, *, civilization: str = "", realm_color: str = "") -> dict:
    return {"agent_id": "", "name": name, "dynasty": dynasty, "role": "", "civilization": civilization,
            "realm_color": realm_color, "age": 0, "birth_year": 0,
            "gender": "", "profession": "", "alive": True, "heroic_title": None,
            "health": 0, "loyalty": 0, "authority": 0, "grievance": 0, "fatigue": 0,
            "relation_to_ruler": "", "parents": [], "grudges": [],
            "needs": {"food": 0, "safety": 0, "belonging": 0, "esteem": 0},
            "recent_events": [], "culture": ""}

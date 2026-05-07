"""Procedural continent geography generator.

This module produces a deterministic, seed-driven physical world: elevation,
moisture, temperature, biomes, and river networks. It is independent of the
political simulation (civilizations, courts, factions) and is consumed both
by the static cartographer and by the interactive map runtime.

The generation pipeline:
    1. Plate seed scatter           -> rough continent shapes
    2. Elevation noise              -> fractal terrain on top of plates
    3. Sea-level masking            -> land vs. water classification
    4. Distance-from-coast pass     -> moderates climate
    5. Temperature field            -> latitude + elevation + noise
    6. Moisture field               -> prevailing-wind + ocean proximity
    7. Biome classification         -> elevation x temperature x moisture
    8. River tracing                -> downhill flow accumulation
    9. Continent labeling           -> connected-component landmass IDs

All stages are deterministic for a given (seed, width, height).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from typing import Iterable

import numpy as np
from noise import snoise2


# Biome ids used throughout the engine. Stable for save/load.
BIOME_DEEP_OCEAN = "deep_ocean"
BIOME_OCEAN = "ocean"
BIOME_COAST = "coast"
BIOME_BEACH = "beach"
BIOME_DESERT = "desert"
BIOME_SAVANNA = "savanna"
BIOME_GRASSLAND = "grassland"
BIOME_SHRUBLAND = "shrubland"
BIOME_TEMPERATE_FOREST = "temperate_forest"
BIOME_RAINFOREST = "rainforest"
BIOME_BOREAL = "boreal"
BIOME_TAIGA = "taiga"
BIOME_TUNDRA = "tundra"
BIOME_GLACIER = "glacier"
BIOME_HILLS = "hills"
BIOME_MOUNTAIN = "mountain"
BIOME_PEAK = "peak"


BIOME_COLORS: dict[str, tuple[int, int, int]] = {
    BIOME_DEEP_OCEAN: (22, 46, 84),
    BIOME_OCEAN: (44, 92, 146),
    BIOME_COAST: (98, 156, 186),
    BIOME_BEACH: (228, 208, 158),
    BIOME_DESERT: (228, 196, 130),
    BIOME_SAVANNA: (188, 174, 96),
    BIOME_GRASSLAND: (130, 168, 76),
    BIOME_SHRUBLAND: (158, 158, 102),
    BIOME_TEMPERATE_FOREST: (76, 124, 60),
    BIOME_RAINFOREST: (38, 92, 50),
    BIOME_BOREAL: (84, 122, 92),
    BIOME_TAIGA: (104, 138, 116),
    BIOME_TUNDRA: (188, 192, 178),
    BIOME_GLACIER: (228, 234, 240),
    BIOME_HILLS: (132, 138, 84),
    BIOME_MOUNTAIN: (134, 116, 96),
    BIOME_PEAK: (240, 236, 230),
}


@dataclass(frozen=True, slots=True)
class GeographyConfig:
    """Tunable inputs for the generator. Exposed so callers can experiment
    without poking at internal noise parameters."""

    width: int = 512
    height: int = 320
    seed: int = 909
    land_fraction: float = 0.42
    """Target fraction of cells that should be land. Sea level is calibrated
    to hit this quantile of the elevation distribution, which produces
    consistent map character across seeds - exactly what map generators like
    Azgaar's and the Dwarf Fortress overworld do."""
    plate_count: int = 7
    mountain_strength: float = 0.42
    river_count: int = 28
    erosion_passes: int = 2

    @property
    def sea_level(self) -> float:
        """Resolved at generation time from land_fraction. Kept as a property
        for callers that previously read sea_level directly."""
        return 0.0


@dataclass(slots=True)
class GeographyResult:
    """The full procedural geography. All grids are shaped (height, width)."""

    config: GeographyConfig
    sea_level: float
    """Calibrated sea level; cells with elevation >= sea_level are land."""
    elevation: np.ndarray
    """Float32, range roughly -1.0 (deep sea) to +1.0 (peaks)."""
    temperature: np.ndarray
    moisture: np.ndarray
    biome: np.ndarray
    biome_names: list[str]
    landmass_id: np.ndarray
    rivers: np.ndarray
    coastline: np.ndarray
    landmasses: list["LandmassInfo"] = field(default_factory=list)

    @property
    def land_mask(self) -> np.ndarray:
        return self.elevation >= self.sea_level

    def biome_at(self, x: int, y: int) -> str:
        return self.biome_names[int(self.biome[y, x])]


@dataclass(frozen=True, slots=True)
class LandmassInfo:
    """A connected continent or island. Useful for placing civilizations and
    for player-facing 'go to continent' navigation in the interactive runtime."""

    landmass_id: int
    cell_count: int
    centroid_x: float
    centroid_y: float
    bounds: tuple[int, int, int, int]
    is_continent: bool


def generate_geography(config: GeographyConfig) -> GeographyResult:
    """Produce a full geography for the given config.

    This is the only function callers should reach for. Subroutines below are
    exposed for testing but are not part of the supported surface.
    """
    rng = np.random.default_rng(config.seed)

    plates = _scatter_plates(config, rng)
    elevation = _build_elevation(config, plates)
    elevation = _apply_erosion(elevation, config)

    sea_level = float(np.quantile(elevation, 1.0 - config.land_fraction))
    land_mask = elevation >= sea_level

    coast_distance = _coast_distance_field(land_mask)

    temperature = _build_temperature(config, elevation, coast_distance, sea_level)
    moisture = _build_moisture(config, elevation, coast_distance, land_mask, sea_level)

    rivers, _ = _trace_rivers(elevation, land_mask, moisture, config, sea_level)
    rivers = rivers & land_mask
    moisture_with_rivers = np.where(rivers, np.maximum(moisture, 0.65), moisture)

    biome_grid, biome_names = _classify_biomes(elevation, temperature, moisture_with_rivers, land_mask, sea_level)
    coastline = _coastline_mask(land_mask)
    landmass_id, landmasses = _label_landmasses(land_mask, config)

    return GeographyResult(
        config=config,
        sea_level=sea_level,
        elevation=elevation,
        temperature=temperature,
        moisture=moisture_with_rivers,
        biome=biome_grid,
        biome_names=biome_names,
        landmass_id=landmass_id,
        rivers=rivers,
        coastline=coastline,
        landmasses=landmasses,
    )


def _scatter_plates(config: GeographyConfig, rng: np.random.Generator) -> np.ndarray:
    """Place plate seed points and return their (x, y, plate_kind) arrays.

    plate_kind is 0 for oceanic (pulls elevation down) and 1 for continental
    (pushes elevation up). The mix matters: too few continental plates and the
    map is mostly water; too many and continents merge into one supercontinent.
    """
    count = config.plate_count
    xs = rng.uniform(0.0, config.width, size=count)
    ys = rng.uniform(0.0, config.height, size=count)
    kinds = (rng.random(count) < 0.55).astype(np.float32)
    return np.stack([xs, ys, kinds], axis=1)


def _build_elevation(config: GeographyConfig, plates: np.ndarray) -> np.ndarray:
    """Combine plate influence + multi-octave noise into a final heightfield.

    The plate influence is the dominant low-frequency signal: it determines
    where continents want to be. Noise then carves coastlines and ridges so
    nothing reads as a circle. The actual land:water ratio is set later by
    quantile-calibrated sea level, not here.
    """
    width, height, seed = config.width, config.height, config.seed
    plate_field = _plate_influence_field(width, height, plates)

    detail = _fractal_noise(width, height, seed=seed, scale=110.0, octaves=6, persistence=0.55, lacunarity=2.05)
    ridge = _ridge_noise(width, height, seed=seed + 1009, scale=180.0)

    elevation = (
        plate_field * 0.62
        + detail * 0.30
        + ridge * config.mountain_strength * 0.45
    )

    elevation *= _edge_falloff(width, height, strength=0.25)
    elevation = _normalize_signed(elevation)
    return elevation.astype(np.float32)


def _plate_influence_field(width: int, height: int, plates: np.ndarray) -> np.ndarray:
    """Each cell's plate field is determined by its distance to the nearest
    seed point and that seed's kind. Continental seeds raise terrain; oceanic
    seeds lower it. The exponential falloff produces broad, smooth continents."""
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    field = np.zeros((height, width), dtype=np.float32)
    falloff_scale = max(width, height) * 0.18

    for plate in plates:
        plate_x, plate_y, kind = plate
        dx = xs - plate_x
        dy = ys - plate_y
        distance = np.sqrt(dx * dx + dy * dy)
        weight = np.exp(-distance / falloff_scale)
        field += weight * (1.0 if kind > 0.5 else -1.0)

    return field


def _fractal_noise(width: int, height: int, *, seed: int, scale: float, octaves: int, persistence: float, lacunarity: float) -> np.ndarray:
    """Standard fBm simplex noise. snoise2 takes one cell at a time so this
    loop is unavoidable, but at typical map sizes (<= 512x512) it runs in
    well under a second."""
    grid = np.empty((height, width), dtype=np.float32)
    for y in range(height):
        for x in range(width):
            grid[y, x] = snoise2(
                x / scale,
                y / scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                base=seed % 1024,
            )
    return grid


def _ridge_noise(width: int, height: int, *, seed: int, scale: float) -> np.ndarray:
    """Inverted absolute-value noise gives mountain-like ridges. Multiplied by
    continent influence so ridges only show on land."""
    base = _fractal_noise(width, height, seed=seed, scale=scale, octaves=4, persistence=0.5, lacunarity=2.0)
    return 1.0 - np.abs(base)


def _edge_falloff(width: int, height: int, strength: float) -> np.ndarray:
    """Smooth radial mask that slightly attenuates elevation near the edges so
    continents tend to sit inside the frame. Strength=0 disables it entirely."""
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xs / max(width - 1, 1)) * 2.0 - 1.0
    ny = (ys / max(height - 1, 1)) * 2.0 - 1.0
    radial = np.sqrt(nx * nx + ny * ny)
    falloff = 1.0 - np.clip(radial - 0.6, 0.0, 1.0) * strength * 2.5
    return falloff.astype(np.float32)


def _normalize_signed(field: np.ndarray) -> np.ndarray:
    """Map an arbitrary float field to roughly [-1, 1] using percentile clipping
    so a single outlier can't squash the rest of the range."""
    low = np.percentile(field, 1.0)
    high = np.percentile(field, 99.0)
    if high - low < 1e-6:
        return np.zeros_like(field)
    centered = (field - (low + high) / 2.0) / ((high - low) / 2.0)
    return np.clip(centered, -1.2, 1.2)


def _apply_erosion(elevation: np.ndarray, config: GeographyConfig) -> np.ndarray:
    """Cheap thermal-erosion approximation: each pass smooths cells against
    their 4-neighbors weighted by slope. Real hydraulic erosion is overkill
    for this rendering; this gives us softer ridges and gentler valleys."""
    eroded = elevation.copy()
    for _ in range(config.erosion_passes):
        up = np.roll(eroded, -1, axis=0)
        down = np.roll(eroded, 1, axis=0)
        left = np.roll(eroded, -1, axis=1)
        right = np.roll(eroded, 1, axis=1)
        neighbor_avg = (up + down + left + right) * 0.25
        slope = np.abs(eroded - neighbor_avg)
        blend = np.clip(slope * 1.3, 0.05, 0.35)
        eroded = eroded * (1.0 - blend) + neighbor_avg * blend
    return eroded.astype(np.float32)


def _coast_distance_field(land_mask: np.ndarray) -> np.ndarray:
    """BFS-based distance from the nearest land/water boundary. Used to
    moderate climate: deep continental interiors are drier and more extreme."""
    height, width = land_mask.shape
    distance = np.full((height, width), -1, dtype=np.int32)
    queue: deque[tuple[int, int]] = deque()

    for y in range(height):
        for x in range(width):
            if not land_mask[y, x]:
                continue
            for ny, nx in _neighbors4(y, x, height, width):
                if not land_mask[ny, nx]:
                    distance[y, x] = 0
                    queue.append((y, x))
                    break

    while queue:
        y, x = queue.popleft()
        for ny, nx in _neighbors4(y, x, height, width):
            if not land_mask[ny, nx]:
                continue
            if distance[ny, nx] == -1:
                distance[ny, nx] = distance[y, x] + 1
                queue.append((ny, nx))

    max_distance = max(int(distance.max()), 1)
    normalized = np.where(distance >= 0, distance.astype(np.float32) / max_distance, 0.0)
    return normalized


def _build_temperature(config: GeographyConfig, elevation: np.ndarray, coast_distance: np.ndarray, sea_level: float) -> np.ndarray:
    """Latitude-driven base temperature, cooled by elevation, with a small
    noise term so isotherms aren't laser-straight."""
    height, width = elevation.shape
    ys = np.arange(height, dtype=np.float32).reshape(-1, 1)
    latitude = np.abs(ys / max(height - 1, 1) - 0.5) * 2.0
    base = 1.0 - latitude
    base = np.broadcast_to(base, (height, width)).copy()

    elevation_above_sea = np.clip(elevation - sea_level, 0.0, 1.0)
    elevation_cooling = elevation_above_sea * 0.55
    interior_swing = coast_distance * 0.15
    jitter = _fractal_noise(width, height, seed=config.seed + 4441, scale=160.0, octaves=3, persistence=0.5, lacunarity=2.0) * 0.08

    temperature = base - elevation_cooling + interior_swing + jitter
    return np.clip(temperature, 0.0, 1.0).astype(np.float32)


def _build_moisture(config: GeographyConfig, elevation: np.ndarray, coast_distance: np.ndarray, land_mask: np.ndarray, sea_level: float) -> np.ndarray:
    """Moisture decreases inland and at high elevation, with rain-shadow noise.
    Water cells get max moisture so they don't pollute downstream classification."""
    height, width = elevation.shape
    inland_dryness = coast_distance * 0.55
    rain = _fractal_noise(width, height, seed=config.seed + 7919, scale=120.0, octaves=4, persistence=0.5, lacunarity=2.0)
    rain = (rain + 1.0) * 0.5

    elevation_above_sea = np.clip(elevation - sea_level, 0.0, 1.0)
    moisture = rain - inland_dryness - elevation_above_sea * 0.25
    moisture = np.where(land_mask, moisture, 1.0)
    return np.clip(moisture, 0.0, 1.0).astype(np.float32)


def _trace_rivers(elevation: np.ndarray, land_mask: np.ndarray, moisture: np.ndarray, config: GeographyConfig, sea_level: float) -> tuple[np.ndarray, list[list[tuple[int, int]]]]:
    """Pick high, wet starting points and walk strictly downhill until we hit
    water or a sink. Rivers carry forward, accumulating other tributaries; we
    don't resolve true watersheds (overkill) but the output reads as plausible."""
    height, width = elevation.shape
    rivers = np.zeros((height, width), dtype=bool)
    paths: list[list[tuple[int, int]]] = []

    elevation_above_sea = np.clip(elevation - sea_level, 0.0, None)
    score = np.where(land_mask, elevation_above_sea * 0.6 + moisture * 0.4, -1.0)
    flat_indices = np.argsort(score, axis=None)[::-1]
    chosen = 0
    visited_sources: set[tuple[int, int]] = set()

    river_source_threshold = sea_level + 0.18
    for flat_index in flat_indices:
        if chosen >= config.river_count:
            break
        y = int(flat_index // width)
        x = int(flat_index % width)
        if not land_mask[y, x] or elevation[y, x] < river_source_threshold:
            continue
        if any(abs(y - sy) < 8 and abs(x - sx) < 8 for sy, sx in visited_sources):
            continue
        visited_sources.add((y, x))

        path = _walk_downhill(y, x, elevation, land_mask, max_steps=max(width, height))
        if len(path) < 6:
            continue
        for py, px in path:
            rivers[py, px] = True
        paths.append(path)
        chosen += 1

    return rivers, paths


def _walk_downhill(start_y: int, start_x: int, elevation: np.ndarray, land_mask: np.ndarray, *, max_steps: int) -> list[tuple[int, int]]:
    height, width = elevation.shape
    path: list[tuple[int, int]] = [(start_y, start_x)]
    y, x = start_y, start_x

    for _ in range(max_steps):
        if not land_mask[y, x]:
            break
        best = None
        best_elevation = elevation[y, x]
        for ny, nx in _neighbors8(y, x, height, width):
            if elevation[ny, nx] < best_elevation:
                best_elevation = elevation[ny, nx]
                best = (ny, nx)
        if best is None:
            break
        y, x = best
        path.append((y, x))
        if not land_mask[y, x]:
            break
    return path


_BIOME_ORDER = [
    BIOME_DEEP_OCEAN, BIOME_OCEAN, BIOME_COAST, BIOME_BEACH,
    BIOME_DESERT, BIOME_SAVANNA, BIOME_GRASSLAND, BIOME_SHRUBLAND,
    BIOME_TEMPERATE_FOREST, BIOME_RAINFOREST, BIOME_BOREAL, BIOME_TAIGA,
    BIOME_TUNDRA, BIOME_GLACIER, BIOME_HILLS, BIOME_MOUNTAIN, BIOME_PEAK,
]
_BIOME_INDEX = {name: index for index, name in enumerate(_BIOME_ORDER)}


def _classify_biomes(
    elevation: np.ndarray,
    temperature: np.ndarray,
    moisture: np.ndarray,
    land_mask: np.ndarray,
    sea_level: float,
) -> tuple[np.ndarray, list[str]]:
    """Classic Whittaker-style classification: bin by temperature x moisture,
    then override with elevation tiers for hills/mountains/peaks.

    Elevation tiers are computed as quantiles of the actual land-elevation
    distribution. That way a flat continent doesn't render as one giant beach
    and a peaky one doesn't render as one giant mountain - each map gets a
    plausible mix regardless of how the noise landed.
    """
    height, width = elevation.shape
    biome = np.full((height, width), _BIOME_INDEX[BIOME_OCEAN], dtype=np.uint16)

    deep = (~land_mask) & (elevation < sea_level - 0.35)
    coast = (~land_mask) & (elevation >= sea_level - 0.10)
    biome[deep] = _BIOME_INDEX[BIOME_DEEP_OCEAN]
    biome[coast] = _BIOME_INDEX[BIOME_COAST]

    land_values = elevation[land_mask]
    if land_values.size == 0:
        return biome, list(_BIOME_ORDER)

    # Quantile-based tier breakpoints. The numbers represent "what fraction of
    # land cells should be plains-or-lower / hills / mountains / peaks". Tighter
    # mountain/peak bands keep the famous 'white halo' visual problem at bay.
    beach_break = float(np.quantile(land_values, 0.04))
    hills_break = float(np.quantile(land_values, 0.78))
    mountain_break = float(np.quantile(land_values, 0.93))
    peak_break = float(np.quantile(land_values, 0.985))

    land_indices = np.where(land_mask)
    for y, x in zip(*land_indices):
        elevation_value = float(elevation[y, x])
        temperature_value = temperature[y, x]
        moisture_value = moisture[y, x]

        if elevation_value > peak_break:
            biome[y, x] = _BIOME_INDEX[BIOME_PEAK]
            continue
        if elevation_value > mountain_break:
            biome[y, x] = _BIOME_INDEX[BIOME_MOUNTAIN]
            continue
        if elevation_value > hills_break:
            biome[y, x] = _BIOME_INDEX[BIOME_HILLS]
            continue
        if elevation_value < beach_break:
            biome[y, x] = _BIOME_INDEX[BIOME_BEACH]
            continue

        if temperature_value < 0.18:
            biome[y, x] = _BIOME_INDEX[BIOME_GLACIER if moisture_value > 0.4 else BIOME_TUNDRA]
        elif temperature_value < 0.32:
            biome[y, x] = _BIOME_INDEX[BIOME_TAIGA if moisture_value > 0.45 else BIOME_TUNDRA]
        elif temperature_value < 0.50:
            biome[y, x] = _BIOME_INDEX[BIOME_BOREAL if moisture_value > 0.4 else BIOME_SHRUBLAND]
        elif temperature_value < 0.72:
            if moisture_value < 0.30:
                biome[y, x] = _BIOME_INDEX[BIOME_SHRUBLAND]
            elif moisture_value < 0.55:
                biome[y, x] = _BIOME_INDEX[BIOME_GRASSLAND]
            else:
                biome[y, x] = _BIOME_INDEX[BIOME_TEMPERATE_FOREST]
        else:
            if moisture_value < 0.25:
                biome[y, x] = _BIOME_INDEX[BIOME_DESERT]
            elif moisture_value < 0.50:
                biome[y, x] = _BIOME_INDEX[BIOME_SAVANNA]
            else:
                biome[y, x] = _BIOME_INDEX[BIOME_RAINFOREST]

    return biome, list(_BIOME_ORDER)


def _coastline_mask(land_mask: np.ndarray) -> np.ndarray:
    height, width = land_mask.shape
    coastline = np.zeros_like(land_mask)
    for y in range(height):
        for x in range(width):
            if not land_mask[y, x]:
                continue
            for ny, nx in _neighbors4(y, x, height, width):
                if not land_mask[ny, nx]:
                    coastline[y, x] = True
                    break
    return coastline


def _label_landmasses(land_mask: np.ndarray, config: GeographyConfig) -> tuple[np.ndarray, list[LandmassInfo]]:
    """Connected-component labeling on the land mask. Anything large enough is
    flagged as a continent; smaller blobs are islands. The interactive runtime
    uses these so the player can jump between continents."""
    height, width = land_mask.shape
    labels = np.full((height, width), -1, dtype=np.int32)
    next_id = 0
    landmasses: list[LandmassInfo] = []
    continent_threshold = max(120, (width * height) // 80)

    for y in range(height):
        for x in range(width):
            if not land_mask[y, x] or labels[y, x] != -1:
                continue
            cells = _flood_fill(y, x, land_mask, labels, next_id)
            if not cells:
                continue
            landmasses.append(_summarize_landmass(next_id, cells, continent_threshold))
            next_id += 1
    return labels, landmasses


def _flood_fill(start_y: int, start_x: int, land_mask: np.ndarray, labels: np.ndarray, label: int) -> list[tuple[int, int]]:
    height, width = land_mask.shape
    queue: deque[tuple[int, int]] = deque([(start_y, start_x)])
    cells: list[tuple[int, int]] = []
    labels[start_y, start_x] = label

    while queue:
        y, x = queue.popleft()
        cells.append((y, x))
        for ny, nx in _neighbors4(y, x, height, width):
            if land_mask[ny, nx] and labels[ny, nx] == -1:
                labels[ny, nx] = label
                queue.append((ny, nx))
    return cells


def _summarize_landmass(label: int, cells: list[tuple[int, int]], continent_threshold: int) -> LandmassInfo:
    ys = [cell[0] for cell in cells]
    xs = [cell[1] for cell in cells]
    return LandmassInfo(
        landmass_id=label,
        cell_count=len(cells),
        centroid_x=sum(xs) / len(xs),
        centroid_y=sum(ys) / len(ys),
        bounds=(min(xs), min(ys), max(xs), max(ys)),
        is_continent=len(cells) >= continent_threshold,
    )


def _neighbors4(y: int, x: int, height: int, width: int) -> Iterable[tuple[int, int]]:
    if y > 0:
        yield (y - 1, x)
    if y + 1 < height:
        yield (y + 1, x)
    if x > 0:
        yield (y, x - 1)
    if x + 1 < width:
        yield (y, x + 1)


def _neighbors8(y: int, x: int, height: int, width: int) -> Iterable[tuple[int, int]]:
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                yield (ny, nx)

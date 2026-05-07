"""Province subdivision for the procedural world.

Provinces are the unit the player clicks on in the interactive map. Each
province owns a contiguous patch of cells on a single landmass, has a
dominant biome, an elevation profile, and a name slot for downstream systems
(civilizations, religions, cultures) to bind to.

The subdivision uses a Lloyd-relaxed Voronoi approach over land cells:
    1. Scatter seeds proportional to landmass area
    2. Assign each land cell to its nearest seed (distance on land only)
    3. Relax seed positions toward their cell centroids (one or two passes)
    4. Reassign cells

This gives reasonably equal-area, blob-shaped provinces with stable IDs
across re-renders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque

import numpy as np

from fantasy_engine.world.geography import GeographyResult


@dataclass(slots=True)
class Province:
    province_id: int
    landmass_id: int
    cell_count: int
    centroid_x: float
    centroid_y: float
    bounds: tuple[int, int, int, int]
    dominant_biome: str
    biome_mix: dict[str, float]
    mean_elevation: float
    mean_temperature: float
    mean_moisture: float
    has_river: bool
    is_coastal: bool
    name: str = ""
    neighbor_ids: tuple[int, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class ProvinceMap:
    province_id_grid: np.ndarray
    provinces: list[Province]
    target_cells_per_province: int

    def province_at(self, x: int, y: int) -> Province | None:
        province_id = int(self.province_id_grid[y, x])
        if province_id < 0:
            return None
        return self.provinces[province_id]


def build_province_map(
    geography: GeographyResult,
    *,
    target_cells_per_province: int = 220,
    relaxation_passes: int = 2,
) -> ProvinceMap:
    """Subdivide every continent and large island into provinces.

    target_cells_per_province controls granularity. The default produces a few
    dozen provinces on a 192x128 map and several hundred on a 512x320 map,
    which is the right ballpark for CK3-style clickability without becoming
    overwhelming.
    """
    height, width = geography.elevation.shape
    province_id_grid = np.full((height, width), -1, dtype=np.int32)
    seeds: list[tuple[float, float, int]] = []

    rng = np.random.default_rng(geography.config.seed + 17)

    for landmass in geography.landmasses:
        cells = _landmass_cells(geography, landmass.landmass_id)
        if not cells:
            continue
        seed_count = max(1, len(cells) // target_cells_per_province)
        seed_indices = rng.choice(len(cells), size=min(seed_count, len(cells)), replace=False)
        for index in seed_indices:
            y, x = cells[int(index)]
            seeds.append((float(x), float(y), landmass.landmass_id))

    if not seeds:
        return ProvinceMap(province_id_grid=province_id_grid, provinces=[], target_cells_per_province=target_cells_per_province)

    for relaxation_pass in range(relaxation_passes + 1):
        province_id_grid = _assign_cells_to_nearest_seed(geography, seeds)
        if relaxation_pass == relaxation_passes:
            break
        seeds = _recompute_seed_centroids(province_id_grid, seeds)

    provinces = _summarize_provinces(geography, province_id_grid, seeds)
    _attach_neighbors(province_id_grid, provinces)
    return ProvinceMap(province_id_grid=province_id_grid, provinces=provinces, target_cells_per_province=target_cells_per_province)


def _landmass_cells(geography: GeographyResult, landmass_id: int) -> list[tuple[int, int]]:
    ys, xs = np.where(geography.landmass_id == landmass_id)
    return list(zip(ys.tolist(), xs.tolist()))


def _assign_cells_to_nearest_seed(geography: GeographyResult, seeds: list[tuple[float, float, int]]) -> np.ndarray:
    """Multi-source BFS over land cells. Seeds expand outward simultaneously,
    and each cell takes the seed that reached it first. This yields true
    distance-on-land rather than Euclidean distance through water, which is
    what we want - provinces shouldn't bleed across narrow channels."""
    height, width = geography.elevation.shape
    province_id_grid = np.full((height, width), -1, dtype=np.int32)
    queue: deque[tuple[int, int, int]] = deque()

    for province_id, (seed_x, seed_y, _landmass_id) in enumerate(seeds):
        sy, sx = int(round(seed_y)), int(round(seed_x))
        sy = max(0, min(height - 1, sy))
        sx = max(0, min(width - 1, sx))
        if not geography.land_mask[sy, sx]:
            sy, sx = _find_nearest_land(geography.land_mask, sy, sx)
            if sy is None:
                continue
        province_id_grid[sy, sx] = province_id
        queue.append((sy, sx, province_id))

    while queue:
        y, x, province_id = queue.popleft()
        for ny, nx in _neighbors4(y, x, height, width):
            if not geography.land_mask[ny, nx]:
                continue
            if province_id_grid[ny, nx] != -1:
                continue
            if geography.landmass_id[ny, nx] != geography.landmass_id[y, x]:
                continue
            province_id_grid[ny, nx] = province_id
            queue.append((ny, nx, province_id))
    return province_id_grid


def _recompute_seed_centroids(province_id_grid: np.ndarray, seeds: list[tuple[float, float, int]]) -> list[tuple[float, float, int]]:
    new_seeds: list[tuple[float, float, int]] = []
    for province_id, (seed_x, seed_y, landmass_id) in enumerate(seeds):
        ys, xs = np.where(province_id_grid == province_id)
        if len(xs) == 0:
            new_seeds.append((seed_x, seed_y, landmass_id))
            continue
        new_seeds.append((float(xs.mean()), float(ys.mean()), landmass_id))
    return new_seeds


def _find_nearest_land(land_mask: np.ndarray, start_y: int, start_x: int) -> tuple[int | None, int | None]:
    """Spiral search for the nearest land cell. Used when a seed lands on water
    after Lloyd relaxation pulls its centroid into a coastal bay."""
    height, width = land_mask.shape
    for radius in range(1, max(height, width)):
        y_min, y_max = max(0, start_y - radius), min(height, start_y + radius + 1)
        x_min, x_max = max(0, start_x - radius), min(width, start_x + radius + 1)
        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                if abs(y - start_y) != radius and abs(x - start_x) != radius:
                    continue
                if land_mask[y, x]:
                    return y, x
    return None, None


def _summarize_provinces(geography: GeographyResult, province_id_grid: np.ndarray, seeds: list[tuple[float, float, int]]) -> list[Province]:
    provinces: list[Province] = []
    for province_id in range(len(seeds)):
        ys, xs = np.where(province_id_grid == province_id)
        if len(xs) == 0:
            continue
        biome_ids, counts = np.unique(geography.biome[ys, xs], return_counts=True)
        biome_mix = {geography.biome_names[int(biome_id)]: int(count) for biome_id, count in zip(biome_ids, counts)}
        total = sum(biome_mix.values()) or 1
        biome_share = {name: count / total for name, count in biome_mix.items()}
        dominant_biome = max(biome_share, key=biome_share.get)

        provinces.append(
            Province(
                province_id=province_id,
                landmass_id=int(geography.landmass_id[ys[0], xs[0]]),
                cell_count=len(xs),
                centroid_x=float(xs.mean()),
                centroid_y=float(ys.mean()),
                bounds=(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                dominant_biome=dominant_biome,
                biome_mix=biome_share,
                mean_elevation=float(geography.elevation[ys, xs].mean()),
                mean_temperature=float(geography.temperature[ys, xs].mean()),
                mean_moisture=float(geography.moisture[ys, xs].mean()),
                has_river=bool(geography.rivers[ys, xs].any()),
                is_coastal=bool(geography.coastline[ys, xs].any()),
            )
        )
    return provinces


def _attach_neighbors(province_id_grid: np.ndarray, provinces: list[Province]) -> None:
    """Find shared borders between provinces. Used both by the cartographer
    and by future simulation systems that need adjacency."""
    height, width = province_id_grid.shape
    neighbor_sets: dict[int, set[int]] = {province.province_id: set() for province in provinces}

    for y in range(height):
        for x in range(width):
            province_id = province_id_grid[y, x]
            if province_id < 0:
                continue
            for ny, nx in _neighbors4(y, x, height, width):
                neighbor_id = province_id_grid[ny, nx]
                if neighbor_id < 0 or neighbor_id == province_id:
                    continue
                neighbor_sets[province_id].add(int(neighbor_id))

    for province in provinces:
        province.neighbor_ids = tuple(sorted(neighbor_sets.get(province.province_id, set())))


def _neighbors4(y: int, x: int, height: int, width: int):
    if y > 0:
        yield (y - 1, x)
    if y + 1 < height:
        yield (y + 1, x)
    if x > 0:
        yield (y, x - 1)
    if x + 1 < width:
        yield (y, x + 1)

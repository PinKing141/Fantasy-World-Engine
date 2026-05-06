from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import matplotlib
from noise import snoise2
import numpy as np

matplotlib.use("Agg")

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as PolygonPatch
from shapely.geometry import Point, Polygon

from fantasy_engine.core.engine import SeasonStepResult
from fantasy_engine.world.territories import build_territory_polygons


@dataclass(frozen=True, slots=True)
class MapCivilizationView:
    name: str
    region_name: str
    terrain_name: str
    culture_id: str
    map_x: int
    map_y: int


@dataclass(frozen=True, slots=True)
class MapRouteView:
    civilization_a: str
    civilization_b: str
    state: str
    path_points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class MapTerritoryView:
    owner_name: str
    polygon_points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class MapTerrainCellView:
    x: float
    y: float
    width: float
    height: float
    terrain_kind: str
    surface_value: float
    height_value: float
    moisture_value: float
    relief_value: float


@dataclass(frozen=True, slots=True)
class MapCoastlineSegmentView:
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True, slots=True)
class WorldMapView:
    year: int
    season: str
    civilizations: tuple[MapCivilizationView, ...]
    routes: tuple[MapRouteView, ...]
    territories: tuple[MapTerritoryView, ...]
    terrain_cells: tuple[MapTerrainCellView, ...]
    coastline_segments: tuple[MapCoastlineSegmentView, ...]


_PALETTE = (
    "#276FBF",
    "#B85C38",
    "#4F7A28",
    "#8A5082",
    "#9C6B30",
    "#4A6C6F",
)

_ROUTE_STYLES = {
    "open": {"color": "#D7C37A", "linestyle": "-", "linewidth": 2.4, "alpha": 0.88},
    "contested": {"color": "#D08B2D", "linestyle": "--", "linewidth": 2.8, "alpha": 0.95},
    "severed": {"color": "#B43C2E", "linestyle": ":", "linewidth": 3.0, "alpha": 0.98},
}
_TERRAIN_COLORS = {
    "deep_water": "#14356A",
    "shallow_water": "#3D78B9",
    "fertile_land": "#5C9442",
    "poor_land": "#8C8A63",
    "hill": "#7A8750",
    "highland": "#776551",
    "mountain": "#DCE1E6",
}
_DEEP_WATER_THRESHOLD = -0.02
_LAND_THRESHOLD = 0.18


def build_world_map_view(step_result: SeasonStepResult) -> WorldMapView:
    civilizations = tuple(
        MapCivilizationView(
            name=civilization.name,
            region_name=civilization.region_name,
            terrain_name=civilization.terrain_name,
            culture_id=civilization.culture_id,
            map_x=civilization.map_x,
            map_y=civilization.map_y,
        )
        for civilization in sorted(step_result.civilization_snapshots, key=lambda item: item.name)
    )
    civilization_lookup = {civilization.name: civilization for civilization in civilizations}
    routes = tuple(
        MapRouteView(
            civilization_a=route.civilization_a,
            civilization_b=route.civilization_b,
            state=route.state,
            path_points=_build_route_path(route.civilization_a, route.civilization_b, civilization_lookup),
        )
        for route in sorted(step_result.active_routes, key=lambda item: (item.civilization_a, item.civilization_b))
    )
    territories = tuple(
        MapTerritoryView(owner_name=territory.owner_name, polygon_points=territory.polygon_points)
        for territory in build_territory_polygons(
            [(civilization.name, civilization.map_x, civilization.map_y) for civilization in civilizations]
        )
    )
    terrain_cells, coastline_segments = _build_terrain_surface(civilizations, territories)
    return WorldMapView(
        year=step_result.year,
        season=step_result.season,
        civilizations=civilizations,
        routes=routes,
        territories=territories,
        terrain_cells=terrain_cells,
        coastline_segments=coastline_segments,
    )


def export_world_map(step_result: SeasonStepResult, output_path: str | Path) -> WorldMapView:
    map_view = build_world_map_view(step_result)
    figure = Figure(figsize=(9.5, 6.5), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(1, 1, 1)
    axes.set_facecolor(_TERRAIN_COLORS["deep_water"])

    _render_terrain_surface(axes, map_view)

    civilization_lookup = {civilization.name: civilization for civilization in map_view.civilizations}
    territory_lookup = {territory.owner_name: territory for territory in map_view.territories}
    for index, civilization in enumerate(map_view.civilizations):
        territory = territory_lookup.get(civilization.name)
        if territory is None:
            continue
        color = _PALETTE[index % len(_PALETTE)]
        axes.add_patch(
            PolygonPatch(
                territory.polygon_points,
                closed=True,
                facecolor=color,
                edgecolor="#241E19",
                linewidth=2.0,
                alpha=0.15,
                zorder=1,
            )
        )

    for route in map_view.routes:
        style = _ROUTE_STYLES.get(route.state, _ROUTE_STYLES["open"])
        route_xs = [point[0] for point in route.path_points]
        route_ys = [point[1] for point in route.path_points]
        axes.plot(route_xs, route_ys, zorder=3, **style)

    for index, civilization in enumerate(map_view.civilizations):
        color = _PALETTE[index % len(_PALETTE)]
        axes.scatter(
            civilization.map_x,
            civilization.map_y,
            s=300,
            facecolors="none",
            edgecolors="#F7F1E1",
            linewidths=2.2,
            zorder=5,
        )
        axes.scatter(
            civilization.map_x,
            civilization.map_y,
            s=150,
            color=color,
            edgecolors="#1E1B18",
            linewidths=1.3,
            zorder=6,
        )
        axes.text(
            civilization.map_x + 0.18,
            civilization.map_y + 0.26,
            civilization.name,
            fontsize=10,
            fontweight="bold",
            color="#1E1B18",
            va="bottom",
            zorder=7,
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "#F5EFD9", "edgecolor": "none", "alpha": 0.72},
        )
        axes.text(
            civilization.map_x + 0.18,
            civilization.map_y + 0.04,
            civilization.region_name,
            fontsize=7.8,
            color="#2A2925",
            va="bottom",
            zorder=7,
        )
        axes.text(
            civilization.map_x,
            civilization.map_y - 0.36,
            civilization.terrain_name,
            fontsize=6.6,
            color="#61584C",
            ha="center",
            va="top",
            zorder=7,
        )

    x_values = [civilization.map_x for civilization in map_view.civilizations]
    y_values = [civilization.map_y for civilization in map_view.civilizations]
    if x_values and y_values:
        axes.set_xlim(min(x_values) - 1.2, max(x_values) + 1.8)
        axes.set_ylim(min(y_values) - 1.2, max(y_values) + 1.4)

    axes.set_aspect("equal", adjustable="box")
    axes.axis("off")
    axes.set_title(f"Fantasy Engine World Map | Year {map_view.year} {map_view.season.title()}", fontsize=14, color="#1E1B18")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_file, dpi=150, facecolor=figure.get_facecolor())
    return map_view


def _build_terrain_surface(
    civilizations: tuple[MapCivilizationView, ...],
    territories: tuple[MapTerritoryView, ...],
) -> tuple[tuple[MapTerrainCellView, ...], tuple[MapCoastlineSegmentView, ...]]:
    if not civilizations or not territories:
        return (), ()

    territory_polygons = {territory.owner_name: Polygon(territory.polygon_points) for territory in territories}
    min_x, min_y, max_x, max_y = _surface_bounds(territories)
    width = max_x - min_x
    height = max_y - min_y
    columns = 56
    rows = max(28, int(round(columns * (height / max(width, 0.1)))))
    cell_width = width / columns
    cell_height = height / rows
    surface_seed = _surface_seed(civilizations)
    influence_radii = _influence_radii(civilizations, territory_polygons)

    cells_by_row: list[list[MapTerrainCellView]] = []
    terrain_cells: list[MapTerrainCellView] = []
    for row in range(rows):
        row_cells: list[MapTerrainCellView] = []
        for column in range(columns):
            center_x = min_x + (column + 0.5) * cell_width
            center_y = min_y + (row + 0.5) * cell_height
            land_strength = _land_strength(
                center_x,
                center_y,
                civilizations,
                territory_polygons,
                influence_radii,
                surface_seed,
            )
            height_value = _height_value(center_x, center_y, surface_seed)
            moisture_value = _moisture_value(center_x, center_y, surface_seed)
            relief_value = _relief_value(center_x, center_y, surface_seed)
            terrain_kind = _terrain_kind(
                land_strength,
                height_value,
                moisture_value,
                relief_value,
            )
            cell = MapTerrainCellView(
                x=round(center_x, 4),
                y=round(center_y, 4),
                width=round(cell_width, 4),
                height=round(cell_height, 4),
                terrain_kind=terrain_kind,
                surface_value=round(land_strength, 4),
                height_value=round(height_value, 4),
                moisture_value=round(moisture_value, 4),
                relief_value=round(relief_value, 4),
            )
            row_cells.append(cell)
            terrain_cells.append(cell)
        cells_by_row.append(row_cells)

    coastline_segments = _coastline_segments(cells_by_row)
    return tuple(terrain_cells), coastline_segments


def _surface_bounds(territories: tuple[MapTerritoryView, ...]) -> tuple[float, float, float, float]:
    x_values = [point[0] for territory in territories for point in territory.polygon_points]
    y_values = [point[1] for territory in territories for point in territory.polygon_points]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _surface_seed(civilizations: tuple[MapCivilizationView, ...]) -> int:
    seed = 0
    for index, civilization in enumerate(civilizations, start=1):
        name_weight = sum(ord(character) for character in civilization.name)
        seed += index * (name_weight + civilization.map_x * 101 + civilization.map_y * 53)
    return seed


def _influence_radii(
    civilizations: tuple[MapCivilizationView, ...],
    territory_polygons: dict[str, Polygon],
) -> dict[str, float]:
    radii: dict[str, float] = {}
    for civilization in civilizations:
        polygon = territory_polygons[civilization.name]
        radius = max(1.1, math.sqrt(max(polygon.area, 0.1)) * 0.72)
        radii[civilization.name] = radius
    return radii


def _land_strength(
    center_x: float,
    center_y: float,
    civilizations: tuple[MapCivilizationView, ...],
    territory_polygons: dict[str, Polygon],
    influence_radii: dict[str, float],
    surface_seed: int,
) -> float:
    point = Point(center_x, center_y)
    influence_total = 0.0
    inside_any_territory = False
    for civilization in civilizations:
        polygon = territory_polygons[civilization.name]
        if polygon.covers(point):
            inside_any_territory = True
        distance_to_center = math.dist((center_x, center_y), (civilization.map_x, civilization.map_y))
        radius = influence_radii[civilization.name]
        influence = max(0.0, 1.0 - distance_to_center / radius)
        influence_total += influence * influence

    macro_noise = snoise2(
        (center_x + surface_seed * 0.0041) / 3.8,
        (center_y - surface_seed * 0.0033) / 3.8,
        octaves=2,
        persistence=0.5,
        lacunarity=2.0,
        base=surface_seed + 41,
    )
    coast_noise = snoise2(
        (center_x - surface_seed * 0.0017) / 1.4,
        (center_y + surface_seed * 0.0021) / 1.4,
        octaves=3,
        persistence=0.55,
        lacunarity=2.0,
        base=surface_seed + 97,
    )
    return influence_total + macro_noise * 0.34 + coast_noise * 0.22 + (0.05 if inside_any_territory else -0.2)


def _terrain_kind(land_strength: float, height_value: float, moisture_value: float, relief_value: float) -> str:
    if land_strength < _DEEP_WATER_THRESHOLD:
        return "deep_water"
    if land_strength < _LAND_THRESHOLD:
        return "shallow_water"

    if relief_value > 0.66 or height_value > 0.62:
        return "mountain"
    if relief_value > 0.46 or height_value > 0.4:
        return "highland"
    if relief_value > 0.24:
        return "hill"
    if moisture_value > 0.08:
        return "fertile_land"
    return "poor_land"


def _height_value(center_x: float, center_y: float, surface_seed: int) -> float:
    broad_ridge = snoise2(
        (center_x + surface_seed * 0.0021) / 4.6,
        (center_y - surface_seed * 0.0016) / 3.9,
        octaves=2,
        persistence=0.55,
        lacunarity=2.0,
        base=surface_seed + 211,
    )
    ridge_strength = 1.0 - abs(broad_ridge)
    continental_shape = snoise2(
        (center_x - surface_seed * 0.0013) / 6.2,
        (center_y + surface_seed * 0.0018) / 6.2,
        octaves=2,
        persistence=0.5,
        lacunarity=2.0,
        base=surface_seed + 257,
    )
    return ridge_strength * 0.62 + continental_shape * 0.38


def _relief_value(center_x: float, center_y: float, surface_seed: int) -> float:
    return snoise2(
        (center_x + surface_seed * 0.0019) / 1.8,
        (center_y - surface_seed * 0.0011) / 1.8,
        octaves=3,
        persistence=0.55,
        lacunarity=2.0,
        base=surface_seed + 131,
    )


def _moisture_value(center_x: float, center_y: float, surface_seed: int) -> float:
    return snoise2(
        (center_x - surface_seed * 0.0013) / 2.6,
        (center_y + surface_seed * 0.0017) / 2.6,
        octaves=2,
        persistence=0.5,
        lacunarity=2.0,
        base=surface_seed + 173,
    )


def _build_route_path(
    civilization_a: str,
    civilization_b: str,
    civilization_lookup: dict[str, MapCivilizationView],
) -> tuple[tuple[float, float], ...]:
    origin = civilization_lookup[civilization_a]
    destination = civilization_lookup[civilization_b]
    start = (float(origin.map_x), float(origin.map_y))
    end = (float(destination.map_x), float(destination.map_y))
    mid_x = (start[0] + end[0]) / 2.0
    mid_y = (start[1] + end[1]) / 2.0
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    distance = math.dist(start, end)
    if distance == 0:
        return (start, end)

    normal_x = -delta_y / distance
    normal_y = delta_x / distance
    pair_weight = sum(ord(character) for character in f"{civilization_a}:{civilization_b}")
    bend_direction = -1.0 if pair_weight % 2 else 1.0
    bend_strength = min(0.55, 0.12 * distance)
    control = (
        round(mid_x + normal_x * bend_strength * bend_direction, 4),
        round(mid_y + normal_y * bend_strength * bend_direction, 4),
    )
    return (start, control, end)


def _coastline_segments(cells_by_row: list[list[MapTerrainCellView]]) -> tuple[MapCoastlineSegmentView, ...]:
    if not cells_by_row:
        return ()

    segments: list[MapCoastlineSegmentView] = []
    row_count = len(cells_by_row)
    column_count = len(cells_by_row[0])
    for row in range(row_count):
        for column in range(column_count):
            cell = cells_by_row[row][column]
            if _is_water_kind(cell.terrain_kind):
                continue
            left = cells_by_row[row][column - 1] if column > 0 else None
            right = cells_by_row[row][column + 1] if column + 1 < column_count else None
            above = cells_by_row[row - 1][column] if row > 0 else None
            below = cells_by_row[row + 1][column] if row + 1 < row_count else None

            if left is None or _is_water_kind(left.terrain_kind):
                segments.append(
                    MapCoastlineSegmentView(
                        start=(round(cell.x - cell.width / 2.0, 4), round(cell.y - cell.height / 2.0, 4)),
                        end=(round(cell.x - cell.width / 2.0, 4), round(cell.y + cell.height / 2.0, 4)),
                    )
                )
            if right is None or _is_water_kind(right.terrain_kind):
                segments.append(
                    MapCoastlineSegmentView(
                        start=(round(cell.x + cell.width / 2.0, 4), round(cell.y - cell.height / 2.0, 4)),
                        end=(round(cell.x + cell.width / 2.0, 4), round(cell.y + cell.height / 2.0, 4)),
                    )
                )
            if above is None or _is_water_kind(above.terrain_kind):
                segments.append(
                    MapCoastlineSegmentView(
                        start=(round(cell.x - cell.width / 2.0, 4), round(cell.y - cell.height / 2.0, 4)),
                        end=(round(cell.x + cell.width / 2.0, 4), round(cell.y - cell.height / 2.0, 4)),
                    )
                )
            if below is None or _is_water_kind(below.terrain_kind):
                segments.append(
                    MapCoastlineSegmentView(
                        start=(round(cell.x - cell.width / 2.0, 4), round(cell.y + cell.height / 2.0, 4)),
                        end=(round(cell.x + cell.width / 2.0, 4), round(cell.y + cell.height / 2.0, 4)),
                    )
                )
    return tuple(segments)


def _is_water_kind(terrain_kind: str) -> bool:
    return terrain_kind in {"deep_water", "shallow_water"}


def _render_terrain_surface(axes, map_view: WorldMapView) -> None:
    if not map_view.terrain_cells:
        return

    x_values = sorted({cell.x for cell in map_view.terrain_cells})
    y_values = sorted({cell.y for cell in map_view.terrain_cells})
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(y_values)}

    surface = np.zeros((len(y_values), len(x_values)))
    relief = np.zeros_like(surface)
    moisture = np.zeros_like(surface)
    height = np.zeros_like(surface)
    for cell in map_view.terrain_cells:
        row = y_index[cell.y]
        column = x_index[cell.x]
        surface[row, column] = cell.surface_value
        relief[row, column] = cell.relief_value
        moisture[row, column] = cell.moisture_value
        height[row, column] = cell.height_value

    x_grid, y_grid = np.meshgrid(x_values, y_values)
    land_mask = surface >= _LAND_THRESHOLD

    axes.contourf(
        x_grid,
        y_grid,
        surface,
        levels=[surface.min() - 0.2, _DEEP_WATER_THRESHOLD, _LAND_THRESHOLD, surface.max() + 0.2],
        colors=[_TERRAIN_COLORS["deep_water"], _TERRAIN_COLORS["shallow_water"], _TERRAIN_COLORS["poor_land"]],
        antialiased=True,
        zorder=-4,
    )

    fertile_overlay = np.ma.masked_where(~land_mask | (moisture < 0.08), moisture)
    if fertile_overlay.count() > 0:
        axes.contourf(
            x_grid,
            y_grid,
            fertile_overlay,
            levels=[0.08, fertile_overlay.max() + 0.01],
            colors=[_TERRAIN_COLORS["fertile_land"]],
            alpha=0.92,
            antialiased=True,
            zorder=-3,
        )

    hill_overlay = np.ma.masked_where(~land_mask | ((relief < 0.2) & (height < 0.3)), np.maximum(relief, height))
    if hill_overlay.count() > 0:
        axes.contourf(
            x_grid,
            y_grid,
            hill_overlay,
            levels=[0.2, 0.4, 0.6, hill_overlay.max() + 0.01],
            colors=[_TERRAIN_COLORS["hill"], _TERRAIN_COLORS["highland"], _TERRAIN_COLORS["mountain"]],
            alpha=0.96,
            antialiased=True,
            zorder=-2,
        )

    axes.contour(
        x_grid,
        y_grid,
        surface,
        levels=[_LAND_THRESHOLD],
        colors=["#F1DFC0"],
        linewidths=1.6,
        alpha=0.95,
        zorder=-1,
    )
    axes.contour(
        x_grid,
        y_grid,
        surface,
        levels=[_DEEP_WATER_THRESHOLD],
        colors=["#79A9D4"],
        linewidths=0.8,
        alpha=0.45,
        zorder=-1,
    )
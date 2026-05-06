from __future__ import annotations

from dataclasses import dataclass

from shapely import voronoi_polygons
from shapely.geometry import MultiPoint, Polygon, box


@dataclass(frozen=True, slots=True)
class TerritoryPolygon:
    owner_name: str
    polygon_points: tuple[tuple[float, float], ...]


def build_territory_polygons(
    centers: list[tuple[str, float, float]],
    *,
    x_padding: float = 1.2,
    y_padding: float = 1.2,
) -> tuple[TerritoryPolygon, ...]:
    if not centers:
        return ()

    if len(centers) == 1:
        owner_name, center_x, center_y = centers[0]
        territory_bounds = box(center_x - x_padding, center_y - y_padding, center_x + x_padding, center_y + y_padding)
        return (TerritoryPolygon(owner_name=owner_name, polygon_points=_polygon_points(territory_bounds)),)

    x_values = [center_x for _, center_x, _ in centers]
    y_values = [center_y for _, _, center_y in centers]
    territory_bounds = box(
        min(x_values) - x_padding,
        min(y_values) - y_padding,
        max(x_values) + x_padding,
        max(y_values) + y_padding,
    )
    point_geometry = MultiPoint([(center_x, center_y) for _, center_x, center_y in centers])
    raw_cells = voronoi_polygons(point_geometry, extend_to=territory_bounds, ordered=True)

    polygons: list[TerritoryPolygon] = []
    for (owner_name, center_x, center_y), raw_cell in zip(centers, raw_cells.geoms, strict=True):
        clipped_cell = raw_cell.intersection(territory_bounds)
        if clipped_cell.is_empty:
            continue
        resolved_polygon = _resolve_polygon(clipped_cell)
        if resolved_polygon is None:
            continue
        if not resolved_polygon.covers(MultiPoint([(center_x, center_y)])):
            resolved_polygon = resolved_polygon.buffer(0)
        polygons.append(
            TerritoryPolygon(
                owner_name=owner_name,
                polygon_points=_polygon_points(resolved_polygon),
            )
        )
    return tuple(polygons)


def _resolve_polygon(geometry) -> Polygon | None:
    if isinstance(geometry, Polygon):
        return geometry
    if hasattr(geometry, "geoms"):
        polygons = [candidate for candidate in geometry.geoms if isinstance(candidate, Polygon)]
        if polygons:
            return max(polygons, key=lambda candidate: candidate.area)
    return None


def _polygon_points(polygon: Polygon) -> tuple[tuple[float, float], ...]:
    coordinates = tuple((round(x, 4), round(y, 4)) for x, y in polygon.exterior.coords[:-1])
    return coordinates
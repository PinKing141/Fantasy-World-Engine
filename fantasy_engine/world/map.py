from __future__ import annotations

from dataclasses import dataclass
import math

from noise import snoise2

from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.world.routes import RouteTerrain, TradeRoute


@dataclass(slots=True)
class RegionTerrain:
    name: str
    arable_land: float
    water_retention: float
    travel_difficulty: float
    exposure: float
    defense: float


@dataclass(slots=True)
class Region:
    name: str
    fertility: float
    rainfall: float
    winter_severity: float
    route_cost: float
    terrain: RegionTerrain
    x: int
    y: int

    @property
    def harvest_potential(self) -> float:
        return self.fertility * self.terrain.arable_land * self.terrain.water_retention


class WorldMap:
    TERRAIN_BLUEPRINTS = {
        "river_vale": ("River Vale", 1.18, 1.12, 0.92, 0.90, 0.96),
        "wind_steppe": ("Wind Steppe", 0.92, 0.86, 1.08, 1.10, 0.98),
        "stone_basin": ("Stone Basin", 1.08, 1.02, 1.06, 0.96, 1.08),
        "storm_coast": ("Storm Coast", 0.94, 1.00, 1.12, 1.18, 1.02),
        "frozen_march": ("Frozen March", 0.78, 0.94, 1.24, 1.16, 1.10),
        "sun_baked_flats": ("Sun-Baked Flats", 0.76, 0.82, 1.18, 1.12, 0.94),
    }
    GRID_WIDTH = 9
    GRID_HEIGHT = 6
    REGION_BLUEPRINTS = (
        ("Greenreach Vale", 1.35, 1.15, 0.80, 1.10, "river_vale", 2, 4),
        ("Ashen Steppe", 0.88, 0.75, 1.05, 1.65, "wind_steppe", 6, 2),
        ("Ironroot Basin", 1.10, 0.95, 1.10, 1.35, "stone_basin", 4, 5),
        ("Stormcoast March", 0.95, 1.20, 0.92, 1.50, "storm_coast", 1, 1),
        ("Frostmere", 0.82, 0.90, 1.35, 1.85, "frozen_march", 8, 0),
        ("Sunscar Flats", 0.72, 0.68, 0.88, 1.70, "sun_baked_flats", 8, 5),
    )

    @classmethod
    def generate(cls, rng: SeededRNG, count: int) -> list[Region]:
        map_seed = rng.randint(10_000, 999_999)
        blueprints = cls._select_blueprints(map_seed, count)
        regions: list[Region] = []
        used_positions: set[tuple[int, int]] = set()
        for index, (name, fertility, rainfall, winter_severity, route_cost, terrain_key, _, _) in enumerate(blueprints):
            x, y = cls._claim_position(map_seed, index, used_positions)
            moisture = cls._noise_value(map_seed, x, y, channel=17 + index)
            elevation = cls._noise_value(map_seed, x, y, channel=43 + index)
            temperature = cls._noise_value(map_seed, x, y, channel=79 + index)
            resolved_terrain_key = cls._terrain_key_for(
                preferred_terrain=terrain_key,
                moisture=moisture,
                elevation=elevation,
                temperature=temperature,
            )
            regions.append(
                Region(
                    name=name,
                    fertility=cls._clamp(fertility + moisture * 0.14 - elevation * 0.08, 0.65, 1.45),
                    rainfall=cls._clamp(rainfall + moisture * 0.18, 0.55, 1.35),
                    winter_severity=cls._clamp(winter_severity - temperature * 0.16 + elevation * 0.05, 0.75, 1.55),
                    route_cost=cls._clamp(route_cost + elevation * 0.16 + abs(moisture) * 0.05, 0.95, 1.95),
                    terrain=cls._region_terrain(resolved_terrain_key),
                    x=x,
                    y=y,
                )
            )
        return regions

    @classmethod
    def build_trade_routes(cls, regions: list[Region], rng: SeededRNG) -> dict[tuple[str, str], TradeRoute]:
        routes: dict[tuple[str, str], TradeRoute] = {}
        for region in regions:
            neighbors = sorted(
                (other for other in regions if other is not region),
                key=lambda other: cls._route_distance(region, other),
            )
            for neighbor in neighbors[:2]:
                cls._add_route(routes, region, neighbor, rng)

        if len(regions) >= 2:
            cls._add_route(routes, regions[0], regions[1], rng)
        return routes

    @classmethod
    def _add_route(
        cls,
        routes: dict[tuple[str, str], TradeRoute],
        region: Region,
        neighbor: Region,
        rng: SeededRNG,
    ) -> None:
        key = tuple(sorted((region.name, neighbor.name)))
        if key in routes:
            return
        distance = cls._route_distance(region, neighbor)
        average_cost = (region.route_cost + neighbor.route_cost) / 2.0
        corridor = cls._route_terrain(region, neighbor, distance)
        capacity = max(8, int(22 - distance * 2.4 - average_cost * 3.0 + rng.uniform(-2.0, 2.0)))
        risk = min(0.38, 0.06 * distance + 0.04 * average_cost)
        routes[key] = TradeRoute(
            region_a=key[0],
            region_b=key[1],
            distance=distance,
            capacity=capacity,
            risk=risk,
            terrain=corridor,
        )

    @classmethod
    def _select_blueprints(cls, map_seed: int, count: int) -> list[tuple[str, float, float, float, float, str, int, int]]:
        scored_blueprints: list[tuple[float, tuple[str, float, float, float, float, str, int, int]]] = []
        for index, blueprint in enumerate(cls.REGION_BLUEPRINTS):
            _, fertility, rainfall, winter_severity, route_cost, _, _, _ = blueprint
            score = (
                cls._noise_value(map_seed, index + 1, fertility + rainfall, channel=5)
                + fertility * 0.08
                - winter_severity * 0.04
                - route_cost * 0.03
            )
            scored_blueprints.append((score, blueprint))
        scored_blueprints.sort(key=lambda item: (item[0], item[1][0]), reverse=True)
        return [blueprint for _, blueprint in scored_blueprints[:count]]

    @classmethod
    def _claim_position(cls, map_seed: int, index: int, used_positions: set[tuple[int, int]]) -> tuple[int, int]:
        best_position: tuple[int, int] | None = None
        best_score = -999.0
        for x in range(cls.GRID_WIDTH):
            for y in range(cls.GRID_HEIGHT):
                if (x, y) in used_positions:
                    continue
                placement = cls._noise_value(map_seed, x + index * 1.7, y + index * 2.3, channel=29)
                spacing_bonus = 0.0
                if used_positions:
                    nearest_neighbor = min(math.dist((x, y), position) for position in used_positions)
                    spacing_bonus = min(0.85, nearest_neighbor * 0.14)
                center_bias = -abs(x - (cls.GRID_WIDTH - 1) / 2) * 0.03 - abs(y - (cls.GRID_HEIGHT - 1) / 2) * 0.04
                score = placement + spacing_bonus + center_bias
                if score > best_score:
                    best_score = score
                    best_position = (x, y)

        if best_position is None:
            raise ValueError("No map position available for region placement.")

        used_positions.add(best_position)
        return best_position

    @classmethod
    def _terrain_key_for(
        cls,
        *,
        preferred_terrain: str,
        moisture: float,
        elevation: float,
        temperature: float,
    ) -> str:
        terrain_scores = {
            "river_vale": moisture * 1.05 - abs(elevation) * 0.28 + (0.32 if preferred_terrain == "river_vale" else 0.0),
            "wind_steppe": 0.18 - abs(moisture) * 0.52 + temperature * 0.24 + (0.32 if preferred_terrain == "wind_steppe" else 0.0),
            "stone_basin": elevation * 0.86 - moisture * 0.16 + (0.32 if preferred_terrain == "stone_basin" else 0.0),
            "storm_coast": moisture * 0.74 + abs(elevation) * 0.10 + (0.32 if preferred_terrain == "storm_coast" else 0.0),
            "frozen_march": -temperature * 0.92 + elevation * 0.24 + (0.32 if preferred_terrain == "frozen_march" else 0.0),
            "sun_baked_flats": temperature * 0.88 - moisture * 0.90 + (0.32 if preferred_terrain == "sun_baked_flats" else 0.0),
        }
        return max(terrain_scores, key=terrain_scores.get)

    @staticmethod
    def _noise_value(map_seed: int, x: float, y: float, *, channel: int) -> float:
        return snoise2(
            (x + channel * 1.73 + map_seed * 0.0013) / 3.6,
            (y - channel * 1.19 - map_seed * 0.0011) / 3.6,
            octaves=3,
            persistence=0.5,
            lacunarity=2.0,
            base=map_seed + channel * 97,
        )

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, round(value, 3)))

    @classmethod
    def _region_terrain(cls, terrain_key: str) -> RegionTerrain:
        name, arable_land, water_retention, travel_difficulty, exposure, defense = cls.TERRAIN_BLUEPRINTS[terrain_key]
        return RegionTerrain(
            name=name,
            arable_land=arable_land,
            water_retention=water_retention,
            travel_difficulty=travel_difficulty,
            exposure=exposure,
            defense=defense,
        )

    @staticmethod
    def _route_terrain(region_a: Region, region_b: Region, distance: float) -> RouteTerrain:
        average_difficulty = (region_a.terrain.travel_difficulty + region_b.terrain.travel_difficulty) / 2.0
        average_exposure = (region_a.terrain.exposure + region_b.terrain.exposure) / 2.0
        defensive_pressure = max(region_a.terrain.defense, region_b.terrain.defense)

        if defensive_pressure >= 1.10 and distance <= 4.6:
            return RouteTerrain(name="Narrow Pass", travel_difficulty=1.22, exposure=max(0.98, average_exposure), chokepoint=1.18)
        if average_exposure >= 1.12:
            return RouteTerrain(name="Weatherbeaten Road", travel_difficulty=1.12, exposure=1.18, chokepoint=1.02)
        if average_difficulty <= 1.0 and average_exposure <= 0.96:
            return RouteTerrain(name="River Road", travel_difficulty=0.92, exposure=0.92, chokepoint=0.96)
        return RouteTerrain(name="Open Road", travel_difficulty=max(1.0, average_difficulty), exposure=max(0.98, average_exposure), chokepoint=1.0)

    @staticmethod
    def _route_distance(region_a: Region, region_b: Region) -> float:
        return round(math.dist((region_a.x, region_a.y), (region_b.x, region_b.y)), 2)
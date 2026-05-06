from __future__ import annotations

from dataclasses import dataclass
import math

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
        blueprints = list(cls.REGION_BLUEPRINTS)
        rng.shuffle(blueprints)
        regions: list[Region] = []
        for name, fertility, rainfall, winter_severity, route_cost, terrain_key, x, y in blueprints[:count]:
            regions.append(
                Region(
                    name=name,
                    fertility=fertility,
                    rainfall=rainfall,
                    winter_severity=winter_severity,
                    route_cost=route_cost,
                    terrain=cls._region_terrain(terrain_key),
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
                key = tuple(sorted((region.name, neighbor.name)))
                if key in routes:
                    continue
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
        return routes

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
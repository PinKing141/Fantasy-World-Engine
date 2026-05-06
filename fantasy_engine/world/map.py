from __future__ import annotations

from dataclasses import dataclass
import math

from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.world.routes import TradeRoute


@dataclass(slots=True)
class Region:
    name: str
    fertility: float
    rainfall: float
    winter_severity: float
    route_cost: float
    x: int
    y: int


class WorldMap:
    REGION_BLUEPRINTS = (
        ("Greenreach Vale", 1.35, 1.15, 0.80, 1.10, 2, 4),
        ("Ashen Steppe", 0.88, 0.75, 1.05, 1.65, 6, 2),
        ("Ironroot Basin", 1.10, 0.95, 1.10, 1.35, 4, 5),
        ("Stormcoast March", 0.95, 1.20, 0.92, 1.50, 1, 1),
        ("Frostmere", 0.82, 0.90, 1.35, 1.85, 8, 0),
        ("Sunscar Flats", 0.72, 0.68, 0.88, 1.70, 8, 5),
    )

    @classmethod
    def generate(cls, rng: SeededRNG, count: int) -> list[Region]:
        blueprints = list(cls.REGION_BLUEPRINTS)
        rng.shuffle(blueprints)
        regions: list[Region] = []
        for name, fertility, rainfall, winter_severity, route_cost, x, y in blueprints[:count]:
            regions.append(
                Region(
                    name=name,
                    fertility=fertility,
                    rainfall=rainfall,
                    winter_severity=winter_severity,
                    route_cost=route_cost,
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
                capacity = max(8, int(22 - distance * 2.4 - average_cost * 3.0 + rng.uniform(-2.0, 2.0)))
                risk = min(0.38, 0.06 * distance + 0.04 * average_cost)
                routes[key] = TradeRoute(
                    region_a=key[0],
                    region_b=key[1],
                    distance=distance,
                    capacity=capacity,
                    risk=risk,
                )
        return routes

    @staticmethod
    def _route_distance(region_a: Region, region_b: Region) -> float:
        return round(math.dist((region_a.x, region_a.y), (region_b.x, region_b.y)), 2)
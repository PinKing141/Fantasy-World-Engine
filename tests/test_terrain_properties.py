from __future__ import annotations

import unittest
from unittest.mock import patch

from fantasy_engine.systems.economy import EconomySystem
from fantasy_engine.systems.military import MilitarySystem
from fantasy_engine.core.engine import TickContext
from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.world.climate import ClimateSystem
from fantasy_engine.world.map import WorldMap
from fantasy_engine.world.world import World


class TerrainPropertyTests(unittest.TestCase):
    def test_procedural_geography_is_deterministic_per_seed_and_varies_across_seeds(self) -> None:
        same_seed_left = WorldMap.generate(SeededRNG(4242), 6)
        same_seed_right = WorldMap.generate(SeededRNG(4242), 6)
        different_seed = WorldMap.generate(SeededRNG(9898), 6)

        left_signature = sorted(
            (region.name, region.terrain.name, region.x, region.y, round(region.fertility, 3), round(region.rainfall, 3))
            for region in same_seed_left
        )
        right_signature = sorted(
            (region.name, region.terrain.name, region.x, region.y, round(region.fertility, 3), round(region.rainfall, 3))
            for region in same_seed_right
        )
        different_signature = sorted(
            (region.name, region.terrain.name, region.x, region.y, round(region.fertility, 3), round(region.rainfall, 3))
            for region in different_seed
        )

        self.assertEqual(left_signature, right_signature)
        self.assertNotEqual(left_signature, different_signature)
        self.assertEqual(len({(region.x, region.y) for region in same_seed_left}), len(same_seed_left))

        same_seed_routes = WorldMap.build_trade_routes(same_seed_left, SeededRNG(4242))
        self.assertTrue(same_seed_routes)
        self.assertTrue(all(route.distance > 0 for route in same_seed_routes.values()))

    def test_region_terrain_changes_harvest_for_same_climate_state(self) -> None:
        fertile_world = World(seed=4242, num_civilizations=4)
        harsh_world = World(seed=4242, num_civilizations=4)
        fertile_civilization = fertile_world.civilizations[0]
        harsh_civilization = harsh_world.civilizations[0]
        context = TickContext(year=1, season_index=2, season="autumn")

        fertile_civilization.farmland = 100
        harsh_civilization.farmland = 100
        fertile_civilization.region.fertility = 1.0
        harsh_civilization.region.fertility = 1.0
        fertile_civilization.region.rainfall = 1.0
        harsh_civilization.region.rainfall = 1.0
        fertile_civilization.region.terrain.arable_land = 1.25
        fertile_civilization.region.terrain.water_retention = 1.10
        harsh_civilization.region.terrain.arable_land = 0.82
        harsh_civilization.region.terrain.water_retention = 0.86

        with patch("fantasy_engine.core.rng.SeededRNG.uniform", return_value=1.0):
            ClimateSystem().update(fertile_world, context)
            ClimateSystem().update(harsh_world, context)
            EconomySystem()._harvest(fertile_world, fertile_civilization, context)
            EconomySystem()._harvest(harsh_world, harsh_civilization, context)

        self.assertGreater(fertile_civilization.last_harvest, harsh_civilization.last_harvest)

    def test_route_terrain_changes_campaign_power_for_same_army(self) -> None:
        open_world = World(seed=4242, num_civilizations=4)
        difficult_world = World(seed=4242, num_civilizations=4)
        open_civilization = open_world.civilizations[0]
        difficult_civilization = difficult_world.civilizations[0]
        open_target = open_world.civilizations[1]
        difficult_target = difficult_world.civilizations[1]
        open_route = open_world.get_route(open_civilization.name, open_target.name)
        difficult_route = difficult_world.get_route(difficult_civilization.name, difficult_target.name)

        self.assertIsNotNone(open_route)
        self.assertIsNotNone(difficult_route)
        open_route = open_route
        difficult_route = difficult_route

        open_civilization.population = difficult_civilization.population = 12000
        open_civilization.military.standing_forces = difficult_civilization.military.standing_forces = 900
        open_civilization.military.levy_pool = difficult_civilization.military.levy_pool = 1800
        open_civilization.military.weapons_stockpile = difficult_civilization.military.weapons_stockpile = 160
        open_civilization.military.supply_stockpile = difficult_civilization.military.supply_stockpile = 90
        open_civilization.court.general.competence = difficult_civilization.court.general.competence = 72.0
        open_civilization.ruler.authority = difficult_civilization.ruler.authority = 68.0

        open_route.distance = difficult_route.distance = 5.0
        open_route.terrain.travel_difficulty = 0.90
        open_route.terrain.exposure = 0.92
        open_route.terrain.chokepoint = 0.95
        difficult_route.terrain.travel_difficulty = 1.35
        difficult_route.terrain.exposure = 1.18
        difficult_route.terrain.chokepoint = 1.22

        military_system = MilitarySystem()
        with patch("fantasy_engine.core.rng.SeededRNG.uniform", return_value=1.0):
            open_power, _, open_supply_cost, _ = military_system._campaign_power(open_civilization, open_route, open_world)
            difficult_power, _, difficult_supply_cost, _ = military_system._campaign_power(difficult_civilization, difficult_route, difficult_world)

        self.assertGreater(difficult_supply_cost, open_supply_cost)
        self.assertLess(difficult_power, open_power)


if __name__ == "__main__":
    unittest.main()
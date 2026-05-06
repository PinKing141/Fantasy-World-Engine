from __future__ import annotations

import unittest
from unittest.mock import patch

from fantasy_engine.core.engine import TickContext
from fantasy_engine.systems.military import MilitarySystem
from fantasy_engine.world.world import World


class HeroesAndProfessionsTests(unittest.TestCase):
    def test_battle_victory_can_raise_explicit_hero_from_general(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        winner = world.civilizations[0]
        loser = world.civilizations[1]
        route = world.get_route(winner.name, loser.name)
        self.assertIsNotNone(route)
        route = route
        route.mark_open()

        winner.active_wars.add(loser.name)
        loser.active_wars.add(winner.name)
        winner.military.standing_forces = 1400
        winner.military.levy_pool = 2600
        winner.military.weapons_stockpile = 220
        winner.military.supply_stockpile = 140
        loser.military.standing_forces = 260
        loser.military.levy_pool = 420
        loser.military.weapons_stockpile = 25
        loser.military.supply_stockpile = 18

        context = TickContext(year=world.year, season_index=2, season="autumn")
        MilitarySystem()._resolve_conflict(world, context, winner, loser)

        self.assertEqual(winner.court.general.profession, "commander")
        self.assertGreater(winner.court.general.heroic_reputation, 0.0)
        self.assertIsNotNone(winner.court.general.heroic_title)
        battle_event = next(event for event in world.history.events if event.event_type == "battle" and event.civilization == winner.name)
        hero_event = next(event for event in world.history.events if event.event_type == "hero_rises" and event.civilization == winner.name)
        self.assertEqual(hero_event.caused_by, battle_event.event_id)
        self.assertEqual(hero_event.data.get("hero_id"), winner.court.general.agent_id)

    def test_heroic_reputation_can_change_later_campaign_power(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        attacker = world.civilizations[0]
        defender = world.civilizations[1]
        route = world.get_route(attacker.name, defender.name)
        self.assertIsNotNone(route)
        route = route
        route.mark_open()
        attacker.military.standing_forces = 900
        attacker.military.levy_pool = 1200
        attacker.military.weapons_stockpile = 120
        attacker.military.supply_stockpile = 90

        with patch("fantasy_engine.core.rng.SeededRNG.uniform", return_value=1.0):
            baseline_power, *_ = MilitarySystem()._campaign_power(attacker, route, world)
            attacker.court.general.heroic_reputation = 20.0
            attacker.court.general.heroic_title = "the Red Banner"
            heroic_power, *_ = MilitarySystem()._campaign_power(attacker, route, world)

        self.assertGreater(heroic_power, baseline_power)


if __name__ == "__main__":
    unittest.main()
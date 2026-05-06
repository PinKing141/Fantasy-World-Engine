from __future__ import annotations

import unittest

from fantasy_engine.characters.needs import AgentNeeds
from fantasy_engine.core.engine import TickContext
from fantasy_engine.systems.diplomacy import DiplomacySystem
from fantasy_engine.world.world import World


class HolyWarTests(unittest.TestCase):
    def test_confessional_pressure_can_bias_war_target_choice(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            target_a = world.civilizations[1]
            target_b = world.civilizations[2]
            extra = world.civilizations[3]
            context = TickContext(year=4, season_index=2, season="autumn")

            civilization.population = 12000
            civilization.stability = 60.0
            civilization.unrest = 32.0
            civilization.unmet_food_pressure = 22.0
            civilization.legitimacy = 14.0
            civilization.schism_pressure = 34.0
            civilization.war_cooldown = 0
            civilization.ruler.aggression = 55.0
            civilization.ruler.ambition = 55.0
            civilization.ruler.empathy = 60.0
            civilization.ruler.authority = 70.0
            civilization.court.general.competence = 72.0
            civilization.military.standing_forces = 900
            civilization.military.levy_pool = 1800
            civilization.military.weapons_stockpile = 160
            civilization.military.supply_stockpile = 55
            civilization.ruler.needs = AgentNeeds(food=92.0, safety=94.0, belonging=48.0, esteem=91.0)
            civilization.court.general.needs = AgentNeeds(food=76.0, safety=96.0, belonging=34.0, esteem=84.0)

            civilization.relations[target_a.name] = -32.0
            civilization.relations[target_b.name] = -18.0
            for target in (target_a, target_b):
                target.relations[civilization.name] = -24.0
                target.population = 9600
                target.stability = 56.0
                target.legitimacy = 54.0
                target.ruler.authority = 60.0
                target.court.general.competence = 58.0
                target.military.standing_forces = 850
                target.military.levy_pool = 1800
                target.military.weapons_stockpile = 155
                target.military.supply_stockpile = 50

            extra.population = 0
            return world, context, civilization, target_a, target_b

        baseline_world, baseline_context, baseline_civilization, baseline_target_a, baseline_target_b = build_world()
        baseline_target_a.faith_id = baseline_civilization.faith_id
        baseline_target_b.faith_id = baseline_civilization.faith_id
        DiplomacySystem()._externalize_crisis(baseline_world, baseline_civilization, baseline_context)
        self.assertIn(baseline_target_a.name, baseline_civilization.active_wars)

        faith_world, faith_context, faith_civilization, faith_target_a, faith_target_b = build_world()
        faith_target_a.faith_id = faith_civilization.faith_id
        faith_target_b.faith_id = "ashen_reform"
        DiplomacySystem()._externalize_crisis(faith_world, faith_civilization, faith_context)

        self.assertNotEqual(baseline_civilization.active_wars, faith_civilization.active_wars)
        self.assertIn(faith_target_b.name, faith_civilization.active_wars)

    def test_confessional_war_can_emit_explicit_holy_war_event(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        target = world.civilizations[1]
        context = TickContext(year=4, season_index=2, season="autumn")

        civilization.population = 12000
        civilization.stability = 60.0
        civilization.unrest = 32.0
        civilization.unmet_food_pressure = 22.0
        civilization.legitimacy = 14.0
        civilization.schism_pressure = 36.0
        civilization.war_cooldown = 0
        civilization.ruler.aggression = 55.0
        civilization.ruler.ambition = 55.0
        civilization.ruler.empathy = 60.0
        civilization.ruler.authority = 70.0
        civilization.court.general.competence = 72.0
        civilization.military.standing_forces = 900
        civilization.military.levy_pool = 1800
        civilization.military.weapons_stockpile = 160
        civilization.military.supply_stockpile = 55
        civilization.ruler.needs = AgentNeeds(food=92.0, safety=94.0, belonging=48.0, esteem=91.0)
        civilization.court.general.needs = AgentNeeds(food=76.0, safety=96.0, belonging=34.0, esteem=84.0)

        civilization.relations[target.name] = -28.0
        target.relations[civilization.name] = -24.0
        target.faith_id = "ashen_reform"
        target.population = 9600
        target.stability = 56.0
        target.legitimacy = 54.0
        target.ruler.authority = 60.0
        target.court.general.competence = 58.0
        target.military.standing_forces = 850
        target.military.levy_pool = 1800
        target.military.weapons_stockpile = 155
        target.military.supply_stockpile = 50

        world.civilizations[2].population = 0
        world.civilizations[3].population = 0

        DiplomacySystem()._externalize_crisis(world, civilization, context)

        war_event = next(event for event in world.history.events if event.event_type == "war_declaration" and event.civilization == civilization.name)
        holy_war_event = next(event for event in world.history.events if event.event_type == "holy_war" and event.civilization == civilization.name)
        self.assertEqual(holy_war_event.caused_by, war_event.event_id)
        self.assertEqual(holy_war_event.other_civilization, target.name)
        self.assertIn("faith", holy_war_event.details.lower())


if __name__ == "__main__":
    unittest.main()
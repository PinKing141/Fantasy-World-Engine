from __future__ import annotations

import unittest
from unittest.mock import patch

from fantasy_engine.characters.needs import AgentNeeds
from fantasy_engine.core.engine import TickContext
from fantasy_engine.core.events import HistoryEvent
from fantasy_engine.systems.characters import CharacterSystem
from fantasy_engine.systems.diplomacy import DiplomacySystem
from fantasy_engine.systems.economy import EconomySystem
from fantasy_engine.systems.factions import FactionSystem
from fantasy_engine.systems.society import SocietySystem
from fantasy_engine.world.world import World


class LineageAndCultureRegressionTests(unittest.TestCase):
    def test_ruler_succession_preserves_dynasty_and_parent_link(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        previous_ruler = civilization.ruler
        previous_heir = civilization.court.heir
        context = TickContext(year=world.year, season_index=3, season="winter")

        previous_ruler.health = 0.0
        CharacterSystem()._check_court_death(world, civilization, previous_ruler, context)

        self.assertEqual(civilization.ruler.agent_id, previous_heir.agent_id)
        self.assertEqual(civilization.ruler.dynasty_name, previous_heir.dynasty_name)
        self.assertEqual(civilization.court.heir.dynasty_name, previous_heir.dynasty_name)
        self.assertEqual(civilization.court.heir.parent_ids, (previous_heir.agent_id,))
        self.assertTrue(any(event.event_type == "succession" for event in world.history.events))

    def test_migration_creates_one_drifted_descendant_culture(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        target = world.civilizations[1]
        society = SocietySystem()
        context = TickContext(year=6, season_index=3, season="winter")

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.shortage_streak = 2
        civilization.unrest = 70.0
        civilization.culture_shift_cooldown = 0
        target.food_stores = 180
        target.stability = 80.0
        target.culture_id = "northlands"

        society._maybe_shift_culture(world, civilization, context)
        shifted_culture = civilization.culture_id

        self.assertNotEqual(shifted_culture, civilization.culture_origin_id)
        self.assertEqual(civilization.culture_generation, 1)
        self.assertIn(shifted_culture, world.name_registry.cultures)
        self.assertTrue(any(event.event_type == "migration" for event in world.history.events))

        society._maybe_shift_culture(world, civilization, context)
        self.assertEqual(civilization.culture_id, shifted_culture)
        self.assertEqual(civilization.culture_generation, 1)

    def test_culture_split_creates_descendant_culture_and_updates_court(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        society = SocietySystem()
        context = TickContext(year=12, season_index=3, season="winter")

        civilization.shortage_streak = 0
        civilization.unrest = 8.0
        civilization.stability = 68.0
        civilization.culture_shift_cooldown = 0

        with patch("fantasy_engine.core.rng.SeededRNG.random", return_value=0.0):
            society._maybe_shift_culture(world, civilization, context)

        self.assertEqual(civilization.culture_generation, 1)
        self.assertNotEqual(civilization.culture_id, civilization.culture_origin_id)
        self.assertEqual(civilization.ruler.culture_id, civilization.culture_id)
        self.assertEqual(civilization.court.heir.culture_id, civilization.culture_id)
        self.assertTrue(any(event.event_type == "culture_split" for event in world.history.events))

    def test_defector_keeps_dynasty_but_origin_replacement_reanchors_to_origin_court(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        origin = world.civilizations[0]
        destination = world.civilizations[1]
        context = TickContext(year=world.year, season_index=1, season="summer")
        character_system = CharacterSystem()

        defector = origin.court.diplomat
        defector.loyalty = 0.0
        defector.grievance = 100.0
        origin.stability = 10.0
        origin.legitimacy = 10.0
        destination.stability = 85.0
        destination.culture_id = "northlands"
        origin.relations[destination.name] = 25.0

        expected_dynasty = defector.dynasty_name
        expected_origin_dynasty = origin.ruler.dynasty_name
        expected_heir_dynasty = origin.court.heir.dynasty_name
        expected_heir_parent = origin.court.heir.parent_ids

        character_system._check_defection(world, origin, context)

        self.assertEqual(destination.court.diplomat.agent_id, defector.agent_id)
        self.assertEqual(defector.dynasty_name, expected_dynasty)
        self.assertEqual(defector.culture_id, destination.culture_id)
        self.assertEqual(origin.court.diplomat.dynasty_name, expected_origin_dynasty)
        self.assertEqual(origin.court.diplomat.parent_ids, (origin.ruler.agent_id,))
        self.assertEqual(origin.court.heir.dynasty_name, expected_heir_dynasty)
        self.assertEqual(origin.court.heir.parent_ids, expected_heir_parent)
        self.assertNotEqual(origin.court.diplomat.agent_id, defector.agent_id)
        self.assertTrue(any(event.event_type == "defection" for event in world.history.events))

    def test_followup_origin_court_replacement_stays_on_ruler_branch_after_defection(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        origin = world.civilizations[0]
        destination = world.civilizations[1]
        defection_context = TickContext(year=world.year, season_index=1, season="summer")
        death_context = TickContext(year=world.year, season_index=3, season="winter")
        character_system = CharacterSystem()

        defector = origin.court.diplomat
        defector.loyalty = 0.0
        defector.grievance = 100.0
        origin.stability = 10.0
        origin.legitimacy = 10.0
        destination.stability = 85.0
        destination.culture_id = "northlands"
        origin.relations[destination.name] = 25.0

        character_system._check_defection(world, origin, defection_context)
        first_replacement = origin.court.diplomat
        origin_dynasty = origin.ruler.dynasty_name

        first_replacement.health = 0.0
        character_system._check_court_death(world, origin, first_replacement, death_context)

        second_replacement = origin.court.diplomat
        self.assertEqual(first_replacement.dynasty_name, origin_dynasty)
        self.assertEqual(second_replacement.dynasty_name, origin_dynasty)
        self.assertEqual(second_replacement.parent_ids, (first_replacement.agent_id,))
        self.assertNotEqual(second_replacement.agent_id, first_replacement.agent_id)

    def test_court_needs_rise_under_food_security_and_status_crisis(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        member = civilization.court.steward
        context = TickContext(year=world.year, season_index=1, season="summer")
        character_system = CharacterSystem()

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.unmet_food_pressure = 55.0
        civilization.shortage_streak = 2
        civilization.unrest = 72.0
        civilization.stability = 18.0
        civilization.legitimacy = 21.0
        civilization.war_exhaustion = 24.0
        civilization.active_wars.add(world.civilizations[1].name)
        member.authority = 32.0
        member.loyalty = 28.0
        member.grievance = 12.0

        previous_fatigue = member.fatigue
        previous_grievance = member.grievance
        previous_loyalty = member.loyalty

        character_system._update_court(world, civilization, context)

        self.assertGreater(member.needs.food, 0.0)
        self.assertGreater(member.needs.safety, 0.0)
        self.assertGreater(member.needs.belonging, 0.0)
        self.assertGreater(member.needs.esteem, 0.0)
        self.assertGreater(member.fatigue, previous_fatigue)
        self.assertGreater(member.grievance, previous_grievance)
        self.assertLess(member.loyalty, previous_loyalty)

    def test_ruler_needs_ease_when_recovery_conditions_hold(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        ruler = civilization.ruler
        character_system = CharacterSystem()

        civilization.food_stores = civilization.seasonal_food_need() * 4
        civilization.grain_stores = civilization.seasonal_food_need() * 4
        civilization.unmet_food_pressure = 0.0
        civilization.shortage_streak = 0
        civilization.unrest = 4.0
        civilization.stability = 78.0
        civilization.legitimacy = 82.0
        civilization.war_exhaustion = 0.0
        civilization.recovery_window = 3
        ruler.needs = AgentNeeds(food=62.0, safety=58.0, belonging=51.0, esteem=47.0)

        character_system._update_ruler(civilization)

        self.assertLess(ruler.needs.food, 62.0)
        self.assertLess(ruler.needs.safety, 58.0)
        self.assertLess(ruler.needs.belonging, 51.0)
        self.assertLess(ruler.needs.esteem, 47.0)

    def test_needs_can_push_defection_even_when_old_gate_values_are_not_met(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        origin = world.civilizations[0]
        route = world.routes_for(origin.name)[0]
        destination = world.get_civilization(world.route_partner_name(origin.name, route))
        self.assertIsNotNone(destination)
        destination = destination
        context = TickContext(year=world.year, season_index=1, season="summer")
        character_system = CharacterSystem()

        diplomat = origin.court.diplomat
        diplomat.loyalty = 55.0
        diplomat.grievance = 22.0
        diplomat.needs = AgentNeeds(food=35.0, safety=88.0, belonging=90.0, esteem=76.0)
        origin.stability = 26.0
        origin.legitimacy = 26.0
        destination.stability = 84.0
        origin.relations[destination.name] = 26.0

        character_system._check_defection(world, origin, context)

        self.assertEqual(destination.court.diplomat.agent_id, diplomat.agent_id)
        self.assertTrue(any(event.event_type == "defection" for event in world.history.events))

    def test_commoner_needs_can_supply_coup_pressure(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        faction_system = FactionSystem()
        context = TickContext(year=world.year, season_index=2, season="autumn")

        commoners = civilization.faction_by_name("Commoners")
        nobility = civilization.faction_by_name("Nobility")
        military = civilization.faction_by_name("Military")
        self.assertIsNotNone(commoners)
        self.assertIsNotNone(nobility)
        self.assertIsNotNone(military)
        commoners = commoners
        nobility = nobility
        military = military

        civilization.coup_cooldown = 0
        civilization.stability = 30.0
        civilization.legitimacy = 36.0
        civilization.unrest = 34.0
        civilization.unmet_food_pressure = 38.0
        commoners.influence = 0.58
        commoners.leader.grievance = 18.0
        commoners.leader.ambition = 42.0
        commoners.leader.authority = 46.0
        commoners.leader.needs = AgentNeeds(food=95.0, safety=72.0, belonging=78.0, esteem=52.0)
        nobility.influence = 0.12
        nobility.leader.grievance = 0.0
        nobility.leader.needs = AgentNeeds()
        military.influence = 0.10
        military.leader.grievance = 0.0
        military.leader.needs = AgentNeeds()

        with patch("fantasy_engine.core.rng.SeededRNG.random", return_value=0.0):
            faction_system.update(world, context)

        self.assertTrue(any(event.event_type == "faction_coup" for event in world.history.events))

    def test_ruler_and_general_needs_can_trigger_diplomatic_aggression(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        target = world.civilizations[1]
        context = TickContext(year=world.year, season_index=2, season="autumn")
        diplomacy_system = DiplomacySystem()

        civilization.unrest = 32.0
        civilization.unmet_food_pressure = 20.0
        civilization.legitimacy = 14.0
        civilization.war_cooldown = 0
        civilization.relations[target.name] = -26.0
        civilization.ruler.aggression = 55.0
        civilization.ruler.ambition = 55.0
        civilization.ruler.empathy = 60.0
        civilization.ruler.needs = AgentNeeds(food=92.0, safety=94.0, belonging=48.0, esteem=91.0)
        civilization.court.general.needs = AgentNeeds(food=76.0, safety=96.0, belonging=34.0, esteem=84.0)
        military = civilization.faction_by_name("Military")
        self.assertIsNotNone(military)
        military.pressure = 60.0

        diplomacy_system._externalize_crisis(world, civilization, context)

        self.assertTrue(civilization.active_wars)
        self.assertTrue(any(event.event_type == "war_declaration" for event in world.history.events))

    def test_war_severs_direct_route_and_contests_adjacent_routes(self) -> None:
        world = World(seed=4242, num_civilizations=4)

        pivot = None
        war_route = None
        adjacent_route = None
        for civilization in world.civilizations:
            routes = world.routes_for(civilization.name)
            if len(routes) >= 2:
                pivot = civilization
                war_route = routes[0]
                adjacent_route = routes[1]
                break

        self.assertIsNotNone(pivot)
        self.assertIsNotNone(war_route)
        self.assertIsNotNone(adjacent_route)
        pivot = pivot
        war_partner = world.get_civilization(world.route_partner_name(pivot.name, war_route))
        self.assertIsNotNone(war_partner)
        war_partner = war_partner

        pivot.active_wars.add(war_partner.name)
        war_partner.active_wars.add(pivot.name)
        world.refresh_route_states()

        self.assertEqual(war_route.state, "severed")
        self.assertEqual(adjacent_route.state, "contested")

    def test_route_transitions_emit_disruption_and_reopen_events(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        route = next(iter(world.trade_routes.values()))
        civilization_a = world.civilization_for_region(route.region_a)
        civilization_b = world.civilization_for_region(route.region_b)
        self.assertIsNotNone(civilization_a)
        self.assertIsNotNone(civilization_b)
        civilization_a = civilization_a
        civilization_b = civilization_b

        civilization_a.active_wars.add(civilization_b.name)
        civilization_b.active_wars.add(civilization_a.name)
        world.refresh_route_states()

        civilization_a.active_wars.clear()
        civilization_b.active_wars.clear()
        world.refresh_route_states()

        route_events = [
            event.event_type
            for event in world.history.events
            if event.event_type in {"route_severed", "route_reopened"}
            and {event.civilization, event.other_civilization} == {civilization_a.name, civilization_b.name}
        ]
        self.assertIn("route_severed", route_events)
        self.assertIn("route_reopened", route_events)

    def test_severed_route_blocks_food_imports_and_preserves_shortage(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        economy_system = EconomySystem()
        context = TickContext(year=world.year, season_index=1, season="summer")
        route = next(iter(world.trade_routes.values()))
        importer = world.civilization_for_region(route.region_a)
        exporter = world.civilization_for_region(route.region_b)
        self.assertIsNotNone(importer)
        self.assertIsNotNone(exporter)
        importer = importer
        exporter = exporter

        importer.food_stores = 0
        importer.grain_stores = 0
        importer.treasury = 120
        exporter.food_stores = 220
        exporter.grain_stores = 180
        importer.active_wars.add(exporter.name)
        exporter.active_wars.add(importer.name)
        for civilization in world.civilizations:
            if civilization.name not in {importer.name, exporter.name}:
                civilization.food_stores = 0
                civilization.grain_stores = 0
        world.refresh_route_states()

        economy_system._attempt_imports(world, importer, context)

        self.assertEqual(route.state, "severed")
        self.assertEqual(world.pending_shipments, [])

    def test_route_driven_shortage_emits_trade_chokepoint_branch(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        partner_route = world.routes_for(civilization.name)[0]
        partner_name = world.route_partner_name(civilization.name, partner_route)
        self.assertIsNotNone(partner_name)
        partner = world.get_civilization(partner_name)
        self.assertIsNotNone(partner)
        partner = partner
        context = TickContext(year=world.year, season_index=1, season="summer")

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.treasury = 0
        civilization.legitimacy = 62.0
        civilization.war_exhaustion = 0.0
        civilization.active_wars.add(partner.name)
        partner.active_wars.add(civilization.name)
        world.refresh_route_states()

        SocietySystem()._apply_shortage(world, civilization, context, shortage=18, food_need=24)

        self.assertTrue(any(event.event_type == "trade_chokepoint" for event in world.history.events))

    def test_battle_memory_can_bias_war_target_choice(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            target_a = world.civilizations[1]
            target_b = world.civilizations[2]
            extra = world.civilizations[3]
            context = TickContext(year=4, season_index=2, season="autumn")

            civilization.unrest = 32.0
            civilization.unmet_food_pressure = 22.0
            civilization.legitimacy = 14.0
            civilization.war_cooldown = 0
            civilization.ruler.aggression = 55.0
            civilization.ruler.ambition = 55.0
            civilization.ruler.empathy = 60.0
            civilization.ruler.needs = AgentNeeds(food=92.0, safety=94.0, belonging=48.0, esteem=91.0)
            civilization.court.general.needs = AgentNeeds(food=76.0, safety=96.0, belonging=34.0, esteem=84.0)
            military = civilization.faction_by_name("Military")
            self.assertIsNotNone(military)
            military.pressure = 60.0

            civilization.relations[target_a.name] = -26.0
            civilization.relations[target_b.name] = -18.0
            for target in (target_a, target_b):
                target.relations[civilization.name] = -24.0
                target.population = 9600
                target.stability = 56.0
                target.legitimacy = 54.0
                target.military.standing_forces = 620
                target.military.levy_pool = 1400
                target.military.weapons_stockpile = 120
                target.military.supply_stockpile = 42

            extra.population = 0
            return world, context, civilization, target_a, target_b

        baseline_world, baseline_context, baseline_civilization, baseline_target_a, baseline_target_b = build_world()
        DiplomacySystem()._externalize_crisis(baseline_world, baseline_civilization, baseline_context)
        self.assertIn(baseline_target_a.name, baseline_civilization.active_wars)

        memory_world, memory_context, memory_civilization, _, memory_target_b = build_world()
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="summer",
                event_type="battle",
                civilization=memory_target_b.name,
                other_civilization=memory_civilization.name,
                details="A remembered frontier clash hardened attitudes.",
                severity="major",
            )
        )

        DiplomacySystem()._externalize_crisis(memory_world, memory_civilization, memory_context)

        self.assertNotEqual(baseline_civilization.active_wars, memory_civilization.active_wars)
        self.assertIn(memory_target_b.name, memory_civilization.active_wars)


if __name__ == "__main__":
    unittest.main()
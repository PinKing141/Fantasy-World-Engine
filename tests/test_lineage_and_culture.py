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
        self.assertIn(previous_heir.agent_id, civilization.court.heir.parent_ids)
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
        target.relations[civilization.name] = -24.0
        target.population = 9600
        target.stability = 56.0
        target.legitimacy = 54.0
        target.military.standing_forces = 620
        target.military.levy_pool = 1400
        target.military.weapons_stockpile = 120
        target.military.supply_stockpile = 42
        for candidate in world.civilizations[2:]:
            candidate.population = 0
        military = civilization.faction_by_name("Military")
        self.assertIsNotNone(military)
        military.pressure = 60.0

        diplomacy_system._externalize_crisis(world, civilization, context)

        self.assertTrue(civilization.active_wars)
        self.assertTrue(any(event.event_type == "war_declaration" for event in world.history.events))

    def test_foreign_backing_can_turn_faction_crisis_into_external_war(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = next(civilization for civilization in world.civilizations if len(world.routes_for(civilization.name)) >= 2)
            backer_name = world.route_partner_name(civilization.name, world.routes_for(civilization.name)[0])
            neutral_name = world.route_partner_name(civilization.name, world.routes_for(civilization.name)[1])
            self.assertIsNotNone(backer_name)
            self.assertIsNotNone(neutral_name)
            backer = world.get_civilization(backer_name)
            neutral = world.get_civilization(neutral_name)
            self.assertIsNotNone(backer)
            self.assertIsNotNone(neutral)
            backer = backer
            neutral = neutral
            context = TickContext(year=world.year, season_index=2, season="autumn")

            civilization.coup_cooldown = 2
            civilization.unrest = 30.0
            civilization.unmet_food_pressure = 14.0
            civilization.legitimacy = 20.0
            civilization.stability = 34.0
            civilization.war_cooldown = 0
            civilization.ruler.aggression = 70.0
            civilization.ruler.ambition = 70.0
            civilization.ruler.empathy = 50.0
            civilization.ruler.needs = AgentNeeds(food=8.0, safety=8.0, belonging=8.0, esteem=8.0)
            civilization.court.general.needs = AgentNeeds(food=8.0, safety=8.0, belonging=8.0, esteem=8.0)

            civilization.relations[backer.name] = -6.0
            civilization.relations[neutral.name] = 24.0
            backer.relations[civilization.name] = -28.0
            neutral.relations[civilization.name] = 12.0

            backer.stability = 72.0
            backer.legitimacy = 62.0
            backer.military.standing_forces = 820
            backer.military.levy_pool = 1800
            backer.military.weapons_stockpile = 150
            backer.military.supply_stockpile = 48

            military = civilization.faction_by_name("Military")
            commoners = civilization.faction_by_name("Commoners")
            nobility = civilization.faction_by_name("Nobility")
            self.assertIsNotNone(military)
            self.assertIsNotNone(commoners)
            self.assertIsNotNone(nobility)
            military = military
            commoners = commoners
            nobility = nobility

            military.influence = 0.28
            military.leader.grievance = 8.0
            military.leader.ambition = 26.0
            military.leader.authority = 50.0
            military.leader.needs = AgentNeeds(food=10.0, safety=40.0, belonging=10.0, esteem=35.0)
            military.pressure = 62.0

            commoners.influence = 0.18
            commoners.leader.grievance = 0.0
            commoners.leader.needs = AgentNeeds()
            nobility.influence = 0.12
            nobility.leader.grievance = 0.0
            nobility.leader.needs = AgentNeeds()

            for route in world.routes_for(civilization.name):
                partner_name = world.route_partner_name(civilization.name, route)
                if partner_name not in {backer.name, neutral.name}:
                    continue
                route.distance = 4.0
                route.capacity = 12
                route.risk = 0.10
                route.mark_open()

            for candidate in world.civilizations:
                if candidate is civilization or candidate is backer or candidate is neutral:
                    continue
                candidate.population = 0

            return world, context, civilization, backer, neutral

        baseline_world, baseline_context, baseline_civilization, baseline_backer, _ = build_world()
        DiplomacySystem()._externalize_crisis(baseline_world, baseline_civilization, baseline_context)
        self.assertFalse(baseline_civilization.active_wars)

        memory_world, memory_context, memory_civilization, memory_backer, _ = build_world()
        FactionSystem().update(memory_world, memory_context)

        pressure_event = next(
            event for event in memory_world.history.events if event.event_type == "faction_pressure" and event.civilization == memory_civilization.name
        )
        backing_event = next(
            event for event in memory_world.history.events if event.event_type == "foreign_backing" and event.civilization == memory_civilization.name
        )

        DiplomacySystem()._externalize_crisis(memory_world, memory_civilization, memory_context)

        war_event = next(
            event for event in memory_world.history.events if event.event_type == "war_declaration" and event.civilization == memory_civilization.name
        )

        self.assertEqual(backing_event.other_civilization, memory_backer.name)
        self.assertEqual(backing_event.caused_by, pressure_event.event_id)
        self.assertEqual(war_event.other_civilization, memory_backer.name)
        self.assertEqual(war_event.caused_by, backing_event.event_id)

    def test_foreign_backing_can_push_nobility_crisis_into_coup(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = next(civilization for civilization in world.civilizations if len(world.routes_for(civilization.name)) >= 2)
            backer_name = world.route_partner_name(civilization.name, world.routes_for(civilization.name)[0])
            neutral_name = world.route_partner_name(civilization.name, world.routes_for(civilization.name)[1])
            self.assertIsNotNone(backer_name)
            self.assertIsNotNone(neutral_name)
            backer = world.get_civilization(backer_name)
            neutral = world.get_civilization(neutral_name)
            self.assertIsNotNone(backer)
            self.assertIsNotNone(neutral)
            backer = backer
            neutral = neutral
            context = TickContext(year=world.year, season_index=1, season="summer")

            civilization.coup_cooldown = 0
            civilization.stability = 31.0
            civilization.legitimacy = 34.0
            civilization.unrest = 22.0
            civilization.unmet_food_pressure = 6.0

            civilization.relations[backer.name] = -10.0
            civilization.relations[neutral.name] = 18.0
            backer.relations[civilization.name] = -32.0
            neutral.relations[civilization.name] = 8.0

            backer.stability = 72.0
            backer.legitimacy = 61.0
            backer.military.standing_forces = 860
            backer.military.levy_pool = 1700
            backer.military.weapons_stockpile = 155
            backer.military.supply_stockpile = 46

            commoners = civilization.faction_by_name("Commoners")
            nobility = civilization.faction_by_name("Nobility")
            military = civilization.faction_by_name("Military")
            self.assertIsNotNone(commoners)
            self.assertIsNotNone(nobility)
            self.assertIsNotNone(military)
            commoners = commoners
            nobility = nobility
            military = military

            nobility.influence = 0.38
            nobility.leader.grievance = 16.0
            nobility.leader.ambition = 24.0
            nobility.leader.authority = 58.0
            nobility.leader.loyalty = 42.0
            nobility.leader.needs = AgentNeeds(food=8.0, safety=18.0, belonging=22.0, esteem=64.0)

            commoners.influence = 0.10
            commoners.leader.grievance = 0.0
            commoners.leader.needs = AgentNeeds()
            military.influence = 0.08
            military.leader.grievance = 0.0
            military.leader.needs = AgentNeeds()

            civilization.ruler.needs = AgentNeeds(food=4.0, safety=4.0, belonging=8.0, esteem=9.0)

            for route in world.routes_for(civilization.name):
                partner_name = world.route_partner_name(civilization.name, route)
                if partner_name not in {backer.name, neutral.name}:
                    continue
                route.distance = 4.0
                route.capacity = 12
                route.risk = 0.10
                route.mark_open()

            for candidate in world.civilizations:
                if candidate is civilization or candidate is backer or candidate is neutral:
                    continue
                candidate.population = 0

            return world, context, civilization, backer, neutral

        baseline_world, baseline_context, baseline_civilization, _, _ = build_world()
        with patch("fantasy_engine.core.rng.SeededRNG.random", return_value=0.0):
            original_seek = FactionSystem._seek_foreign_backing
            FactionSystem._seek_foreign_backing = lambda self, world, civilization, context, faction, pressure: None
            try:
                FactionSystem().update(baseline_world, baseline_context)
            finally:
                FactionSystem._seek_foreign_backing = original_seek

        self.assertFalse(any(event.event_type == "faction_coup" for event in baseline_world.history.events))

        memory_world, memory_context, memory_civilization, memory_backer, _ = build_world()
        with patch("fantasy_engine.core.rng.SeededRNG.random", return_value=0.0):
            FactionSystem().update(memory_world, memory_context)

        pressure_event = next(
            event for event in memory_world.history.events if event.event_type == "faction_pressure" and event.civilization == memory_civilization.name
        )
        backing_event = next(
            event for event in memory_world.history.events if event.event_type == "foreign_backing" and event.civilization == memory_civilization.name
        )
        coup_event = next(
            event for event in memory_world.history.events if event.event_type == "faction_coup" and event.civilization == memory_civilization.name
        )

        self.assertEqual(backing_event.other_civilization, memory_backer.name)
        self.assertEqual(backing_event.caused_by, pressure_event.event_id)
        self.assertEqual(coup_event.caused_by, backing_event.event_id)
        self.assertEqual(coup_event.data.get("faction"), "Nobility")

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

    def test_route_severance_can_chain_into_shortage_pressure_and_coup(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        route = world.routes_for(civilization.name)[0]
        partner_name = world.route_partner_name(civilization.name, route)
        self.assertIsNotNone(partner_name)
        partner = world.get_civilization(partner_name)
        self.assertIsNotNone(partner)
        partner = partner
        context = TickContext(year=world.year, season_index=1, season="summer")

        civilization.active_wars.add(partner.name)
        partner.active_wars.add(civilization.name)
        world.refresh_route_states()

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.treasury = 0
        civilization.coup_cooldown = 0
        civilization.stability = 28.0
        civilization.legitimacy = 34.0
        civilization.unrest = 31.0
        civilization.unmet_food_pressure = 24.0

        commoners = civilization.faction_by_name("Commoners")
        nobility = civilization.faction_by_name("Nobility")
        military = civilization.faction_by_name("Military")
        self.assertIsNotNone(commoners)
        self.assertIsNotNone(nobility)
        self.assertIsNotNone(military)
        commoners = commoners
        nobility = nobility
        military = military

        commoners.influence = 0.58
        commoners.leader.grievance = 18.0
        commoners.leader.ambition = 42.0
        commoners.leader.authority = 46.0
        commoners.leader.needs = AgentNeeds(food=95.0, safety=74.0, belonging=80.0, esteem=54.0)
        nobility.influence = 0.12
        nobility.leader.grievance = 0.0
        nobility.leader.needs = AgentNeeds()
        military.influence = 0.10
        military.leader.grievance = 0.0
        military.leader.needs = AgentNeeds()

        SocietySystem()._apply_shortage(world, civilization, context, shortage=18, food_need=24)

        with patch("fantasy_engine.core.rng.SeededRNG.random", return_value=0.0):
            FactionSystem().update(world, context)

        route_event = next(
            event
            for event in world.history.events
            if event.event_type == "route_severed"
            and {event.civilization, event.other_civilization} == {civilization.name, partner.name}
        )
        shortage_event = next(
            event for event in world.history.events if event.event_type == "food_shortage" and event.civilization == civilization.name
        )
        chokepoint_event = next(
            event for event in world.history.events if event.event_type == "trade_chokepoint" and event.civilization == civilization.name
        )
        pressure_event = next(
            event for event in world.history.events if event.event_type == "faction_pressure" and event.civilization == civilization.name
        )
        coup_event = next(
            event for event in world.history.events if event.event_type == "faction_coup" and event.civilization == civilization.name
        )

        self.assertEqual(shortage_event.caused_by, route_event.event_id)
        self.assertEqual(chokepoint_event.caused_by, shortage_event.event_id)
        self.assertEqual(pressure_event.caused_by, chokepoint_event.event_id)
        foreign_backing_event = next(
            (
                event
                for event in world.history.events
                if event.event_type == "foreign_backing" and event.civilization == civilization.name
            ),
            None,
        )
        if foreign_backing_event is None:
            self.assertEqual(coup_event.caused_by, pressure_event.event_id)
            self.assertIn((pressure_event.event_id, coup_event.event_id), world.history.cause_effect_pairs())
        else:
            self.assertEqual(foreign_backing_event.caused_by, pressure_event.event_id)
            self.assertEqual(coup_event.caused_by, foreign_backing_event.event_id)
            self.assertIn((pressure_event.event_id, foreign_backing_event.event_id), world.history.cause_effect_pairs())
            self.assertIn((foreign_backing_event.event_id, coup_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((route_event.event_id, shortage_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((shortage_event.event_id, chokepoint_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((chokepoint_event.event_id, pressure_event.event_id), world.history.cause_effect_pairs())

    def test_contested_route_shortage_can_chain_into_unrest_and_war(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        route = world.routes_for(civilization.name)[0]
        partner_name = world.route_partner_name(civilization.name, route)
        self.assertIsNotNone(partner_name)
        partner = world.get_civilization(partner_name)
        self.assertIsNotNone(partner)
        partner = partner
        disruptor = next(candidate for candidate in world.civilizations if candidate.name not in {civilization.name, partner.name})
        context = TickContext(year=world.year, season_index=2, season="autumn")

        partner.active_wars.add(disruptor.name)
        disruptor.active_wars.add(partner.name)
        world.refresh_route_states()

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.treasury = 0
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
        military = military
        military.pressure = 60.0

        for candidate in world.civilizations:
            if candidate is civilization:
                continue
            civilization.relations[candidate.name] = -26.0 if candidate is partner else -18.0
            candidate.relations[civilization.name] = -24.0
            candidate.population = max(1, candidate.population)
            candidate.stability = 56.0
            candidate.legitimacy = 54.0
            candidate.military.standing_forces = 620
            candidate.military.levy_pool = 1400
            candidate.military.weapons_stockpile = 120
            candidate.military.supply_stockpile = 42

        SocietySystem()._apply_shortage(world, civilization, context, shortage=18, food_need=24)
        DiplomacySystem()._externalize_crisis(world, civilization, context)

        shortage_event = next(
            event for event in world.history.events if event.event_type == "food_shortage" and event.civilization == civilization.name
        )
        route_event = next(event for event in world.history.events if event.event_id == shortage_event.caused_by)
        unrest_event = next(
            event for event in world.history.events if event.event_type == "unrest" and event.civilization == civilization.name
        )
        war_event = next(
            event for event in world.history.events if event.event_type == "war_declaration" and event.civilization == civilization.name
        )

        self.assertEqual(route_event.event_type, "route_contested")
        self.assertIn(civilization.name, {route_event.civilization, route_event.other_civilization})
        self.assertEqual(unrest_event.caused_by, shortage_event.event_id)
        self.assertEqual(war_event.caused_by, unrest_event.event_id)
        self.assertIn((route_event.event_id, shortage_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((shortage_event.event_id, unrest_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((unrest_event.event_id, war_event.event_id), world.history.cause_effect_pairs())

    def test_contested_route_shortage_can_chain_into_court_stress_and_defection(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        route = world.routes_for(civilization.name)[0]
        partner_name = world.route_partner_name(civilization.name, route)
        self.assertIsNotNone(partner_name)
        partner = world.get_civilization(partner_name)
        self.assertIsNotNone(partner)
        partner = partner
        disruptor = next(candidate for candidate in world.civilizations if candidate.name not in {civilization.name, partner.name})
        context = TickContext(year=world.year, season_index=1, season="summer")

        partner.active_wars.add(disruptor.name)
        disruptor.active_wars.add(partner.name)
        world.refresh_route_states()

        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.treasury = 0
        civilization.stability = 22.0
        civilization.legitimacy = 20.0
        civilization.unrest = 34.0
        civilization.unmet_food_pressure = 24.0

        diplomat = civilization.court.diplomat
        diplomat.loyalty = 52.0
        diplomat.grievance = 28.0
        diplomat.needs = AgentNeeds(food=42.0, safety=86.0, belonging=88.0, esteem=72.0)

        SocietySystem()._apply_shortage(world, civilization, context, shortage=18, food_need=24)
        CharacterSystem().update(world, context)

        shortage_event = next(
            event for event in world.history.events if event.event_type == "food_shortage" and event.civilization == civilization.name
        )
        route_event = next(event for event in world.history.events if event.event_id == shortage_event.caused_by)
        court_stress_event = next(
            event for event in world.history.events if event.event_type == "court_hoarding" and event.civilization == civilization.name
        )
        defection_event = next(
            event for event in world.history.events if event.event_type == "defection" and event.civilization == civilization.name
        )

        self.assertEqual(route_event.event_type, "route_contested")
        self.assertIn(civilization.name, {route_event.civilization, route_event.other_civilization})
        self.assertEqual(court_stress_event.caused_by, shortage_event.event_id)
        self.assertEqual(defection_event.caused_by, court_stress_event.event_id)
        self.assertIn((route_event.event_id, shortage_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((shortage_event.event_id, court_stress_event.event_id), world.history.cause_effect_pairs())
        self.assertIn((court_stress_event.event_id, defection_event.event_id), world.history.cause_effect_pairs())

    def test_battle_memory_can_bias_war_target_choice(self) -> None:
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
            military = civilization.faction_by_name("Military")
            self.assertIsNotNone(military)
            military.pressure = 60.0

            civilization.relations[target_a.name] = -32.0
            civilization.relations[target_b.name] = -18.0
            for target in (target_a, target_b):
                target.relations[civilization.name] = -24.0
                target.population = 9600
                target.stability = 56.0
                target.legitimacy = 54.0
                target.ruler.authority = 60.0
                target.court.general.competence = 58.0

            target_a.military.standing_forces = 850
            target_a.military.levy_pool = 1800
            target_a.military.weapons_stockpile = 155
            target_a.military.supply_stockpile = 50

            target_b.military.standing_forces = 760
            target_b.military.levy_pool = 1650
            target_b.military.weapons_stockpile = 140
            target_b.military.supply_stockpile = 46

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

    def test_aid_memory_can_bias_relief_donor_choice(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            recipient = next(civilization for civilization in world.civilizations if len(world.routes_for(civilization.name)) >= 2)
            donor_a_name = world.route_partner_name(recipient.name, world.routes_for(recipient.name)[0])
            donor_b_name = world.route_partner_name(recipient.name, world.routes_for(recipient.name)[1])
            self.assertIsNotNone(donor_a_name)
            self.assertIsNotNone(donor_b_name)
            donor_a = world.get_civilization(donor_a_name)
            donor_b = world.get_civilization(donor_b_name)
            self.assertIsNotNone(donor_a)
            self.assertIsNotNone(donor_b)
            donor_a = donor_a
            donor_b = donor_b
            context = TickContext(year=4, season_index=1, season="summer")

            recipient.food_stores = 0
            recipient.grain_stores = 0
            recipient.unrest = 24.0
            recipient.legitimacy = 40.0
            recipient.recovery_window = 0
            recipient.last_relief_season = None

            for donor in (donor_a, donor_b):
                donor.food_stores = 160
                donor.grain_stores = 140
                donor.relief_cooldown = 0
                donor.court.diplomat.empathy = 60.0
                donor.stability = 70.0

            recipient.relations[donor_a.name] = 30.0
            recipient.relations[donor_b.name] = 10.0
            donor_a.relations[recipient.name] = 10.0
            donor_b.relations[recipient.name] = 10.0

            for route in world.routes_for(recipient.name):
                partner_name = world.route_partner_name(recipient.name, route)
                if partner_name not in {donor_a.name, donor_b.name}:
                    continue
                route.distance = 4.0
                route.capacity = 12
                route.risk = 0.10
                route.mark_open()

            return world, context, recipient, donor_a, donor_b

        baseline_world, baseline_context, baseline_recipient, baseline_donor_a, baseline_donor_b = build_world()
        DiplomacySystem()._attempt_relief(baseline_world, baseline_recipient, baseline_context)
        self.assertEqual(len(baseline_world.pending_shipments), 1)
        self.assertEqual(baseline_world.pending_shipments[0].kind, "aid")
        self.assertEqual(baseline_world.pending_shipments[0].origin, baseline_donor_a.name)

        memory_world, memory_context, memory_recipient, memory_donor_a, memory_donor_b = build_world()
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="war_declaration",
                civilization=memory_donor_a.name,
                other_civilization=memory_recipient.name,
                details="A remembered border war poisoned trust.",
                severity="major",
            )
        )
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="diplomatic_aid",
                civilization=memory_donor_b.name,
                other_civilization=memory_recipient.name,
                details="Past emergency grain relief built trust.",
                severity="normal",
            )
        )

        DiplomacySystem()._attempt_relief(memory_world, memory_recipient, memory_context)

        self.assertEqual(len(memory_world.pending_shipments), 1)
        self.assertEqual(memory_world.pending_shipments[0].kind, "aid")
        self.assertNotEqual(baseline_world.pending_shipments[0].origin, memory_world.pending_shipments[0].origin)
        self.assertEqual(memory_world.pending_shipments[0].origin, memory_donor_b.name)

    def test_hostile_aid_memory_can_cause_relief_refusal(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object]:
            world = World(seed=4242, num_civilizations=4)
            recipient = next(civilization for civilization in world.civilizations if world.routes_for(civilization.name))
            route = world.routes_for(recipient.name)[0]
            donor_name = world.route_partner_name(recipient.name, route)
            self.assertIsNotNone(donor_name)
            donor = world.get_civilization(donor_name)
            self.assertIsNotNone(donor)
            donor = donor
            context = TickContext(year=4, season_index=1, season="summer")

            recipient.food_stores = 0
            recipient.grain_stores = 0
            recipient.unrest = 24.0
            recipient.legitimacy = 40.0
            recipient.recovery_window = 0
            recipient.last_relief_season = None

            donor.food_stores = 45
            donor.grain_stores = 20
            donor.relief_cooldown = 0
            donor.court.diplomat.empathy = 28.0

            recipient.relations[donor.name] = 12.0
            donor.relations[recipient.name] = 8.0

            for candidate_route in world.routes_for(recipient.name):
                partner_name = world.route_partner_name(recipient.name, candidate_route)
                if partner_name == donor.name:
                    candidate_route.distance = 7.0
                    candidate_route.capacity = 6
                    candidate_route.risk = 0.45
                    candidate_route.mark_open()
                else:
                    candidate_route.mark_severed(recipient.name, partner_name or "blocked")

            return world, context, recipient, donor

        baseline_world, baseline_context, baseline_recipient, baseline_donor = build_world()
        DiplomacySystem()._attempt_relief(baseline_world, baseline_recipient, baseline_context)
        self.assertEqual(len(baseline_world.pending_shipments), 1)
        self.assertEqual(baseline_world.pending_shipments[0].kind, "aid")
        self.assertEqual(baseline_world.pending_shipments[0].origin, baseline_donor.name)

        memory_world, memory_context, memory_recipient, memory_donor = build_world()
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="war_declaration",
                civilization=memory_donor.name,
                other_civilization=memory_recipient.name,
                details="A remembered border war poisoned trust.",
                severity="major",
            )
        )
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="summer",
                event_type="route_severed",
                civilization=memory_donor.name,
                other_civilization=memory_recipient.name,
                details="A remembered severed route deepened diplomatic distrust.",
                severity="major",
            )
        )

        DiplomacySystem()._attempt_relief(memory_world, memory_recipient, memory_context)

        self.assertEqual(memory_world.pending_shipments, [])

    def test_pair_history_can_bias_relation_alignment_drift(self) -> None:
        def build_world() -> tuple[World, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            counterpart = world.civilizations[1]

            civilization.active_wars.clear()
            counterpart.active_wars.clear()
            civilization.unrest = 12.0
            counterpart.unrest = 12.0
            civilization.relations[counterpart.name] = 10.0
            counterpart.relations[civilization.name] = 10.0
            return world, civilization, counterpart

        baseline_world, baseline_civilization, baseline_counterpart = build_world()
        DiplomacySystem()._drift_relations(baseline_world, [baseline_civilization, baseline_counterpart], current_year=4)

        memory_world, memory_civilization, memory_counterpart = build_world()
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="diplomatic_aid",
                civilization=memory_counterpart.name,
                other_civilization=memory_civilization.name,
                details="Past relief built trust.",
                severity="normal",
            )
        )
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="summer",
                event_type="war_declaration",
                civilization=memory_counterpart.name,
                other_civilization=memory_civilization.name,
                details="Past war hardened distrust.",
                severity="major",
            )
        )

        DiplomacySystem()._drift_relations(memory_world, [memory_civilization, memory_counterpart], current_year=4)

        self.assertNotEqual(
            baseline_civilization.relation_with(baseline_counterpart.name),
            memory_civilization.relation_with(memory_counterpart.name),
        )
        self.assertLess(
            memory_civilization.relation_with(memory_counterpart.name),
            baseline_civilization.relation_with(baseline_counterpart.name),
        )

    def test_dynasty_continuity_can_preserve_alignment_hostility_across_succession(self) -> None:
        def build_world() -> tuple[World, object, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            counterpart = world.civilizations[1]

            civilization.active_wars.clear()
            counterpart.active_wars.clear()
            civilization.unrest = 12.0
            counterpart.unrest = 12.0
            civilization.relations[counterpart.name] = 10.0
            counterpart.relations[civilization.name] = 10.0
            return world, civilization, counterpart

        succession_world, succession_civilization, succession_counterpart = build_world()
        succession_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="war_declaration",
                civilization=succession_counterpart.name,
                other_civilization=succession_civilization.name,
                details="The rival court opened a remembered border war.",
                severity="major",
            )
        )
        succession_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="succession",
                civilization=succession_counterpart.name,
                details="The heir inherited the throne without changing houses.",
                severity="major",
                data={
                    "old_ruler": "Old House Lord",
                    "old_ruler_dynasty": succession_counterpart.ruler.dynasty_name,
                    "new_ruler": "New House Lord",
                    "new_ruler_dynasty": succession_counterpart.ruler.dynasty_name,
                },
            )
        )

        DiplomacySystem()._drift_relations(
            succession_world,
            [succession_civilization, succession_counterpart],
            current_year=4,
        )

        coup_world, coup_civilization, coup_counterpart = build_world()
        coup_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="war_declaration",
                civilization=coup_counterpart.name,
                other_civilization=coup_civilization.name,
                details="The rival court opened a remembered border war.",
                severity="major",
            )
        )
        coup_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="faction_coup",
                civilization=coup_counterpart.name,
                details="A new ruling house seized the court.",
                severity="catastrophic",
                data={
                    "old_ruler": "Old House Lord",
                    "old_ruler_dynasty": "House Auric",
                    "new_ruler": "Coup Marshal",
                    "new_ruler_dynasty": "House Varyn",
                },
            )
        )
        coup_counterpart.ruler.dynasty_name = "House Varyn"

        DiplomacySystem()._drift_relations(
            coup_world,
            [coup_civilization, coup_counterpart],
            current_year=4,
        )

        self.assertLess(
            succession_civilization.relation_with(succession_counterpart.name),
            coup_civilization.relation_with(coup_counterpart.name),
        )

    def test_dynasty_continuity_can_preserve_aid_caution_across_succession(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            recipient = next(civilization for civilization in world.civilizations if len(world.routes_for(civilization.name)) >= 2)
            donor_a_name = world.route_partner_name(recipient.name, world.routes_for(recipient.name)[0])
            donor_b_name = world.route_partner_name(recipient.name, world.routes_for(recipient.name)[1])
            self.assertIsNotNone(donor_a_name)
            self.assertIsNotNone(donor_b_name)
            donor_a = world.get_civilization(donor_a_name)
            donor_b = world.get_civilization(donor_b_name)
            self.assertIsNotNone(donor_a)
            self.assertIsNotNone(donor_b)
            donor_a = donor_a
            donor_b = donor_b
            context = TickContext(year=4, season_index=1, season="summer")

            recipient.food_stores = 0
            recipient.grain_stores = 0
            recipient.unrest = 24.0
            recipient.legitimacy = 40.0
            recipient.recovery_window = 0
            recipient.last_relief_season = None

            for donor in (donor_a, donor_b):
                donor.food_stores = 160
                donor.grain_stores = 140
                donor.relief_cooldown = 0
                donor.court.diplomat.empathy = 60.0
                donor.stability = 70.0

            recipient.relations[donor_a.name] = 30.0
            recipient.relations[donor_b.name] = 10.0
            donor_a.relations[recipient.name] = 10.0
            donor_b.relations[recipient.name] = 10.0

            for route in world.routes_for(recipient.name):
                partner_name = world.route_partner_name(recipient.name, route)
                if partner_name not in {donor_a.name, donor_b.name}:
                    continue
                route.distance = 4.0
                route.capacity = 12
                route.risk = 0.10
                route.mark_open()

            return world, context, recipient, donor_a, donor_b

        succession_world, succession_context, succession_recipient, succession_donor_a, succession_donor_b = build_world()
        succession_world.history.record_event(
            HistoryEvent(
                year=2,
                season="autumn",
                event_type="war_declaration",
                civilization=succession_donor_a.name,
                other_civilization=succession_recipient.name,
                details="A remembered border war poisoned trust.",
                severity="major",
            )
        )
        succession_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="succession",
                civilization=succession_donor_a.name,
                details="The heir inherited the throne without changing houses.",
                severity="major",
                data={
                    "old_ruler": "Old House Lord",
                    "old_ruler_dynasty": succession_donor_a.ruler.dynasty_name,
                    "new_ruler": "New House Lord",
                    "new_ruler_dynasty": succession_donor_a.ruler.dynasty_name,
                },
            )
        )

        DiplomacySystem()._attempt_relief(succession_world, succession_recipient, succession_context)

        self.assertEqual(len(succession_world.pending_shipments), 1)
        self.assertEqual(succession_world.pending_shipments[0].origin, succession_donor_b.name)

        coup_world, coup_context, coup_recipient, coup_donor_a, coup_donor_b = build_world()
        coup_world.history.record_event(
            HistoryEvent(
                year=2,
                season="autumn",
                event_type="war_declaration",
                civilization=coup_donor_a.name,
                other_civilization=coup_recipient.name,
                details="A remembered border war poisoned trust.",
                severity="major",
            )
        )
        coup_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="faction_coup",
                civilization=coup_donor_a.name,
                details="A new ruling house seized the court.",
                severity="catastrophic",
                data={
                    "old_ruler": "Old House Lord",
                    "old_ruler_dynasty": "House Auric",
                    "new_ruler": "Coup Marshal",
                    "new_ruler_dynasty": "House Varyn",
                },
            )
        )
        coup_donor_a.ruler.dynasty_name = "House Varyn"

        DiplomacySystem()._attempt_relief(coup_world, coup_recipient, coup_context)

        self.assertEqual(len(coup_world.pending_shipments), 1)
        self.assertEqual(coup_world.pending_shipments[0].origin, coup_donor_a.name)

    def test_defection_memory_can_bias_destination_choice(self) -> None:
        def build_world() -> tuple[World, TickContext, object, object, object, object]:
            world = World(seed=4242, num_civilizations=4)
            origin = next(civilization for civilization in world.civilizations if len(world.routes_for(civilization.name)) >= 2)
            destination_a_name = world.route_partner_name(origin.name, world.routes_for(origin.name)[0])
            destination_b_name = world.route_partner_name(origin.name, world.routes_for(origin.name)[1])
            self.assertIsNotNone(destination_a_name)
            self.assertIsNotNone(destination_b_name)
            destination_a = world.get_civilization(destination_a_name)
            destination_b = world.get_civilization(destination_b_name)
            self.assertIsNotNone(destination_a)
            self.assertIsNotNone(destination_b)
            destination_a = destination_a
            destination_b = destination_b
            context = TickContext(year=4, season_index=1, season="summer")
            character_system = CharacterSystem()

            diplomat = origin.court.diplomat
            diplomat.loyalty = 55.0
            diplomat.grievance = 22.0
            diplomat.needs = AgentNeeds(food=35.0, safety=88.0, belonging=90.0, esteem=76.0)

            origin.stability = 26.0
            origin.legitimacy = 26.0
            origin.relations[destination_a.name] = 26.0
            origin.relations[destination_b.name] = 22.0

            for destination in (destination_a, destination_b):
                destination.stability = 84.0
                destination.legitimacy = 60.0
                destination.culture_id = destination.culture_id
                destination.relations[origin.name] = 10.0

            for route in world.routes_for(origin.name):
                partner_name = world.route_partner_name(origin.name, route)
                if partner_name not in {destination_a.name, destination_b.name}:
                    continue
                route.distance = 4.0
                route.capacity = 12
                route.risk = 0.10
                route.mark_open()

            return world, context, origin, destination_a, destination_b, character_system

        baseline_world, baseline_context, baseline_origin, baseline_destination_a, baseline_destination_b, character_system = build_world()
        original_diplomat_id = baseline_origin.court.diplomat.agent_id
        character_system._check_defection(baseline_world, baseline_origin, baseline_context)
        self.assertEqual(baseline_destination_a.court.diplomat.agent_id, original_diplomat_id)
        self.assertNotEqual(baseline_destination_b.court.diplomat.agent_id, original_diplomat_id)

        memory_world, memory_context, memory_origin, memory_destination_a, memory_destination_b, memory_character_system = build_world()
        memory_diplomat_id = memory_origin.court.diplomat.agent_id
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="spring",
                event_type="war_declaration",
                civilization=memory_destination_a.name,
                other_civilization=memory_origin.name,
                details="A remembered border war poisoned trust.",
                severity="major",
            )
        )
        memory_world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="diplomatic_aid",
                civilization=memory_destination_b.name,
                other_civilization=memory_origin.name,
                details="Past emergency grain relief built trust.",
                severity="normal",
            )
        )

        memory_character_system._check_defection(memory_world, memory_origin, memory_context)

        self.assertNotEqual(baseline_destination_a.court.diplomat.agent_id, memory_destination_a.court.diplomat.agent_id)
        self.assertEqual(memory_destination_b.court.diplomat.agent_id, memory_diplomat_id)
        self.assertNotEqual(memory_destination_a.court.diplomat.agent_id, memory_diplomat_id)


if __name__ == "__main__":
    unittest.main()
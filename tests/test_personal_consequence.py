from __future__ import annotations

import unittest

from fantasy_engine.core.engine import TickContext
from fantasy_engine.systems.characters import CharacterSystem
from fantasy_engine.world.world import World


class PersonalConsequenceTests(unittest.TestCase):
    def test_ruler_death_can_create_bereavement_pressure_for_bonded_heir(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        previous_ruler = civilization.ruler
        previous_heir = civilization.court.heir
        previous_heir_loyalty = previous_heir.loyalty
        context = TickContext(year=world.year, season_index=3, season="winter")

        previous_ruler.health = 0.0
        CharacterSystem()._check_court_death(world, civilization, previous_ruler, context)

        self.assertEqual(civilization.ruler.agent_id, previous_heir.agent_id)
        self.assertGreater(civilization.ruler.grievance, 0.0)
        self.assertLess(civilization.ruler.loyalty, previous_heir_loyalty)
        bereavement_event = next(
            event
            for event in world.history.events
            if event.event_type == "bereavement"
            and event.civilization == civilization.name
            and event.data.get("subject_id") == previous_heir.agent_id
        )
        self.assertEqual(bereavement_event.data.get("lost_relation_id"), previous_ruler.agent_id)
        self.assertEqual(bereavement_event.caused_by, next(event.event_id for event in world.history.events if event.event_type == "succession"))

    def test_successor_behavior_can_diverge_from_lingering_bereavement(self) -> None:
        def build_world() -> tuple[World, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            context = TickContext(year=world.year, season_index=3, season="winter")
            civilization.ruler.health = 0.0
            CharacterSystem()._check_court_death(world, civilization, civilization.ruler, context)
            return world, civilization

        grieving_world, grieving_civilization = build_world()
        baseline_world, baseline_civilization = build_world()
        grieving_ruler = grieving_civilization.ruler
        baseline_ruler = baseline_civilization.ruler

        self.assertGreater(grieving_ruler.bereavement_load, 0.0)

        for attribute in ("stability", "legitimacy", "unrest", "unmet_food_pressure", "schism_pressure"):
            setattr(baseline_civilization, attribute, getattr(grieving_civilization, attribute))

        baseline_ruler.health = grieving_ruler.health
        baseline_ruler.fatigue = grieving_ruler.fatigue
        baseline_ruler.grievance = grieving_ruler.grievance
        baseline_ruler.loyalty = grieving_ruler.loyalty
        baseline_ruler.authority = grieving_ruler.authority
        baseline_ruler.needs = grieving_ruler.needs
        baseline_ruler.bereavement_load = 0.0

        character_system = CharacterSystem()
        character_system._update_ruler(grieving_civilization)
        character_system._update_ruler(baseline_civilization)

        self.assertGreater(grieving_ruler.grievance, baseline_ruler.grievance)
        self.assertLess(grieving_ruler.loyalty, baseline_ruler.loyalty)
        self.assertLess(grieving_ruler.authority, baseline_ruler.authority)

    def test_defection_can_create_estrangement_for_sibling_kin_without_direct_bond(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        origin = world.civilizations[0]
        destination = world.civilizations[1]
        context = TickContext(year=world.year, season_index=1, season="summer")

        heir = origin.court.heir
        defector = origin.court.diplomat
        defector.parent_ids = heir.parent_ids
        defector.dynasty_name = heir.dynasty_name
        defector.bond_ids = tuple(bond for bond in defector.bond_ids if bond != heir.agent_id)
        heir.bond_ids = tuple(bond for bond in heir.bond_ids if bond != defector.agent_id)

        defector.loyalty = 0.0
        defector.grievance = 100.0
        origin.stability = 10.0
        origin.legitimacy = 10.0
        destination.stability = 85.0
        origin.relations[destination.name] = 25.0

        previous_grievance = heir.grievance
        CharacterSystem()._check_defection(world, origin, context)

        self.assertGreater(heir.estrangement_load, 0.0)
        self.assertGreater(heir.grievance, previous_grievance)
        defection_event = next(event for event in world.history.events if event.event_type == "defection" and event.civilization == origin.name)
        estrangement_event = next(
            event
            for event in world.history.events
            if event.event_type == "estrangement"
            and event.civilization == origin.name
            and event.data.get("subject_id") == heir.agent_id
        )
        self.assertEqual(estrangement_event.data.get("relationship"), "sibling")
        self.assertEqual(estrangement_event.data.get("lost_relation_id"), defector.agent_id)
        self.assertEqual(estrangement_event.caused_by, defection_event.event_id)

    def test_heir_behavior_can_diverge_from_lingering_estrangement_after_defection(self) -> None:
        def build_world() -> tuple[World, object, object]:
            world = World(seed=4242, num_civilizations=4)
            origin = world.civilizations[0]
            destination = world.civilizations[1]
            context = TickContext(year=world.year, season_index=1, season="summer")

            heir = origin.court.heir
            defector = origin.court.diplomat
            defector.parent_ids = heir.parent_ids
            defector.dynasty_name = heir.dynasty_name
            defector.bond_ids = tuple(bond for bond in defector.bond_ids if bond != heir.agent_id)
            heir.bond_ids = tuple(bond for bond in heir.bond_ids if bond != defector.agent_id)

            defector.loyalty = 0.0
            defector.grievance = 100.0
            origin.stability = 10.0
            origin.legitimacy = 10.0
            destination.stability = 85.0
            origin.relations[destination.name] = 25.0

            CharacterSystem()._check_defection(world, origin, context)
            return world, origin, origin.court.heir

        estranged_world, estranged_civilization, estranged_heir = build_world()
        baseline_world, baseline_civilization, baseline_heir = build_world()

        self.assertGreater(estranged_heir.estrangement_load, 0.0)

        for attribute in ("stability", "legitimacy", "unrest", "unmet_food_pressure", "schism_pressure"):
            setattr(baseline_civilization, attribute, getattr(estranged_civilization, attribute))

        baseline_heir.health = estranged_heir.health
        baseline_heir.fatigue = estranged_heir.fatigue
        baseline_heir.grievance = estranged_heir.grievance
        baseline_heir.loyalty = estranged_heir.loyalty
        baseline_heir.authority = estranged_heir.authority
        baseline_heir.needs = estranged_heir.needs
        baseline_heir.bereavement_load = estranged_heir.bereavement_load
        baseline_heir.estrangement_load = 0.0

        character_system = CharacterSystem()
        context = TickContext(year=estranged_world.year, season_index=2, season="autumn")
        character_system._update_court(estranged_world, estranged_civilization, context)
        character_system._update_court(baseline_world, baseline_civilization, context)

        self.assertGreater(estranged_heir.grievance, baseline_heir.grievance)
        self.assertLess(estranged_heir.loyalty, baseline_heir.loyalty)

    def test_ruling_household_can_form_explicit_marriage_state(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        consort = civilization.court.consort

        self.assertEqual(civilization.ruler.spouse_id, consort.agent_id)
        self.assertEqual(consort.spouse_id, civilization.ruler.agent_id)
        self.assertEqual(civilization.ruler.household_id, consort.household_id)
        self.assertIn(civilization.ruler.agent_id, civilization.court.heir.parent_ids)
        self.assertIn(consort.agent_id, civilization.court.heir.parent_ids)

    def test_succession_can_generate_new_heir_from_ruling_household(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        previous_consort_id = civilization.court.consort.agent_id
        previous_heir = civilization.court.heir
        context = TickContext(year=world.year, season_index=3, season="winter")

        civilization.ruler.health = 0.0
        CharacterSystem()._check_court_death(world, civilization, civilization.ruler, context)

        self.assertEqual(civilization.ruler.agent_id, previous_heir.agent_id)
        self.assertNotEqual(civilization.court.consort.agent_id, previous_consort_id)
        self.assertEqual(civilization.ruler.spouse_id, civilization.court.consort.agent_id)
        self.assertEqual(civilization.court.consort.spouse_id, civilization.ruler.agent_id)
        self.assertIn(civilization.ruler.agent_id, civilization.court.heir.parent_ids)
        self.assertIn(civilization.court.consort.agent_id, civilization.court.heir.parent_ids)


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

import unittest

from fantasy_engine.core.engine import TickContext
from fantasy_engine.systems.society import SocietySystem
from fantasy_engine.world.world import World


class FaithPressureTests(unittest.TestCase):
    def test_shortage_crisis_can_create_schism_pressure(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        civilization = world.civilizations[0]
        context = TickContext(year=world.year, season_index=1, season="summer")

        civilization.stability = 66.0
        civilization.legitimacy = 52.0
        civilization.unrest = 18.0
        civilization.food_stores = 0
        civilization.grain_stores = 0
        civilization.treasury = 0
        civilization.shortage_response_cooldown = 0

        civilization.ruler.faith_id = civilization.faith_id
        civilization.court.heir.faith_id = civilization.faith_id
        civilization.court.general.faith_id = civilization.faith_id
        civilization.court.diplomat.faith_id = civilization.faith_id
        civilization.court.steward.faith_id = civilization.faith_id

        SocietySystem()._apply_shortage(world, civilization, context, shortage=18, food_need=24)

        schism_event = next(
            event for event in world.history.events if event.event_type == "schism_pressure" and event.civilization == civilization.name
        )

        self.assertGreater(civilization.schism_pressure, 0.0)
        self.assertIn("faith", schism_event.details.lower())
        self.assertEqual(schism_event.caused_by, next(
            event.event_id for event in reversed(world.history.events) if event.event_type in {"court_hoarding", "food_shortage"} and event.civilization == civilization.name
        ))

    def test_court_faith_alignment_changes_schism_pressure_for_same_crisis(self) -> None:
        def build_world() -> tuple[World, TickContext, object]:
            world = World(seed=4242, num_civilizations=4)
            civilization = world.civilizations[0]
            context = TickContext(year=world.year, season_index=1, season="summer")

            civilization.stability = 66.0
            civilization.legitimacy = 52.0
            civilization.unrest = 18.0
            civilization.food_stores = 0
            civilization.grain_stores = 0
            civilization.treasury = 0
            civilization.shortage_response_cooldown = 0
            return world, context, civilization

        aligned_world, aligned_context, aligned_civilization = build_world()
        aligned_civilization.ruler.faith_id = aligned_civilization.faith_id
        aligned_civilization.court.heir.faith_id = aligned_civilization.faith_id
        aligned_civilization.court.general.faith_id = aligned_civilization.faith_id
        aligned_civilization.court.diplomat.faith_id = aligned_civilization.faith_id
        aligned_civilization.court.steward.faith_id = aligned_civilization.faith_id

        SocietySystem()._apply_shortage(aligned_world, aligned_civilization, aligned_context, shortage=18, food_need=24)

        misaligned_world, misaligned_context, misaligned_civilization = build_world()
        misaligned_civilization.ruler.faith_id = "ashen_reform"
        misaligned_civilization.court.heir.faith_id = "ashen_reform"
        misaligned_civilization.court.general.faith_id = misaligned_civilization.faith_id
        misaligned_civilization.court.diplomat.faith_id = "ashen_reform"
        misaligned_civilization.court.steward.faith_id = misaligned_civilization.faith_id

        SocietySystem()._apply_shortage(misaligned_world, misaligned_civilization, misaligned_context, shortage=18, food_need=24)

        self.assertGreater(misaligned_civilization.schism_pressure, aligned_civilization.schism_pressure)
        self.assertTrue(
            any(
                event.event_type == "schism_pressure" and event.civilization == misaligned_civilization.name
                for event in misaligned_world.history.events
            )
        )


if __name__ == "__main__":
    unittest.main()
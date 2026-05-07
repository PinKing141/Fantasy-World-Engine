from __future__ import annotations

from collections import Counter
import unittest

from fantasy_engine.web.simulation_session import SimulationSession


class WebSimulationSessionTests(unittest.TestCase):
    def test_initial_payload_covers_every_province_owner(self) -> None:
        session = SimulationSession(seed=909, width=384, height=240, land_fraction=0.42, num_civilizations=4)

        try:
            payload = session.initial_payload()
            province_owners = payload["province_owners"]

            self.assertEqual(len(province_owners), len(session.provinces.provinces))
            self.assertFalse(any(owner == "" for owner in province_owners))

            expected_counts = {
                civ["name"]: civ["province_count"]
                for civ in payload["civilizations"]
            }
            actual_counts = Counter(province_owners)
            self.assertEqual(actual_counts, expected_counts)

            for province in session.provinces.provinces:
                self.assertEqual(
                    session.civ_for_province(province.province_id),
                    province_owners[province.province_id],
                )
        finally:
            session.shutdown()
from __future__ import annotations

import unittest

from rich.console import Console

from fantasy_engine.core.events import HistoryEvent
from fantasy_engine.visual.rich_renderer import RichDashboardRenderer
from fantasy_engine.world.world import World


class LegendsReaderTests(unittest.TestCase):
    def test_world_recent_legends_reads_linked_event_chain(self) -> None:
        world = World(seed=4242, num_civilizations=4)

        route_event = world.history.record_event(
            HistoryEvent(
                year=3,
                season="summer",
                event_type="route_severed",
                civilization="Sylgard",
                other_civilization="Quor-Thal",
                details="War on the border severed the caravan road.",
                severity="major",
            )
        )
        shortage_event = world.history.record_event(
            HistoryEvent(
                year=3,
                season="autumn",
                event_type="food_shortage",
                civilization="Sylgard",
                details="Granaries failed to cover the autumn ration draw.",
                severity="major",
            )
        )
        pressure_event = world.history.record_event(
            HistoryEvent(
                year=3,
                season="autumn",
                event_type="faction_pressure",
                civilization="Sylgard",
                details="The nobility rallied openly against the court.",
                severity="major",
                data={"faction": "Nobility", "pressure": 66.0},
            )
        )
        coup_event = world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="faction_coup",
                civilization="Sylgard",
                details="The nobles seized the palace before winter court assembled.",
                severity="catastrophic",
                data={"faction": "Nobility"},
            )
        )
        world.history.record_event(
            HistoryEvent(
                year=3,
                season="winter",
                event_type="diplomatic_aid",
                civilization="Arador",
                other_civilization="Zanthar",
                details="A separate grain convoy reached a different frontier.",
                severity="normal",
            )
        )

        legends = world.recent_legends(limit=1)

        self.assertEqual(len(legends), 1)
        legend = legends[0]
        self.assertEqual(legend.anchor_event_id, coup_event.event_id)
        self.assertEqual(legend.event_ids, (route_event.event_id, shortage_event.event_id, pressure_event.event_id, coup_event.event_id))
        self.assertIn("Route Severed", legend.summary)
        self.assertIn("Food Shortage", legend.summary)
        self.assertIn("Faction Pressure", legend.summary)
        self.assertIn("Faction Coup", legend.summary)
        self.assertNotIn("Diplomatic Aid", legend.summary)

    def test_rich_renderer_run_end_prints_legends(self) -> None:
        console = Console(record=True, width=120)
        renderer = RichDashboardRenderer(console=console)

        renderer.render_run_end(
            [("E000010", "E000011")],
            [
                "Legend: Route Severed in Sylgard led to Food Shortage, then Faction Pressure, and ended in Faction Coup.",
            ],
        )

        output = console.export_text()
        self.assertIn("Cause", output)
        self.assertIn("Effect", output)
        self.assertIn("Legends", output)
        self.assertIn("Route Severed in Sylgard", output)


if __name__ == "__main__":
    unittest.main()
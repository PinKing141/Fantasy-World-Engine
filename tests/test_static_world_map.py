from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

import main
from fantasy_engine.visual.world_map import build_world_map_view, export_world_map
from fantasy_engine.world.world import World


class StaticWorldMapTests(unittest.TestCase):
    def test_seeded_world_builds_deterministic_map_view_from_snapshots(self) -> None:
        left_world = World(seed=4242, num_civilizations=4)
        right_world = World(seed=4242, num_civilizations=4)

        left_view = build_world_map_view(left_world.snapshot_current_state())
        right_view = build_world_map_view(right_world.snapshot_current_state())

        self.assertEqual(left_view, right_view)
        self.assertTrue(left_view.civilizations)
        self.assertTrue(left_view.routes)
        self.assertTrue(all(civilization.region_name for civilization in left_view.civilizations))
        self.assertTrue(all(civilization.terrain_name for civilization in left_view.civilizations))
        self.assertTrue(all(isinstance(civilization.map_x, int) for civilization in left_view.civilizations))
        self.assertTrue(all(isinstance(civilization.map_y, int) for civilization in left_view.civilizations))
        self.assertTrue(left_view.territories)
        self.assertEqual(len(left_view.territories), len(left_view.civilizations))
        self.assertTrue(all(len(territory.polygon_points) >= 3 for territory in left_view.territories))
        self.assertTrue(left_view.terrain_cells)
        self.assertTrue(any(cell.terrain_kind == "shallow_water" for cell in left_view.terrain_cells))
        self.assertTrue(any(cell.terrain_kind == "deep_water" for cell in left_view.terrain_cells))
        self.assertTrue(any(cell.terrain_kind == "fertile_land" for cell in left_view.terrain_cells))
        self.assertTrue(any(cell.terrain_kind == "hill" for cell in left_view.terrain_cells))
        self.assertTrue(any(cell.terrain_kind in {"highland", "mountain"} for cell in left_view.terrain_cells))
        self.assertTrue(left_view.coastline_segments)
        self.assertTrue(all(len(route.path_points) >= 3 for route in left_view.routes))

    def test_export_world_map_writes_non_empty_png(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        step_result = world.snapshot_current_state()

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "world_map.png"
            rendered_view = export_world_map(step_result, output_path)

            self.assertEqual(rendered_view, build_world_map_view(step_result))
            self.assertTrue(rendered_view.territories)
            self.assertTrue(rendered_view.terrain_cells)
            self.assertTrue(rendered_view.coastline_segments)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_different_seed_changes_terrain_surface_signature(self) -> None:
        left_world = World(seed=4242, num_civilizations=4)
        right_world = World(seed=9898, num_civilizations=4)

        left_view = build_world_map_view(left_world.snapshot_current_state())
        right_view = build_world_map_view(right_world.snapshot_current_state())

        left_signature = tuple((cell.x, cell.y, cell.terrain_kind) for cell in left_view.terrain_cells)
        right_signature = tuple((cell.x, cell.y, cell.terrain_kind) for cell in right_view.terrain_cells)

        self.assertNotEqual(left_signature, right_signature)

    def test_run_demo_can_export_map_from_entry_point(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "entry_point_map.png"
            renderer = mock.Mock()
            renderer.console = mock.Mock()

            with mock.patch("main.RichDashboardRenderer", return_value=renderer):
                main.run_demo(seed=4242, years=0, watch=False, export_map_path=str(output_path))

            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_main_forwards_export_map_argument_to_run_demo(self) -> None:
        with mock.patch("main.run_demo") as run_demo:
            with mock.patch(
                "sys.argv",
                ["main.py", "--seed", "111", "--years", "0", "--no-watch", "--export-map", "exports/world_map.png"],
            ):
                main.main()

        run_demo.assert_called_once_with(
            seed=111,
            years=0,
            watch=False,
            pace_seconds=1.0,
            clear_between_years=True,
            honor_autopause=True,
            export_map_path="exports/world_map.png",
        )


if __name__ == "__main__":
    unittest.main()
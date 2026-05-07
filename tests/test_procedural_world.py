from __future__ import annotations

import os
import unittest

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from fantasy_engine.visual.cartographer import CartographyOptions, RenderInputs, render_world
from fantasy_engine.world.geography import BIOME_COLORS, GeographyConfig, generate_geography
from fantasy_engine.world.provinces import build_province_map


class ProceduralGeographyTests(unittest.TestCase):
    """The geography generator is the foundation of every downstream layer."""

    def test_same_seed_produces_identical_geography(self) -> None:
        config = GeographyConfig(width=96, height=64, seed=4242)
        left = generate_geography(config)
        right = generate_geography(config)

        self.assertTrue(np.array_equal(left.elevation, right.elevation))
        self.assertTrue(np.array_equal(left.biome, right.biome))
        self.assertTrue(np.array_equal(left.rivers, right.rivers))
        self.assertEqual(left.sea_level, right.sea_level)
        self.assertEqual(len(left.landmasses), len(right.landmasses))

    def test_different_seeds_produce_different_geography(self) -> None:
        left = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        right = generate_geography(GeographyConfig(width=96, height=64, seed=9999))

        self.assertFalse(np.array_equal(left.elevation, right.elevation))
        self.assertAlmostEqual(left.land_mask.mean(), right.land_mask.mean(), places=3)

    def test_land_fraction_is_honored_across_seeds(self) -> None:
        for seed in (4242, 9999, 1234, 7777, 5555, 31415):
            result = generate_geography(GeographyConfig(width=80, height=64, seed=seed, land_fraction=0.42))
            self.assertAlmostEqual(result.land_mask.mean(), 0.42, places=2, msg=f"seed {seed}")

    def test_rivers_only_run_on_land(self) -> None:
        result = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        rivers_off_land = result.rivers & ~result.land_mask
        self.assertFalse(rivers_off_land.any(), "rivers should never paint water cells")

    def test_landmass_labels_are_contiguous_and_complete(self) -> None:
        result = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        self.assertTrue(((result.landmass_id >= 0) == result.land_mask).all())
        total_reported = sum(landmass.cell_count for landmass in result.landmasses)
        self.assertEqual(total_reported, int(result.land_mask.sum()))

    def test_biome_grid_uses_only_known_biome_names(self) -> None:
        result = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        for biome_idx in np.unique(result.biome):
            biome_name = result.biome_names[int(biome_idx)]
            self.assertIn(biome_name, BIOME_COLORS, f"unknown biome {biome_name}")


class ProvinceMapTests(unittest.TestCase):
    def test_every_land_cell_has_a_province_and_water_does_not(self) -> None:
        geography = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=120)
        has_province = provinces.province_id_grid >= 0
        self.assertTrue(np.array_equal(has_province, geography.land_mask))

    def test_provinces_do_not_cross_landmasses(self) -> None:
        geography = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=120)
        for province in provinces.provinces:
            cells_y, cells_x = np.where(provinces.province_id_grid == province.province_id)
            landmass_ids = np.unique(geography.landmass_id[cells_y, cells_x])
            self.assertEqual(landmass_ids.size, 1, f"province {province.province_id} spans landmasses {landmass_ids}")

    def test_province_neighbors_are_symmetric(self) -> None:
        geography = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=120)
        by_id = {province.province_id: province for province in provinces.provinces}
        for province in provinces.provinces:
            for neighbor_id in province.neighbor_ids:
                self.assertIn(province.province_id, by_id[neighbor_id].neighbor_ids)

    def test_province_generation_is_deterministic(self) -> None:
        geography = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        left = build_province_map(geography, target_cells_per_province=120)
        right = build_province_map(geography, target_cells_per_province=120)
        self.assertTrue(np.array_equal(left.province_id_grid, right.province_id_grid))
        self.assertEqual(len(left.provinces), len(right.provinces))


class CartographerTests(unittest.TestCase):
    def test_render_world_returns_correctly_shaped_rgb(self) -> None:
        geography = generate_geography(GeographyConfig(width=64, height=48, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=80)
        rgb = render_world(RenderInputs(geography=geography, provinces=provinces))

        self.assertEqual(rgb.shape, (geography.config.height, geography.config.width, 3))
        self.assertEqual(rgb.dtype, np.uint8)

    def test_render_is_deterministic_for_fixed_inputs(self) -> None:
        geography = generate_geography(GeographyConfig(width=64, height=48, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=80)
        options = CartographyOptions()
        a = render_world(RenderInputs(geography=geography, provinces=provinces, options=options))
        b = render_world(RenderInputs(geography=geography, provinces=provinces, options=options))
        self.assertTrue(np.array_equal(a, b))

    def test_selection_changes_pixels_within_selected_province(self) -> None:
        geography = generate_geography(GeographyConfig(width=64, height=48, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=80)
        baseline = render_world(RenderInputs(geography=geography, provinces=provinces))
        selected_id = provinces.provinces[0].province_id
        with_selection = render_world(RenderInputs(
            geography=geography,
            provinces=provinces,
            selected_province_id=selected_id,
        ))

        province_mask = provinces.province_id_grid == selected_id
        self.assertTrue(province_mask.any())
        diff = (baseline != with_selection).any(axis=2)
        self.assertTrue(np.all(diff[~province_mask] == False))
        self.assertTrue(diff[province_mask].any())


class InteractiveMapTests(unittest.TestCase):
    def setUp(self) -> None:
        import pygame

        pygame.init()
        self._pygame = pygame
        pygame.display.set_mode((640, 480))

        from fantasy_engine.runner import interactive_map
        self._module = interactive_map

    def tearDown(self) -> None:
        self._pygame.quit()

    def test_camera_round_trip_is_exact_at_default_zoom(self) -> None:
        camera = self._module.Camera(world_width=128, world_height=80, viewport_size=(800, 480))
        for x, y in [(64, 40), (10, 5), (120, 78)]:
            sx, sy = camera.world_to_screen(x, y)
            wx, wy = camera.screen_to_world(sx, sy)
            self.assertAlmostEqual(wx, x, places=3)
            self.assertAlmostEqual(wy, y, places=3)

    def test_zoom_at_anchors_world_point_under_cursor(self) -> None:
        camera = self._module.Camera(world_width=128, world_height=80, viewport_size=(800, 480))
        cursor = (300, 200)
        before = camera.screen_to_world(*cursor)
        camera.zoom_at(*cursor, factor=1.5)
        after = camera.screen_to_world(*cursor)
        self.assertAlmostEqual(before[0], after[0], places=3)
        self.assertAlmostEqual(before[1], after[1], places=3)

    def test_province_picking_returns_correct_id_at_centroid(self) -> None:
        geography = generate_geography(GeographyConfig(width=96, height=64, seed=4242))
        provinces = build_province_map(geography, target_cells_per_province=120)
        state = self._module.InteractiveMapState(geography=geography, provinces=provinces)
        camera = self._module.Camera(world_width=96, world_height=64, viewport_size=(800, 480))

        for province in provinces.provinces:
            if province.cell_count < 25:
                continue
            screen_pos = camera.world_to_screen(province.centroid_x, province.centroid_y)
            picked = self._module._province_id_at_screen(screen_pos, state, camera)
            self.assertEqual(picked, province.province_id, f"province #{province.province_id} centroid picked {picked}")
            return
        self.fail("No suitably large province found to test picking")


if __name__ == "__main__":
    unittest.main()

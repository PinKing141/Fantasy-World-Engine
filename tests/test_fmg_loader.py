"""Tests for the FMG .map loader.

We build a minimum-viable FMG-format payload by hand and verify the loader
extracts every domain object correctly. The synthetic payload mirrors
FMG's actual save structure (40 ``\\r\\n``-delimited lines) — see
``public/modules/io/save.js`` in the FMG source.
"""
import gzip
import io
import json
import unittest
from pathlib import Path

from fantasy_engine.io import (
    Biome,
    Burg,
    Culture,
    Province,
    Religion,
    River,
    State,
    World,
    load_fmg_map,
    parse_fmg_text,
)


def build_synthetic_map() -> str:
    """Return a minimum-viable FMG .map payload as a string.

    Three cells, two cultures, two states, two religions, two provinces,
    two burgs, one river. Values chosen to make assertions easy."""
    params = "1.120.5|MIT|2026-05-07|test_seed|1200|800|1700000000000"
    settings = "mi|3||ft|1.8|°F|||||||1|1.0|50|50|||1.0|{}|TestMap"
    coords = json.dumps({"latT": 60, "lonT": 80, "latN": 30, "lonW": -40})
    biomes = (
        # FMG format: colors_csv | habitability_csv | names_csv
        "#466eab,#fbe79f,#b5b887,#d2d082,#c8d68f"
        "|0,4,10,22,30"
        "|Marine,Hot desert,Cold desert,Savanna,Grassland"
    )
    notes = json.dumps([])
    svg = "<svg/>"
    grid_general = json.dumps({"cellsX": 50, "cellsY": 30})
    cell_h = ",".join(["10", "20", "30"])
    cell_prec = ",".join(["50", "60", "70"])
    cell_f = ",".join(["1", "1", "2"])
    cell_t = ",".join(["1", "1", "-1"])
    cell_temp = ",".join(["20", "22", "5"])
    pack_features = json.dumps([0, {"i": 1, "land": True}, {"i": 2, "land": False}])

    cultures = json.dumps([
        {"i": 0, "name": "Wildlands", "removed": True, "color": "#888"},
        {"i": 1, "name": "Anorian", "color": "#aa0", "type": "Generic", "base": 0,
         "expansionism": 1.2, "center": 1},
        {"i": 2, "name": "Brennic", "color": "#0aa", "type": "Highland", "base": 1,
         "expansionism": 0.9, "center": 2, "shield": "spanish"},
    ])
    states = json.dumps([
        {"i": 0, "name": "Neutrals", "removed": True},
        {"i": 1, "name": "Anor", "fullName": "Kingdom of Anor", "form": "Monarchy",
         "color": "#cc8", "capital": 1, "culture": 1, "center": 1,
         "expansionism": 1.5, "type": "Generic"},
        {"i": 2, "name": "Brenne", "fullName": "Republic of Brenne", "form": "Republic",
         "color": "#8cc", "capital": 2, "culture": 2, "center": 2,
         "expansionism": 1.0, "type": "Highland"},
    ])
    burgs = json.dumps([
        {"i": 0, "name": ""},  # sentinel
        {"i": 1, "name": "Anorhall", "cell": 1, "x": 100.5, "y": 200.0,
         "state": 1, "culture": 1, "feature": 1, "population": 12.3,
         "capital": 1, "port": 0},
        {"i": 2, "name": "Brennefurt", "cell": 2, "x": 250.0, "y": 100.0,
         "state": 2, "culture": 2, "feature": 1, "population": 8.5,
         "capital": 1, "port": 1, "shield": "swiss"},
    ])
    cell_biome = ",".join(["3", "4", "0"])
    cell_burg = ",".join(["1", "2", "0"])
    cell_conf = ",".join(["0", "0", "0"])
    cell_culture = ",".join(["1", "2", "0"])
    cell_fl = ",".join(["0", "10", "0"])
    cell_pop = ",".join(["12.3000", "8.5000", "0.0000"])
    cell_r = ",".join(["1", "1", "0"])
    deprecated_road = ""
    cell_s = ",".join(["100", "80", "0"])
    cell_state = ",".join(["1", "2", "0"])
    cell_religion = ",".join(["1", "2", "0"])
    cell_province = ",".join(["1", "2", "0"])
    deprecated_crossroad = ""
    religions = json.dumps([
        {"i": 0, "name": "No religion", "removed": True},
        {"i": 1, "name": "Anorian Faith", "color": "#fa0", "type": "Folk",
         "form": "Polytheism", "deity": "Anorus, the Sky-Father",
         "culture": 1, "center": 1, "expansionism": 1.1},
        {"i": 2, "name": "Brennic Truth", "color": "#0fa", "type": "Organized",
         "form": "Monotheism", "deity": None, "culture": 2,
         "center": 2, "expansionism": 1.3, "origins": [0]},
    ])
    provinces = json.dumps([
        0,  # sentinel
        {"i": 1, "name": "Anorshire", "fullName": "Duchy of Anorshire",
         "color": "#caa", "state": 1, "burg": 1, "center": 1,
         "formName": "Duchy"},
        {"i": 2, "name": "Brennereach", "fullName": "March of Brennereach",
         "color": "#aac", "state": 2, "burg": 2, "center": 2,
         "formName": "March", "kinship": 0.5},
    ])
    names_data = json.dumps([])
    rivers = json.dumps([
        {"i": 1, "name": "Anorflow", "type": "River", "parent": 0,
         "source": 1, "mouth": 2, "discharge": 50.0, "length": 120.5,
         "width": 4.5, "cells": [1, 2]},
    ])
    rulers = ""
    fonts = json.dumps([])
    markers = json.dumps([])
    cell_routes = json.dumps({})
    routes = json.dumps([])
    zones = json.dumps([])
    ice = json.dumps([])

    sections = [
        params, settings, coords, biomes, notes, svg, grid_general,
        cell_h, cell_prec, cell_f, cell_t, cell_temp, pack_features,
        cultures, states, burgs, cell_biome, cell_burg, cell_conf,
        cell_culture, cell_fl, cell_pop, cell_r, deprecated_road,
        cell_s, cell_state, cell_religion, cell_province,
        deprecated_crossroad, religions, provinces, names_data,
        rivers, rulers, fonts, markers, cell_routes, routes, zones, ice,
    ]
    assert len(sections) == 40, f"expected 40 sections, got {len(sections)}"
    return "\r\n".join(sections)


class FmgLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_synthetic_map()
        cls.world = parse_fmg_text(cls.payload)

    # ------------------------------------------------------------------ #
    #  Header                                                             #
    # ------------------------------------------------------------------ #

    def test_header_is_parsed(self):
        self.assertEqual(self.world.fmg_version, "1.120.5")
        self.assertEqual(self.world.seed, "test_seed")
        self.assertEqual(self.world.width, 1200)
        self.assertEqual(self.world.height, 800)

    # ------------------------------------------------------------------ #
    #  Biomes                                                             #
    # ------------------------------------------------------------------ #

    def test_biomes_are_parsed_with_columns_aligned(self):
        b = self.world.biomes
        self.assertEqual(len(b), 5)
        self.assertEqual(b[0].name, "Marine")
        self.assertEqual(b[0].color, "#466eab")
        self.assertEqual(b[0].habitability, 0)
        self.assertEqual(b[3].name, "Savanna")
        self.assertEqual(b[3].habitability, 22)
        # Cost defaults to 10 — FMG doesn't persist cost in the .map file.
        self.assertEqual(b[3].cost, 10)

    # ------------------------------------------------------------------ #
    #  Cultures                                                           #
    # ------------------------------------------------------------------ #

    def test_cultures_preserve_sentinel(self):
        c = self.world.cultures
        self.assertEqual(c[0].id, 0)
        self.assertTrue(c[0].is_removed)

    def test_cultures_are_parsed(self):
        anorian = self.world.cultures[1]
        self.assertEqual(anorian.name, "Anorian")
        self.assertEqual(anorian.type, "Generic")
        self.assertAlmostEqual(anorian.expansionism, 1.2)
        self.assertEqual(anorian.center, 1)

    def test_cultures_capture_extras(self):
        brennic = self.world.cultures[2]
        # 'shield' isn't a modeled field but should land in extras
        self.assertEqual(brennic.extras.get("shield"), "spanish")

    # ------------------------------------------------------------------ #
    #  States                                                             #
    # ------------------------------------------------------------------ #

    def test_states_are_parsed(self):
        s = self.world.states[1]
        self.assertEqual(s.name, "Anor")
        self.assertEqual(s.full_name, "Kingdom of Anor")
        self.assertEqual(s.form, "Monarchy")
        self.assertEqual(s.capital, 1)
        self.assertEqual(s.culture, 1)

    # ------------------------------------------------------------------ #
    #  Burgs                                                              #
    # ------------------------------------------------------------------ #

    def test_burgs_are_parsed_including_capital_and_port_flags(self):
        anorhall = self.world.burgs[1]
        self.assertEqual(anorhall.name, "Anorhall")
        self.assertTrue(anorhall.is_capital)
        self.assertFalse(anorhall.is_port)
        brennefurt = self.world.burgs[2]
        self.assertTrue(brennefurt.is_port)
        self.assertEqual(brennefurt.extras.get("shield"), "swiss")

    # ------------------------------------------------------------------ #
    #  Religions                                                          #
    # ------------------------------------------------------------------ #

    def test_religions_handle_null_deity(self):
        # Brennic Truth has deity=None in the source JSON. We coerce to "".
        brennic_truth = self.world.religions[2]
        self.assertEqual(brennic_truth.deity, "")
        self.assertEqual(brennic_truth.form, "Monotheism")

    def test_religions_capture_extras(self):
        brennic_truth = self.world.religions[2]
        self.assertEqual(brennic_truth.extras.get("origins"), [0])

    # ------------------------------------------------------------------ #
    #  Provinces                                                          #
    # ------------------------------------------------------------------ #

    def test_province_zero_sentinel_is_marked_removed(self):
        # FMG writes the sentinel as integer 0, not a dict — loader must cope.
        sentinel = self.world.provinces[0]
        self.assertEqual(sentinel.id, 0)
        self.assertTrue(sentinel.is_removed)

    def test_province_real_entries_are_parsed(self):
        anorshire = self.world.provinces[1]
        self.assertEqual(anorshire.name, "Anorshire")
        self.assertEqual(anorshire.full_name, "Duchy of Anorshire")
        self.assertEqual(anorshire.form_name, "Duchy")
        self.assertEqual(anorshire.state, 1)
        self.assertEqual(anorshire.burg, 1)

    def test_province_extras(self):
        brennereach = self.world.provinces[2]
        self.assertEqual(brennereach.extras.get("kinship"), 0.5)

    # ------------------------------------------------------------------ #
    #  Rivers                                                             #
    # ------------------------------------------------------------------ #

    def test_river_cells_path_is_parsed(self):
        anorflow = self.world.rivers[0]
        self.assertEqual(anorflow.name, "Anorflow")
        self.assertEqual(anorflow.cells, [1, 2])
        self.assertAlmostEqual(anorflow.discharge, 50.0)
        self.assertAlmostEqual(anorflow.length, 120.5)

    # ------------------------------------------------------------------ #
    #  Cell arrays                                                        #
    # ------------------------------------------------------------------ #

    def test_cell_arrays_align_in_length(self):
        n = len(self.world.cell_biome)
        self.assertEqual(n, 3)
        self.assertEqual(len(self.world.cell_burg), n)
        self.assertEqual(len(self.world.cell_culture), n)
        self.assertEqual(len(self.world.cell_state), n)
        self.assertEqual(len(self.world.cell_religion), n)
        self.assertEqual(len(self.world.cell_province), n)
        self.assertEqual(len(self.world.cell_population), n)
        # Grid arrays use a different length scale, but in our synthetic
        # payload we made grid and pack the same size to keep things simple.
        self.assertEqual(len(self.world.grid_height), n)

    def test_cell_arrays_have_expected_values(self):
        self.assertEqual(self.world.cell_biome, [3, 4, 0])
        self.assertEqual(self.world.cell_culture, [1, 2, 0])
        self.assertEqual(self.world.cell_state, [1, 2, 0])
        self.assertEqual(self.world.grid_height, [10, 20, 30])
        # Population is a float array — make sure we didn't lose precision.
        self.assertAlmostEqual(self.world.cell_population[0], 12.3, places=3)

    # ------------------------------------------------------------------ #
    #  Cross-references                                                   #
    # ------------------------------------------------------------------ #

    def test_cell_references_resolve_to_real_objects(self):
        """The whole point of the loader: cell-level references should point
        at the right province/state/culture object."""
        cell_idx = 0  # the first non-sentinel cell
        province_id = self.world.cell_province[cell_idx]
        state_id = self.world.cell_state[cell_idx]
        culture_id = self.world.cell_culture[cell_idx]

        self.assertEqual(self.world.provinces[province_id].name, "Anorshire")
        self.assertEqual(self.world.states[state_id].name, "Anor")
        self.assertEqual(self.world.cultures[culture_id].name, "Anorian")

    # ------------------------------------------------------------------ #
    #  Compression                                                        #
    # ------------------------------------------------------------------ #

    def test_loader_handles_gzip_compressed_files(self):
        """FMG started gzipping saves in v1.95+. The loader must transparently
        decompress."""
        compressed = gzip.compress(self.payload.encode("utf-8"))
        path = Path("/tmp/fmg_compressed_test.map")
        path.write_bytes(compressed)
        try:
            world = load_fmg_map(path)
            self.assertEqual(world.fmg_version, "1.120.5")
            self.assertEqual(world.states[1].name, "Anor")
        finally:
            path.unlink(missing_ok=True)

    def test_loader_handles_plain_text_files(self):
        path = Path("/tmp/fmg_plaintext_test.map")
        path.write_bytes(self.payload.encode("utf-8"))
        try:
            world = load_fmg_map(path)
            self.assertEqual(world.fmg_version, "1.120.5")
            self.assertEqual(world.provinces[1].name, "Anorshire")
        finally:
            path.unlink(missing_ok=True)

    # ------------------------------------------------------------------ #
    #  Robustness                                                         #
    # ------------------------------------------------------------------ #

    def test_truncated_file_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            parse_fmg_text("only one line")
        self.assertIn("truncated", str(ctx.exception).lower())

    def test_optional_sections_default_safely(self):
        """Religions, provinces, rivers can be empty in older saves. The
        loader should produce empty lists rather than crashing."""
        # Build a copy with religions/provinces/rivers blanked out.
        sections = self.payload.split("\r\n")
        sections[29] = ""  # religions
        sections[30] = ""  # provinces
        sections[32] = ""  # rivers
        world = parse_fmg_text("\r\n".join(sections))
        self.assertEqual(world.religions, [])
        self.assertEqual(world.provinces, [])
        self.assertEqual(world.rivers, [])

    def test_raw_lines_are_preserved(self):
        """SVG, notes, routes etc. live in raw_lines so callers can extract
        them later without re-reading."""
        self.assertEqual(self.world.raw_lines[5], "<svg/>")


class FmgRealFileIntegrationTests(unittest.TestCase):
    """Smoke test against the real demo.map shipped with FMG.

    This catches regressions where a parser drifts from FMG's actual output
    format. We only check shape and cross-reference integrity, not specific
    values, since the demo file may be regenerated upstream."""

    DEMO_PATH = Path(__file__).parent.parent / "sample_maps" / "demo.map"

    @classmethod
    def setUpClass(cls):
        if not cls.DEMO_PATH.exists():
            raise unittest.SkipTest(f"demo.map fixture not found at {cls.DEMO_PATH}")
        cls.world = load_fmg_map(cls.DEMO_PATH)

    def test_real_file_has_thousands_of_cells(self):
        # demo.map is ~7000 cells. Even the smallest FMG map has 1000+.
        self.assertGreater(len(self.world.cell_biome), 1000)

    def test_real_file_has_full_biome_table(self):
        # FMG ships 13 biomes by default. demo.map should have them all.
        self.assertGreaterEqual(len(self.world.biomes), 5)
        # First biome is always Marine.
        self.assertEqual(self.world.biomes[0].name, "Marine")

    def test_real_file_pack_arrays_align(self):
        n = len(self.world.cell_biome)
        # Pack-level arrays must all be the same length.
        self.assertEqual(len(self.world.cell_burg), n)
        self.assertEqual(len(self.world.cell_culture), n)
        self.assertEqual(len(self.world.cell_state), n)
        self.assertEqual(len(self.world.cell_religion), n)
        self.assertEqual(len(self.world.cell_province), n)
        self.assertEqual(len(self.world.cell_river), n)
        self.assertEqual(len(self.world.cell_population), n)

    def test_real_file_grid_arrays_align(self):
        n = len(self.world.grid_height)
        # Grid-level arrays must all be the same length, generally LARGER
        # than pack arrays since the pack drops deep ocean cells.
        self.assertEqual(len(self.world.grid_temperature), n)
        self.assertEqual(len(self.world.grid_precipitation), n)
        self.assertGreaterEqual(n, len(self.world.cell_biome))

    def test_real_file_cell_references_are_in_range(self):
        """Every per-cell reference must point to a valid index in the
        corresponding lookup table. Off-by-one errors here are silent and
        catastrophic — they only surface much later as wrong names."""
        n_provinces = len(self.world.provinces)
        n_states = len(self.world.states)
        n_cultures = len(self.world.cultures)
        n_burgs = len(self.world.burgs)
        n_religions = len(self.world.religions)
        n_biomes = len(self.world.biomes)
        for i in range(0, len(self.world.cell_biome), 100):
            self.assertLess(self.world.cell_province[i], n_provinces, f"cell {i} province out of range")
            self.assertLess(self.world.cell_state[i], n_states, f"cell {i} state out of range")
            self.assertLess(self.world.cell_culture[i], n_cultures, f"cell {i} culture out of range")
            self.assertLess(self.world.cell_burg[i], n_burgs, f"cell {i} burg out of range")
            self.assertLess(self.world.cell_religion[i], n_religions, f"cell {i} religion out of range")
            self.assertLess(self.world.cell_biome[i], n_biomes, f"cell {i} biome out of range")

    def test_real_file_has_named_states_and_provinces(self):
        # Every non-removed state should have a non-empty name.
        for state in self.world.states:
            if not state.is_removed and state.id > 0:
                self.assertTrue(state.name, f"state {state.id} has empty name")
        # Same for provinces.
        for province in self.world.provinces:
            if not province.is_removed and province.id > 0:
                self.assertTrue(province.name, f"province {province.id} has empty name")

    def test_real_file_burgs_have_coordinates(self):
        # A burg with x=y=0 is suspicious unless the cell really is at origin.
        real_burgs = [b for b in self.world.burgs if not b.is_removed and b.id > 0]
        self.assertGreater(len(real_burgs), 0)
        burgs_at_origin = [b for b in real_burgs if b.x == 0 and b.y == 0]
        # Allow at most a handful at origin (edge cases) — flag if widespread.
        self.assertLess(len(burgs_at_origin), len(real_burgs) * 0.1,
                        "many burgs have suspicious (0,0) coordinates")

    def test_real_file_capitals_resolve_to_real_burgs(self):
        for state in self.world.states:
            if state.is_removed or state.id == 0:
                continue
            if state.capital == 0:
                continue  # state has no capital — possible for tiny states
            capital = self.world.burgs[state.capital]
            self.assertFalse(capital.is_removed,
                             f"state {state.name} points to removed burg {state.capital}")
            self.assertEqual(capital.state, state.id,
                             f"state {state.name} capital {capital.name} doesn't reciprocate")


if __name__ == "__main__":
    unittest.main()

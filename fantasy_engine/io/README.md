# FMG Bridge — replacing Python world generation with Azgaar's FMG

This package replaces the procedural world generation we were building in
Python (`fantasy_engine/world/geography.py`, `provinces.py`, the cartographer,
the Flask viewer) with Azgaar's [Fantasy Map Generator (FMG)][fmg]. FMG generates
the map; this Python package loads FMG's output so your simulation layer can
consume it.

[fmg]: https://github.com/Azgaar/Fantasy-Map-Generator

## The new workflow

1. Open FMG. Either:
   - **Hosted (recommended for now):** [azgaar.github.io/Fantasy-Map-Generator](https://azgaar.github.io/Fantasy-Map-Generator) — zero setup.
   - **Local:** `npm install` + `npm run dev` from the FMG repo (needs Node.js).
2. Generate a world. Hit "New Map" until you like one. Use the in-app editors
   to tweak states, cultures, religions if you want.
3. **Save → Save Map** in FMG. You get a `.map` file (≈4 MB for a default-size
   world).
4. Load it in Python:

   ```python
   from fantasy_engine.io import load_fmg_map

   world = load_fmg_map("worlds/my_world.map")
   print(f"{world.n_pack_cells} cells, {len(world.states)} states, "
         f"{len(world.burgs)} burgs, {len(world.rivers)} rivers")
   ```

5. Run your simulation against the loaded `World` object.

## Quick CLI inspection

```
python -m fantasy_engine.io path/to/world.map
python -m fantasy_engine.io path/to/world.map --cell 5000
```

The first form prints a summary. The second prints everything FMG knows
about a specific pack cell.

## Data model

FMG keeps **two** cell graphs in every map:

- **pack** — sociopolitical data lives here (biome, state, culture,
  province, religion, burg, river, population, flow). The simulation should
  read from these.
- **grid** — raw terrain only (height, temperature, precipitation). Bigger
  than pack because it includes deep ocean cells the pack drops.

Pack and grid use **different cell indices**, so `world.grid_height[i]` does
not give you the height of pack cell `i`. FMG reconstructs the pack-to-grid
mapping at load time by re-running its `reGraph()` algorithm — we don't
ship a port of that, so terrain data is exposed at the grid level only.
For most simulation purposes this is fine: biomes already encode climate.

Lookup tables (`world.provinces`, `world.states`, `world.cultures`,
`world.religions`, `world.burgs`) all keep index 0 as a sentinel (the
"neutrals", "no province", "no religion" placeholder). Per-cell arrays use
`0` to mean "this cell has no province/state/etc.", which lines up. When
iterating *real* entities, filter on `id > 0` and `not is_removed`.

```python
real_states = [s for s in world.states if not s.is_removed and s.id > 0]
```

## Migration: what to delete from the old project

You picked Option 1 (replace Python world gen entirely). These files from
the previous Phase 16/17 work are now obsolete:

```
fantasy_engine/world/geography.py
fantasy_engine/world/provinces.py
fantasy_engine/visual/cartographer.py
fantasy_engine/runner/interactive_map.py
fantasy_engine/web/                       (whole folder)
web_main.py
procedural_world_main.py
tests/test_procedural_world.py
```

Anywhere in your simulation layer that used to import
`fantasy_engine.world.geography` or `fantasy_engine.world.provinces`,
switch to `fantasy_engine.io.World` and adapt. The mapping is roughly:

| Old                                           | New                                           |
|-----------------------------------------------|-----------------------------------------------|
| `GeographyResult.land_mask[i]`                | `world.grid_height[i] >= 20`                  |
| `GeographyResult.biome[i]`                    | `world.cell_biome[i]` (pack-level)            |
| `ProvinceMap.provinces[i].name`               | `world.provinces[i].name`                     |
| `ProvinceMap.provinces[i].neighbor_ids`       | not in FMG saves — derive from cell adjacency |
| `ProvinceMap.province_id_grid[y, x]`          | `world.cell_province[cell_at(x, y)]`          |

Note the last one: FMG cells are Voronoi polygons, not a regular pixel
grid. There's no `province_id_grid[y, x]` lookup. If your sim needs to
answer "what province contains this point on the map", you'll need a
spatial index. The cells' `(x, y)` centroids and the burg coordinates are
in `world.burgs[i].x/y`; cell centroids aren't directly saved but can be
extracted from FMG's embedded SVG (`world.raw_lines[5]`).

## Getting a real `.map` to test with

A real demo file is included at `sample_maps/demo.map` (4.2 MB, 7,462
pack cells, 21 states, 192 provinces, 754 burgs, 370 rivers, FMG version
1.112). The test suite uses it for integration testing. You can use it as
a stand-in until you generate your own.

## Running the tests

```
python -m unittest tests.test_fmg_loader
```

29 tests; should run in well under a second.

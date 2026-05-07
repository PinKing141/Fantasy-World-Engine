"""``python -m fantasy_engine.io <map-file>`` — quickly inspect an FMG save.

Useful for sanity-checking that a download from FMG parses cleanly before
plumbing it into a longer simulation pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fantasy_engine.io.fmg_loader import load_fmg_map


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect an FMG .map file (Azgaar's Fantasy Map Generator save format).",
    )
    parser.add_argument("path", type=Path, help="Path to a .map file (plain or gzipped)")
    parser.add_argument("-c", "--cell", type=int, default=None,
                        help="Print everything known about a specific pack cell")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1

    world = load_fmg_map(args.path)

    print(f"FMG version : {world.fmg_version}")
    print(f"Seed        : {world.seed}")
    print(f"Dimensions  : {world.width} x {world.height}")
    print()
    print(f"Pack cells  : {world.n_pack_cells:>6}  (simulation-relevant)")
    print(f"Grid cells  : {world.n_grid_cells:>6}  (raw terrain)")
    print(f"Biomes      : {len(world.biomes):>6}")
    print(f"Cultures    : {len(world.cultures):>6}  (incl. sentinel)")
    print(f"States      : {len(world.states):>6}  (incl. neutral land)")
    print(f"Provinces   : {len(world.provinces):>6}  (incl. sentinel)")
    print(f"Burgs       : {len(world.burgs):>6}  (incl. sentinel)")
    print(f"Religions   : {len(world.religions):>6}  (incl. no-religion)")
    print(f"Rivers      : {len(world.rivers):>6}")

    if args.cell is not None:
        i = args.cell
        if not (0 <= i < world.n_pack_cells):
            print(f"\nerror: cell index out of range (0..{world.n_pack_cells - 1})", file=sys.stderr)
            return 1
        print(f"\nPack cell #{i}:")
        print(f"  biome      = {world.biomes[world.cell_biome[i]].name}")
        if world.cell_state[i] > 0:
            s = world.states[world.cell_state[i]]
            print(f"  state      = {s.full_name or s.name} ({s.form})")
        if world.cell_culture[i] > 0:
            print(f"  culture    = {world.cultures[world.cell_culture[i]].name}")
        if world.cell_province[i] > 0:
            p = world.provinces[world.cell_province[i]]
            print(f"  province   = {p.full_name or p.name}")
        if world.cell_religion[i] > 0:
            print(f"  religion   = {world.religions[world.cell_religion[i]].name}")
        if world.cell_burg[i] > 0:
            b = world.burgs[world.cell_burg[i]]
            print(f"  burg       = {b.name} (pop {b.population:.1f}{', port' if b.is_port else ''}{', capital' if b.is_capital else ''})")
        print(f"  population = {world.cell_population[i]:.2f}")
        print(f"  flow       = {world.cell_flow[i]}")
        if world.cell_river[i] > 0:
            r = world.rivers[world.cell_river[i] - 1] if world.cell_river[i] - 1 < len(world.rivers) else None
            if r:
                print(f"  river      = {r.name} ({r.type})")

    return 0


if __name__ == "__main__":
    sys.exit(main())

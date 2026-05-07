"""Standalone entry point for the procedural world map.

Usage:
    python -m fantasy_engine.procedural_world_main --seed 4242
    python -m fantasy_engine.procedural_world_main --seed 4242 --interactive
    python -m fantasy_engine.procedural_world_main --width 384 --height 240 --export world.png

You can also wire this into the existing main.py via the new --procedural-map
and --interactive-map flags; see main.py for the integrated version.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from fantasy_engine.visual.cartographer import CartographyOptions, RenderInputs, render_world
from fantasy_engine.world.geography import GeographyConfig, generate_geography
from fantasy_engine.world.provinces import build_province_map


def export_static_map(
    *,
    seed: int,
    width: int,
    height: int,
    land_fraction: float,
    output_path: Path,
    show_borders: bool,
) -> None:
    """Generate a procedural world and write it to a high-res PNG."""
    config = GeographyConfig(width=width, height=height, seed=seed, land_fraction=land_fraction)
    print(f"Generating world (seed={seed}, size={width}x{height})...")
    start = time.time()
    geography = generate_geography(config)
    print(f"  geography: {time.time() - start:.2f}s, {len(geography.landmasses)} landmasses, sea_level={geography.sea_level:+.3f}")

    start = time.time()
    provinces = build_province_map(geography)
    print(f"  provinces: {time.time() - start:.2f}s, {len(provinces.provinces)} provinces")

    rgb = render_world(RenderInputs(
        geography=geography,
        provinces=provinces,
        options=CartographyOptions(show_province_borders=show_borders),
    ))

    figure = Figure(figsize=(width / 96, height / 96), dpi=192, constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(1, 1, 1)
    axes.imshow(rgb)
    axes.set_axis_off()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=192, facecolor="#101418")
    print(f"  saved to {output_path}")


def run_interactive(*, seed: int, width: int, height: int, land_fraction: float) -> None:
    """Open the pygame interactive map runtime."""
    from fantasy_engine.runner.interactive_map import run_interactive_map

    config = GeographyConfig(width=width, height=height, seed=seed, land_fraction=land_fraction)
    run_interactive_map(config=config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Procedural fantasy world map generator and viewer.")
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--width", type=int, default=384, help="Map width in cells.")
    parser.add_argument("--height", type=int, default=240, help="Map height in cells.")
    parser.add_argument("--land-fraction", type=float, default=0.42, help="Target land:water ratio (0..1).")
    parser.add_argument("--export", type=Path, default=None, help="Write a static PNG to this path.")
    parser.add_argument("--interactive", action="store_true", help="Open the interactive pygame viewer.")
    parser.add_argument("--no-borders", action="store_true", help="Suppress province borders in the static export.")
    args = parser.parse_args()

    if not args.export and not args.interactive:
        args.interactive = True

    if args.export is not None:
        export_static_map(
            seed=args.seed,
            width=args.width,
            height=args.height,
            land_fraction=args.land_fraction,
            output_path=args.export,
            show_borders=not args.no_borders,
        )

    if args.interactive:
        run_interactive(
            seed=args.seed,
            width=args.width,
            height=args.height,
            land_fraction=args.land_fraction,
        )


if __name__ == "__main__":
    main()

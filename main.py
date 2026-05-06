from __future__ import annotations

import argparse

from fantasy_engine.runner import SimulationController, run_with_rich
from fantasy_engine.visual import RichDashboardRenderer
from fantasy_engine.visual.dashboard import make_dashboard_snapshot
from fantasy_engine.world.world import World


def run_demo(
    seed: int = 4242,
    years: int | None = None,
    *,
    watch: bool = False,
    pace_seconds: float = 0.0,
    clear_between_years: bool = False,
    honor_autopause: bool = True,
) -> None:
    world = World(seed=seed, num_civilizations=4)
    controller = SimulationController(world, initial_speed=max(0.25, pace_seconds if pace_seconds > 0.0 else 1.0))
    renderer = RichDashboardRenderer()

    if watch:
        run_with_rich(
            controller,
            renderer,
            years=years,
            honor_autopause=honor_autopause,
            clear_between_frames=clear_between_years,
        )
        return

    opening_result = controller.current_result()
    renderer.render_run_start(seed=seed, years=years, snapshot=make_dashboard_snapshot(opening_result))
    previous_result = None
    target_year = None if years is None else world.year + years
    try:
        while target_year is None or world.year < target_year:
            step_result = controller.step()
            snapshot = make_dashboard_snapshot(step_result, previous_step_result=previous_result)
            if step_result.year_boundary:
                renderer.render_year_close(year=step_result.year, snapshot=snapshot)
            previous_result = step_result
    except KeyboardInterrupt:
        renderer.console.print("\nRun interrupted by user.")

    renderer.render_run_end(world.history.cause_effect_pairs()[-8:])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fantasy Engine terminal demo.")
    parser.add_argument("--seed", type=int, default=4242, help="Seed used for the deterministic simulation.")
    parser.add_argument(
        "--years",
        type=int,
        default=None,
        help="How many years to simulate. Omit to run until you stop it.",
    )
    parser.add_argument(
        "--watch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show the run as a paced terminal watch mode instead of dumping everything at once.",
    )
    parser.add_argument(
        "--pace-seconds",
        type=float,
        default=1.0,
        help="Target ticks per second in watch mode.",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Keep earlier yearly frames in the terminal instead of clearing between them.",
    )
    parser.add_argument(
        "--autopause",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop the Rich watch runner when a curated autopause event fires.",
    )
    args = parser.parse_args()
    run_demo(
        seed=args.seed,
        years=args.years,
        watch=args.watch,
        pace_seconds=args.pace_seconds,
        clear_between_years=not args.no_clear,
        honor_autopause=args.autopause,
    )


if __name__ == "__main__":
    main()
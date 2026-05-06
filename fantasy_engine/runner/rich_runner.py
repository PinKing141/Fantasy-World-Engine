from __future__ import annotations

import time

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from fantasy_engine.runner.controller import SimulationController
from fantasy_engine.visual.dashboard import make_dashboard_snapshot
from fantasy_engine.visual.rich_renderer import RichDashboardRenderer

try:
    import msvcrt
except ImportError:  # pragma: no cover - Windows terminals are the current target.
    msvcrt = None


POLL_INTERVAL_SECONDS = 0.05


def _poll_control() -> str | None:
    if msvcrt is None or not msvcrt.kbhit():
        return None

    character = msvcrt.getwch()
    if character in {"\x00", "\xe0"}:
        extended = msvcrt.getwch()
        if extended == "H":
            return "select_prev_court"
        if extended == "P":
            return "select_next_court"
        if extended == "K":
            return "slower"
        if extended == "M":
            return "faster"
        return None

    normalized = character.lower()
    if normalized == " ":
        return "toggle_pause"
    if normalized == "[":
        return "select_prev_event"
    if normalized == "]":
        return "select_next_event"
    if normalized == "s":
        return "step"
    if normalized == "e":
        return "skip_major"
    if normalized == "b":
        return "toggle_biography"
    if normalized == "q":
        return "quit"
    return None


def _compose_runtime_frame(
    renderer: RichDashboardRenderer,
    *,
    title: str,
    snapshot,
    paused: bool,
    speed: float,
    status_message: str,
    selected_actor_index: int = 0,
    selected_event_index: int = 0,
    biography_visible: bool = False,
    rule_style: str = "bold green",
) -> Group:
    controls_lines = [
        "[space] pause/resume  [<-] slower  [->] faster",
        "[up]/[down] select actor  [b] biography",
        "[ and ] select event",
        "[s] step  [e] skip major  [q] quit",
    ]
    state_line = f"State: {'PAUSED' if paused else 'RUNNING'} | Speed: {speed:g}x"
    panel_lines = [state_line, *controls_lines]
    if status_message:
        panel_lines.append(f"Status: {status_message}")
    return Group(
        renderer.compose_frame(
            title=title,
            snapshot=snapshot,
            rule_style=rule_style,
            selected_actor_index=selected_actor_index,
            selected_event_index=selected_event_index,
            biography_visible=biography_visible,
        ),
        Panel(Text("\n".join(panel_lines)), title="Controls", border_style="blue"),
    )


def _step_once(controller: SimulationController, *, pause_after_step: bool = False):
    result = controller.step()
    if pause_after_step:
        controller.paused = True
    return result


def _handle_control(
    command: str,
    controller: SimulationController,
    *,
    target_year: int | None,
):
    if command == "toggle_pause":
        paused = controller.toggle_pause()
        return None, ("Paused" if paused else "Resumed"), False
    if command == "faster":
        return None, f"Speed set to {controller.faster():g}x", False
    if command == "slower":
        return None, f"Speed set to {controller.slower():g}x", False
    if command == "step":
        return _step_once(controller, pause_after_step=True), "Stepped one season", False
    if command == "skip_major":
        controller.paused = True
        return controller.skip_to_next_major_event(stop_year=target_year), "Skipped to next major event", False
    if command == "quit":
        controller.paused = True
        return None, "Quit requested", True
    return None, "", False


def run_with_rich(
    controller: SimulationController,
    renderer: RichDashboardRenderer,
    *,
    years: int | None,
    honor_autopause: bool = True,
    clear_between_frames: bool = True,
    refresh_per_second: int = 4,
) -> None:
    current_result = controller.current_result()
    previous_result = None
    current_snapshot = make_dashboard_snapshot(current_result)
    status_message = "Interactive watch mode ready"
    frame = _compose_runtime_frame(
        renderer,
        title=f"Fantasy Engine vertical slice | seed={controller.world.seed} | years={years if years is not None else 'open-ended'}",
        snapshot=current_snapshot,
        paused=controller.paused,
        speed=controller.speed,
        status_message=status_message,
        selected_actor_index=0,
        selected_event_index=0,
        biography_visible=False,
        rule_style="bold cyan",
    )

    with Live(frame, console=renderer.console, refresh_per_second=refresh_per_second, auto_refresh=False, transient=False) as live:
        live.refresh()
        target_year = None if years is None else controller.world.year + years
        next_tick_at = time.monotonic()
        quit_requested = False
        needs_refresh = False
        selected_actor_index = 0
        selected_event_index = 0
        biography_visible = False

        while (target_year is None or controller.world.year < target_year) and not quit_requested:
            command = _poll_control()
            if command is not None:
                step_result = None
                control_status = ""
                if command == "select_next_court":
                    if current_snapshot.visible_actors:
                        selected_actor_index = (selected_actor_index + 1) % len(current_snapshot.visible_actors)
                        selected_actor = current_snapshot.visible_actors[selected_actor_index]
                        status_message = f"Selected {selected_actor.actor_name} ({selected_actor.relation_label})"
                        needs_refresh = True
                elif command == "select_prev_court":
                    if current_snapshot.visible_actors:
                        selected_actor_index = (selected_actor_index - 1) % len(current_snapshot.visible_actors)
                        selected_actor = current_snapshot.visible_actors[selected_actor_index]
                        status_message = f"Selected {selected_actor.actor_name} ({selected_actor.relation_label})"
                        needs_refresh = True
                elif command == "select_next_event":
                    if current_snapshot.key_events:
                        selected_event_index = (selected_event_index + 1) % len(current_snapshot.key_events)
                        status_message = f"Selected event {selected_event_index + 1}/{len(current_snapshot.key_events)}"
                        needs_refresh = True
                elif command == "select_prev_event":
                    if current_snapshot.key_events:
                        selected_event_index = (selected_event_index - 1) % len(current_snapshot.key_events)
                        status_message = f"Selected event {selected_event_index + 1}/{len(current_snapshot.key_events)}"
                        needs_refresh = True
                elif command == "toggle_biography":
                    biography_visible = not biography_visible
                    control_status = "Biography open" if biography_visible else "Biography hidden"
                    needs_refresh = True
                else:
                    step_result, control_status, quit_requested = _handle_control(
                        command,
                        controller,
                        target_year=target_year,
                    )
                if control_status:
                    status_message = control_status
                if step_result is not None:
                    current_result = step_result
                    current_snapshot = make_dashboard_snapshot(step_result, previous_step_result=previous_result)
                    previous_result = step_result
                    if current_snapshot.visible_actors:
                        selected_actor_index %= len(current_snapshot.visible_actors)
                    else:
                        selected_actor_index = 0
                    if current_snapshot.key_events:
                        selected_event_index %= len(current_snapshot.key_events)
                    else:
                        selected_event_index = 0
                    if step_result.should_pause and honor_autopause:
                        controller.paused = True
                        status_message = f"Autopause: {step_result.pause_reason}"
                    needs_refresh = True
                next_tick_at = time.monotonic() + (1.0 / controller.speed if not controller.paused else POLL_INTERVAL_SECONDS)
                if command in {"toggle_pause", "faster", "slower", "quit", "toggle_biography"}:
                    needs_refresh = True

            if (target_year is not None and controller.world.year >= target_year) or quit_requested:
                break

            if not controller.paused and time.monotonic() >= next_tick_at:
                step_result = controller.step()
                current_result = step_result
                current_snapshot = make_dashboard_snapshot(step_result, previous_step_result=previous_result)
                previous_result = step_result
                if step_result.should_pause and honor_autopause:
                    controller.paused = True
                    status_message = f"Autopause: {step_result.pause_reason}"
                else:
                    status_message = ""
                next_tick_at = time.monotonic() + (1.0 / controller.speed)
                needs_refresh = True

            if needs_refresh:
                frame_title = f"Year {current_result.year} · {current_result.season.title()} · Tick {current_result.tick}"
                if current_result.should_pause and controller.paused:
                    frame_title = f"{frame_title} · AUTOPAUSE"

                live.update(
                    _compose_runtime_frame(
                        renderer,
                        title=frame_title,
                        snapshot=current_snapshot,
                        paused=controller.paused,
                        speed=controller.speed,
                        status_message=status_message,
                        selected_actor_index=selected_actor_index,
                        selected_event_index=selected_event_index,
                        biography_visible=biography_visible,
                    ),
                    refresh=True,
                )
                needs_refresh = False
            time.sleep(POLL_INTERVAL_SECONDS)

        live.console.print(
            _compose_runtime_frame(
                renderer,
                title="Run complete",
                snapshot=make_dashboard_snapshot(previous_result or current_result),
                paused=controller.paused,
                speed=controller.speed,
                status_message=status_message if quit_requested else "Run finished",
                selected_actor_index=selected_actor_index,
                selected_event_index=selected_event_index,
                biography_visible=biography_visible,
                rule_style="bold cyan",
            )
        )
        renderer.render_run_end(
            controller.world.history.cause_effect_pairs()[-8:],
            controller.world.recent_legend_summaries(limit=3),
        )
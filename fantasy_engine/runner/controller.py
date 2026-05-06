from __future__ import annotations

from collections.abc import Sequence

from fantasy_engine.core.engine import SeasonStepResult


AUTOPAUSE_ALWAYS = frozenset(
    {
        "famine",
        "faction_coup",
        "war_declaration",
        "route_severed",
    }
)

AUTOPAUSE_AT_LOW_SPEED = frozenset(
    {
        "succession",
        "battle",
        "culture_split",
        "migration",
    }
)

LOW_SPEED_THRESHOLD = 2.0
DEFAULT_SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0, 16.0, 64.0)


def compute_autopause(step_result: SeasonStepResult, speed: float) -> tuple[bool, str]:
    for event in step_result.events:
        if event.event_type in AUTOPAUSE_ALWAYS:
            return True, f"{event.label} · {event.civilization}"
        if event.event_type in AUTOPAUSE_AT_LOW_SPEED and speed <= LOW_SPEED_THRESHOLD:
            return True, f"{event.label} · {event.civilization}"
    return False, ""


class SimulationController:
    def __init__(
        self,
        world,
        *,
        speeds: Sequence[float] | None = None,
        initial_speed: float = 1.0,
    ) -> None:
        self.world = world
        self.paused = False
        self.speeds = tuple(speeds or DEFAULT_SPEEDS)
        try:
            self._speed_index = self.speeds.index(initial_speed)
        except ValueError:
            self._speed_index = min(range(len(self.speeds)), key=lambda index: abs(self.speeds[index] - initial_speed))
        self.speed = self.speeds[self._speed_index]

    def current_result(self) -> SeasonStepResult:
        return self.world.snapshot_current_state()

    def step(self) -> SeasonStepResult:
        result = self.world.advance_season()
        should_pause, pause_reason = compute_autopause(result, self.speed)
        result.should_pause = should_pause
        result.pause_reason = pause_reason
        return result

    def faster(self) -> float:
        self._speed_index = min(len(self.speeds) - 1, self._speed_index + 1)
        self.speed = self.speeds[self._speed_index]
        return self.speed

    def slower(self) -> float:
        self._speed_index = max(0, self._speed_index - 1)
        self.speed = self.speeds[self._speed_index]
        return self.speed

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def skip_to_next_major_event(self, *, stop_year: int | None = None) -> SeasonStepResult:
        while True:
            current_year = getattr(self.world, "year", self.world.snapshot_current_state().world_year)
            if stop_year is not None and current_year >= stop_year:
                return self.world.snapshot_current_state()
            result = self.step()
            if result.should_pause or result.major_events:
                return result
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


def load_event_types() -> dict[str, str]:
    event_file = Path(__file__).resolve().parents[1] / "data" / "event_types.json"
    with event_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


EVENT_TYPES = load_event_types()


@dataclass(slots=True)
class HistoryEvent:
    year: int
    season: str
    event_type: str
    civilization: str
    details: str
    severity: str = "normal"
    other_civilization: str | None = None
    caused_by: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str | None = None

    @property
    def label(self) -> str:
        return EVENT_TYPES.get(self.event_type, self.event_type.replace("_", " ").title())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "year": self.year,
            "season": self.season,
            "event_type": self.event_type,
            "civilization": self.civilization,
            "details": self.details,
            "severity": self.severity,
            "other_civilization": self.other_civilization,
            "caused_by": self.caused_by,
            "data": self.data,
        }


class HistoryArchive:
    def __init__(self) -> None:
        self.events: list[HistoryEvent] = []
        self._by_type: dict[str, list[HistoryEvent]] = {}
        self._by_civilization: dict[str, list[HistoryEvent]] = {}
        self._cause_effect: list[tuple[str, str]] = []
        self._next_id = 1

    def record_event(self, event: HistoryEvent) -> HistoryEvent:
        if event.event_id is None:
            event.event_id = f"E{self._next_id:06d}"
            self._next_id += 1

        self.events.append(event)
        self._by_type.setdefault(event.event_type, []).append(event)
        self._by_civilization.setdefault(event.civilization, []).append(event)
        self._auto_link(event)
        return event

    def _auto_link(self, event: HistoryEvent) -> None:
        if event.caused_by:
            self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type in {"route_contested", "route_severed"} and event.other_civilization:
            war_events = self.get_recent_pair_events(
                event.civilization,
                event.other_civilization,
                event_types={"war_declaration", "battle"},
                years_back=2,
                current_year=event.year,
            )
            if war_events:
                event.caused_by = war_events[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "route_reopened" and event.other_civilization:
            peace_events = self.get_recent_pair_events(
                event.civilization,
                event.other_civilization,
                event_types={"diplomatic_peace"},
                years_back=2,
                current_year=event.year,
            )
            if peace_events:
                event.caused_by = peace_events[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "faction_coup":
            unrest = self.get_recent_events(event.civilization, "unrest", years_back=2, current_year=event.year)
            if unrest:
                event.caused_by = unrest[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "war_declaration":
            unrest = self.get_recent_events(event.civilization, "unrest", years_back=2, current_year=event.year)
            if unrest:
                event.caused_by = unrest[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "diplomatic_aid":
            shortages = self.get_recent_events(event.other_civilization, "food_shortage", years_back=1, current_year=event.year)
            if shortages:
                event.caused_by = shortages[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "trade_shipment":
            shortages = self.get_recent_events(event.other_civilization, "food_shortage", years_back=1, current_year=event.year)
            if shortages:
                event.caused_by = shortages[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "unrest":
            shortages = self.get_recent_events(event.civilization, "food_shortage", years_back=2, current_year=event.year)
            if shortages:
                event.caused_by = shortages[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "recovery":
            famines = self.get_recent_events(event.civilization, "famine", years_back=3, current_year=event.year)
            if famines:
                event.caused_by = famines[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))
            return

        if event.event_type == "succession":
            deaths = self.get_recent_events(event.civilization, "court_death", years_back=1, current_year=event.year)
            if deaths:
                event.caused_by = deaths[-1].event_id
                self._cause_effect.append((event.caused_by, event.event_id))

    def get_recent_events(
        self,
        civilization: str | None = None,
        event_type: str | None = None,
        years_back: int = 5,
        current_year: int | None = None,
    ) -> list[HistoryEvent]:
        if not self.events:
            return []

        effective_year = current_year if current_year is not None else self.events[-1].year
        results: list[HistoryEvent] = []
        for event in self.events:
            if civilization and event.civilization != civilization:
                continue
            if event_type and event.event_type != event_type:
                continue
            if event.year < effective_year - years_back:
                continue
            if event.year > effective_year:
                continue
            results.append(event)
        return results

    def get_recent_pair_events(
        self,
        civilization_a: str,
        civilization_b: str,
        *,
        event_types: set[str] | None = None,
        years_back: int = 5,
        current_year: int | None = None,
    ) -> list[HistoryEvent]:
        pair = {civilization_a, civilization_b}
        results: list[HistoryEvent] = []
        for event in self.get_recent_events(years_back=years_back, current_year=current_year):
            if event_types is not None and event.event_type not in event_types:
                continue
            participants = {event.civilization}
            if event.other_civilization is not None:
                participants.add(event.other_civilization)
            if pair.issubset(participants):
                results.append(event)
        return results

    def recent(self, limit: int = 10) -> list[HistoryEvent]:
        return self.events[-limit:]

    def cause_effect_pairs(self) -> list[tuple[str, str]]:
        return list(self._cause_effect)
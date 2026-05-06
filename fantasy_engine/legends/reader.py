from __future__ import annotations

from dataclasses import dataclass

from fantasy_engine.core.events import HistoryArchive, HistoryEvent


@dataclass(frozen=True, slots=True)
class LegendEntry:
    anchor_event_id: str
    event_ids: tuple[str, ...]
    title: str
    summary: str


class LegendsReader:
    def __init__(self, history: HistoryArchive) -> None:
        self.history = history

    def recent_legends(self, *, limit: int = 3) -> list[LegendEntry]:
        legends: list[LegendEntry] = []
        seen_paths: set[tuple[str, ...]] = set()
        for event in reversed(self.history.events):
            if len(legends) >= limit:
                break
            if event.event_id is None:
                continue
            if event.event_type in {"foundation", "annual_summary"}:
                continue

            entry = self.legend_for_event(event.event_id)
            if entry is None or len(entry.event_ids) < 2:
                continue
            if entry.event_ids in seen_paths:
                continue

            seen_paths.add(entry.event_ids)
            legends.append(entry)
        return legends

    def legend_for_event(self, event_id: str) -> LegendEntry | None:
        chain = self._chain_for_event(event_id)
        if not chain:
            return None

        anchor = chain[-1]
        event_ids = tuple(event.event_id for event in chain if event.event_id is not None)
        if not event_ids:
            return None

        title = f"{anchor.label} in {anchor.civilization}"
        return LegendEntry(
            anchor_event_id=event_ids[-1],
            event_ids=event_ids,
            title=title,
            summary=self._summarize_chain(chain),
        )

    def _chain_for_event(self, event_id: str) -> list[HistoryEvent]:
        chain: list[HistoryEvent] = []
        seen: set[str] = set()
        current_id: str | None = event_id
        while current_id and current_id not in seen:
            seen.add(current_id)
            event = self.history.event_by_id(current_id)
            if event is None:
                break
            chain.append(event)
            current_id = event.caused_by
        chain.reverse()
        return chain

    def _summarize_chain(self, chain: list[HistoryEvent]) -> str:
        if len(chain) == 1:
            event = chain[0]
            return f"Legend: {event.label} in {event.civilization}. {event.details}"

        first = self._event_stub(chain[0], include_place=True)
        last = self._event_stub(chain[-1], include_place=True)
        middle = [self._event_stub(event, include_place=False) for event in chain[1:-1]]

        if not middle:
            path_text = f"{first} led to {last}"
        elif len(middle) == 1:
            path_text = f"{first} led to {middle[0]}, and ended in {last}"
        else:
            path_text = f"{first} led to {', then '.join(middle)}, and ended in {last}"

        return f"Legend: {path_text}. {chain[-1].details}"

    def _event_stub(self, event: HistoryEvent, *, include_place: bool) -> str:
        if include_place:
            return f"{event.label} in {event.civilization}"
        return event.label
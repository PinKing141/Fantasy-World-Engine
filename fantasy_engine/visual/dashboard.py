from __future__ import annotations

from dataclasses import dataclass
from fantasy_engine.core.engine import AgentBioSnapshot, EventSnapshot, SeasonStepResult


@dataclass(frozen=True, slots=True)
class NeedsView:
    food: float
    safety: float
    belonging: float
    esteem: float


@dataclass(frozen=True, slots=True)
class RouteRow:
    civilization_a: str
    civilization_b: str
    distance: float
    effective_capacity: int
    capacity: int
    effective_risk: float
    state: str


@dataclass(frozen=True, slots=True)
class StatusRow:
    civilization: str
    culture_id: str
    population: int
    grain_stores: int
    food_stores: int
    weapons_stockpile: int
    supply_stockpile: int
    stability: float
    legitimacy: float
    unrest: float
    war_count: int
    contested_routes: int
    severed_routes: int


@dataclass(frozen=True, slots=True)
class CourtRow:
    changed: bool
    civilization: str
    culture_id: str
    ruler_name: str
    dynasty_name: str
    heir_name: str
    heir_agent_id: str
    general_name: str
    general_agent_id: str
    diplomat_name: str
    diplomat_agent_id: str
    heir_parent_name: str
    needs: NeedsView
    ruler_agent_id: str
    ruler_biography: AgentBioSnapshot | None
    heir_biography: AgentBioSnapshot | None
    general_biography: AgentBioSnapshot | None
    diplomat_biography: AgentBioSnapshot | None


@dataclass(frozen=True, slots=True)
class FactionRow:
    changed: bool
    civilization: str
    faction_name: str
    leader_name: str
    leader_agent_id: str
    dynasty_name: str
    pressure: float
    agenda: str
    needs: NeedsView
    biography: AgentBioSnapshot | None


@dataclass(frozen=True, slots=True)
class EventRow:
    summary: str
    context: str
    severity: str
    caused_by: tuple[str, ...] = ()
    led_to: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VisibleActorRow:
    actor_id: str
    actor_name: str
    section: str
    row_index: int
    relation_label: str
    biography: AgentBioSnapshot | None


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    route_rows: list[RouteRow]
    status_rows: list[StatusRow]
    court_rows: list[CourtRow]
    faction_rows: list[FactionRow]
    key_events: list[EventRow]
    visible_actors: list[VisibleActorRow]

def make_dashboard_snapshot(
    step_result: SeasonStepResult,
    *,
    previous_step_result: SeasonStepResult | None = None,
) -> DashboardSnapshot:
    previous_court_snapshot = _court_identity_map(previous_step_result) if previous_step_result is not None else None
    previous_faction_snapshot = _faction_identity_map(previous_step_result) if previous_step_result is not None else None
    route_rows = _route_rows(step_result)
    status_rows = _status_rows(step_result)
    court_rows = _court_rows(step_result, previous_snapshot=previous_court_snapshot)
    faction_rows = _faction_rows(step_result, previous_snapshot=previous_faction_snapshot)
    key_events = _key_events(step_result)
    return DashboardSnapshot(
        route_rows=route_rows,
        status_rows=status_rows,
        court_rows=court_rows,
        faction_rows=faction_rows,
        key_events=key_events,
        visible_actors=_visible_actors(court_rows, faction_rows),
    )


def _route_rows(step_result: SeasonStepResult) -> list[RouteRow]:
    return [
        RouteRow(
            civilization_a=route.civilization_a,
            civilization_b=route.civilization_b,
            distance=route.distance,
            effective_capacity=route.effective_capacity,
            capacity=route.capacity,
            effective_risk=route.effective_risk,
            state=route.state,
        )
        for route in step_result.active_routes
    ]


def _status_rows(step_result: SeasonStepResult) -> list[StatusRow]:
    return [
        StatusRow(
            civilization=civilization.name,
            culture_id=civilization.culture_id,
            population=civilization.population,
            grain_stores=civilization.grain_stores,
            food_stores=civilization.food_stores,
            weapons_stockpile=civilization.weapons_stockpile,
            supply_stockpile=civilization.supply_stockpile,
            stability=civilization.stability,
            legitimacy=civilization.legitimacy,
            unrest=civilization.unrest,
            war_count=len(civilization.at_war_with),
            contested_routes=civilization.contested_routes,
            severed_routes=civilization.severed_routes,
        )
        for civilization in step_result.civilization_snapshots
    ]


def _court_rows(
    step_result: SeasonStepResult,
    *,
    previous_snapshot: dict[str, tuple[str, str, str, str, str]] | None = None,
) -> list[CourtRow]:
    rows: list[CourtRow] = []
    for civilization in step_result.civilization_snapshots:
        current_snapshot = (
            civilization.culture_id,
            civilization.court.ruler_name,
            civilization.court.ruler_dynasty,
            civilization.court.heir_name or "none",
            civilization.court.heir_parent_id,
        )
        changed = previous_snapshot is not None and previous_snapshot.get(civilization.name) != current_snapshot
        rows.append(
            CourtRow(
                changed=changed,
                civilization=civilization.name,
                culture_id=civilization.culture_id,
                ruler_name=civilization.court.ruler_name,
                dynasty_name=civilization.court.ruler_dynasty,
                heir_name=civilization.court.heir_name or "none",
                heir_agent_id=civilization.court.heir_agent_id,
                general_name=civilization.court.general_name,
                general_agent_id=civilization.court.general_agent_id,
                diplomat_name=civilization.court.diplomat_name,
                diplomat_agent_id=civilization.court.diplomat_agent_id,
                heir_parent_name=civilization.court.heir_parent_name,
                needs=NeedsView(
                    food=civilization.court.ruler_needs.food,
                    safety=civilization.court.ruler_needs.safety,
                    belonging=civilization.court.ruler_needs.belonging,
                    esteem=civilization.court.ruler_needs.esteem,
                ),
                ruler_agent_id=civilization.court.ruler_agent_id,
                ruler_biography=civilization.court.ruler_bio,
                heir_biography=civilization.court.heir_bio,
                general_biography=civilization.court.general_bio,
                diplomat_biography=civilization.court.diplomat_bio,
            )
        )
    return rows


def _faction_rows(
    step_result: SeasonStepResult,
    *,
    previous_snapshot: dict[tuple[str, str], tuple[str, str, str]] | None = None,
) -> list[FactionRow]:
    rows: list[FactionRow] = []
    for civilization in step_result.civilization_snapshots:
        for faction in civilization.factions:
            current_snapshot = (
                faction.leader_name,
                faction.dynasty_name,
                faction.agenda,
            )
            changed = previous_snapshot is not None and previous_snapshot.get((civilization.name, faction.name)) != current_snapshot
            rows.append(
                FactionRow(
                    changed=changed,
                    civilization=civilization.name,
                    faction_name=faction.name,
                    leader_name=faction.leader_name,
                    leader_agent_id=faction.leader_agent_id,
                    dynasty_name=faction.dynasty_name,
                    pressure=faction.pressure,
                    agenda=faction.agenda,
                    needs=NeedsView(
                        food=faction.needs.food,
                        safety=faction.needs.safety,
                        belonging=faction.needs.belonging,
                        esteem=faction.needs.esteem,
                    ),
                    biography=faction.leader_bio,
                )
            )
    return rows


def _key_events(step_result: SeasonStepResult, *, limit: int = 6) -> list[EventRow]:
    if step_result.event_snapshots:
        notable_events = [event for event in step_result.event_snapshots if event.severity in {"major", "catastrophic"}]
    else:
        notable_events = [
            EventSnapshot(
                event_type=event.event_type,
                label=event.label,
                civilization=event.civilization,
                details=event.details,
                severity=event.severity,
            )
            for event in step_result.events
            if event.severity in {"major", "catastrophic"}
        ]

    rows: list[EventRow] = []
    for event in notable_events[-limit:]:
        rows.append(
            EventRow(
                summary=f"[{event.label}] {event.civilization}: {event.details}",
                context=event.context_summary,
                severity=event.severity,
                caused_by=event.caused_by_events,
                led_to=event.led_to_events,
            )
        )

    for event in step_result.events:
        if event.event_type not in {"migration", "culture_split"}:
            continue
        new_culture = event.data.get("new_culture", "unknown")
        rows.append(
            EventRow(
                summary=f"[Culture Drift] {event.civilization}: {new_culture}",
                context="",
                severity=event.severity,
            )
        )

    active_wars = [
        f"{civilization_a}->{civilization_b}"
        for civilization_a, civilization_b in step_result.active_wars
    ]
    if active_wars:
        rows.append(EventRow(summary=f"Wars: {', '.join(active_wars)}", context="", severity="normal"))
    return rows


def _court_identity_map(step_result: SeasonStepResult) -> dict[str, tuple[str, str, str, str, str]]:
    return {
        civilization.name: (
            civilization.culture_id,
            civilization.court.ruler_name,
            civilization.court.ruler_dynasty,
            civilization.court.heir_name or "none",
            civilization.court.heir_parent_id,
        )
        for civilization in step_result.civilization_snapshots
    }


def _faction_identity_map(step_result: SeasonStepResult) -> dict[tuple[str, str], tuple[str, str, str]]:
    return {
        (civilization.name, faction.name): (faction.leader_name, faction.dynasty_name, faction.agenda)
        for civilization in step_result.civilization_snapshots
        for faction in civilization.factions
    }


def _visible_actors(court_rows: list[CourtRow], faction_rows: list[FactionRow]) -> list[VisibleActorRow]:
    visible: list[VisibleActorRow] = []
    for index, row in enumerate(court_rows):
        visible.append(
            VisibleActorRow(
                actor_id=row.ruler_agent_id,
                actor_name=row.ruler_name,
                section="court",
                row_index=index,
                relation_label="ruler",
                biography=row.ruler_biography,
            )
        )
        if row.heir_agent_id and row.heir_biography is not None:
            visible.append(
                VisibleActorRow(
                    actor_id=row.heir_agent_id,
                    actor_name=row.heir_name,
                    section="court",
                    row_index=index,
                    relation_label="heir",
                    biography=row.heir_biography,
                )
            )
        if row.general_agent_id and row.general_biography is not None:
            visible.append(
                VisibleActorRow(
                    actor_id=row.general_agent_id,
                    actor_name=row.general_name,
                    section="court",
                    row_index=index,
                    relation_label="general",
                    biography=row.general_biography,
                )
            )
        if row.diplomat_agent_id and row.diplomat_biography is not None:
            visible.append(
                VisibleActorRow(
                    actor_id=row.diplomat_agent_id,
                    actor_name=row.diplomat_name,
                    section="court",
                    row_index=index,
                    relation_label="diplomat",
                    biography=row.diplomat_biography,
                )
            )

    for index, row in enumerate(faction_rows):
        visible.append(
            VisibleActorRow(
                actor_id=row.leader_agent_id,
                actor_name=row.leader_name,
                section="faction",
                row_index=index,
                relation_label=f"{row.faction_name.lower()} leader",
                biography=row.biography,
            )
        )
    return visible
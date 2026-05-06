from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fantasy_engine.core.events import HistoryEvent


class Phase(str, Enum):
    CLIMATE = "climate"
    ECONOMY = "economy"
    TRADE = "trade"
    SOCIETY = "society"
    CHARACTERS = "characters"
    FACTIONS = "factions"
    DIPLOMACY = "diplomacy"
    MILITARY = "military"


SEASONS = ("spring", "summer", "autumn", "winter")


@dataclass(frozen=True, slots=True)
class TickContext:
    year: int
    season_index: int
    season: str


@dataclass(frozen=True, slots=True)
class NeedsSnapshot:
    food: float
    safety: float
    belonging: float
    esteem: float


@dataclass(frozen=True, slots=True)
class AgentBioSnapshot:
    agent_id: str
    name: str
    role: str
    civilization: str
    culture_id: str
    dynasty_name: str
    age: int
    estimated_birth_year: int
    health: float
    loyalty: float
    authority: float
    grievance: float
    fatigue: float
    relation_to_ruler: str
    parent_names: tuple[str, ...]
    grudge_targets: tuple[str, ...]
    needs: NeedsSnapshot
    recent_events: tuple[str, ...]
    caused_by_events: tuple[str, ...] = ()
    led_to_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EventSnapshot:
    event_type: str
    label: str
    civilization: str
    details: str
    severity: str
    actor_name: str = ""
    actor_role: str = ""
    relation_to_ruler: str = ""
    context_summary: str = ""
    other_civilization: str | None = None
    caused_by_events: tuple[str, ...] = ()
    led_to_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CourtSnapshot:
    ruler_name: str
    ruler_dynasty: str
    heir_name: str | None
    heir_agent_id: str
    general_name: str
    general_agent_id: str
    diplomat_name: str
    diplomat_agent_id: str
    heir_parent_id: str
    heir_parent_name: str
    ruler_needs: NeedsSnapshot
    ruler_agent_id: str = ""
    ruler_bio: AgentBioSnapshot | None = None
    heir_bio: AgentBioSnapshot | None = None
    general_bio: AgentBioSnapshot | None = None
    diplomat_bio: AgentBioSnapshot | None = None


@dataclass(frozen=True, slots=True)
class FactionSnapshot:
    name: str
    agenda: str
    leader_name: str
    leader_agent_id: str
    dynasty_name: str
    pressure: float
    needs: NeedsSnapshot
    leader_bio: AgentBioSnapshot | None = None


@dataclass(frozen=True, slots=True)
class CivilizationSnapshot:
    name: str
    culture_id: str
    population: int
    grain_stores: int
    food_stores: int
    weapons_stockpile: int
    supply_stockpile: int
    stability: float
    legitimacy: float
    unrest: float
    at_war_with: tuple[str, ...]
    contested_routes: int
    severed_routes: int
    court: CourtSnapshot
    factions: tuple[FactionSnapshot, ...]
    region_name: str = ""
    terrain_name: str = ""
    map_x: int = 0
    map_y: int = 0


@dataclass(frozen=True, slots=True)
class RouteSnapshot:
    civilization_a: str
    civilization_b: str
    distance: float
    effective_capacity: int
    capacity: int
    effective_risk: float
    state: str
    disrupted_by: tuple[str, ...]


@dataclass(slots=True)
class SeasonStepResult:
    # --- Simulation fields (set by engine/world) ---
    year: int
    season: str
    tick: int
    year_boundary: bool
    world_year: int
    events: list["HistoryEvent"]
    major_events: list["HistoryEvent"]
    civilization_snapshots: list[CivilizationSnapshot]
    active_wars: list[tuple[str, str]]
    active_routes: list[RouteSnapshot]
    event_snapshots: tuple[EventSnapshot, ...] = ()

    # --- Controller fields (set by SimulationController after tick) ---
    # These are intentionally written after the simulation tick completes.
    # Do not treat them as engine-owned state.
    should_pause: bool = False
    pause_reason: str = ""


class System(Protocol):
    phase: Phase

    def update(self, world: "World", context: TickContext) -> None:
        ...


class Engine:
    def __init__(self) -> None:
        self._systems: dict[Phase, list[System]] = {phase: [] for phase in Phase}

    def register(self, system: System) -> None:
        self._systems[system.phase].append(system)

    def run_tick(self, world: "World", context: TickContext) -> None:
        for phase in Phase:
            for system in self._systems[phase]:
                system.update(world, context)
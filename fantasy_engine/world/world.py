from __future__ import annotations

import re

from fantasy_engine.core.engine import (
    AgentBioSnapshot,
    CivilizationSnapshot,
    CourtSnapshot,
    Engine,
    EventSnapshot,
    FactionSnapshot,
    NeedsSnapshot,
    RouteSnapshot,
    SEASONS,
    SeasonStepResult,
    TickContext,
)
from fantasy_engine.core.events import HistoryArchive, HistoryEvent
from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.legends import LegendEntry, LegendsReader
from fantasy_engine.characters.names import get_default_name_registry
from fantasy_engine.systems.characters import CharacterSystem
from fantasy_engine.systems.civilization import Civilization
from fantasy_engine.systems.diplomacy import DiplomacySystem
from fantasy_engine.systems.economy import EconomySystem
from fantasy_engine.systems.factions import FactionSystem
from fantasy_engine.systems.military import MilitarySystem
from fantasy_engine.systems.society import SocietySystem
from fantasy_engine.systems.trade import TradeSystem
from fantasy_engine.world.climate import ClimateSystem
from fantasy_engine.world.map import WorldMap
from fantasy_engine.world.routes import Shipment, TradeRoute


class World:
    CIVILIZATION_NAMES = ("Sylgard", "Quor-Thal", "Arador", "Zanthar", "Velis", "Dunmere")

    def __init__(self, seed: int = 4242, num_civilizations: int = 4) -> None:
        self.seed = seed
        self.rng = SeededRNG(seed)
        self.name_registry = get_default_name_registry()
        self.year = 1
        self.season_index = 0
        self.total_ticks = 0
        self.history = HistoryArchive()
        self.legends_reader = LegendsReader(self.history)
        self.map_regions = WorldMap.generate(self.rng, num_civilizations)
        self.trade_routes = WorldMap.build_trade_routes(self.map_regions, self.rng)
        self.pending_shipments: list[Shipment] = []
        civilization_names = self.CIVILIZATION_NAMES[: len(self.map_regions)]
        self.civilizations = [
            Civilization.from_region(name, region, self.rng)
            for name, region in zip(civilization_names, self.map_regions)
        ]
        self.engine = Engine()
        self.engine.register(ClimateSystem())
        self.engine.register(EconomySystem())
        self.engine.register(TradeSystem())
        self.engine.register(SocietySystem())
        self.engine.register(CharacterSystem())
        self.engine.register(FactionSystem())
        self.engine.register(DiplomacySystem())
        self.engine.register(MilitarySystem())

        self._initialize_relations()
        self.refresh_route_states()

        for civilization in self.civilizations:
            self.history.record_event(
                HistoryEvent(
                    year=self.year,
                    season="spring",
                    event_type="foundation",
                    civilization=civilization.name,
                    details=(
                        f"{civilization.name} took root in {civilization.region.name} under {civilization.ruler.name}, building its fortunes around "
                        f"{civilization.region.terrain.name.lower()} ground, the {civilization.faith_id} faith, fertility {civilization.region.fertility:.2f}, "
                        f"and route cost {civilization.route_cost:.2f}."
                    ),
                    severity="major",
                )
            )

    def _initialize_relations(self) -> None:
        for civilization in self.civilizations:
            for other in self.civilizations:
                if civilization is other:
                    continue
                civilization.relations[other.name] = self.rng.uniform(-28.0, 18.0)

    @property
    def current_season(self) -> str:
        return SEASONS[self.season_index]

    def advance_season(self) -> SeasonStepResult:
        simulated_year = self.year
        simulated_season = self.current_season
        start_index = len(self.history.events)
        self.refresh_route_states()
        context = TickContext(year=self.year, season_index=self.season_index, season=self.current_season)
        self.engine.run_tick(self, context)
        self.refresh_route_states()
        self.total_ticks += 1

        year_boundary = simulated_season == "winter"

        if year_boundary:
            self.season_index = 0
            self.year += 1
        else:
            self.season_index += 1

        return self._build_step_result(
            simulated_year=simulated_year,
            simulated_season=simulated_season,
            tick=self.total_ticks,
            year_boundary=year_boundary,
            events=self.history.events[start_index:],
        )

    def snapshot_current_state(self) -> SeasonStepResult:
        return self._build_step_result(
            simulated_year=self.year,
            simulated_season=self.current_season,
            tick=self.total_ticks,
            year_boundary=False,
            events=[],
        )

    def advance_year(self) -> list[HistoryEvent]:
        year_events: list[HistoryEvent] = []
        for _ in range(4):
            step_result = self.advance_season()
            year_events.extend(step_result.events)
        return year_events

    def simulate(self, years: int = 12) -> list[HistoryEvent]:
        for _ in range(years):
            self.advance_year()
        return self.history.events

    def recent_legends(self, limit: int = 3) -> list[LegendEntry]:
        return self.legends_reader.recent_legends(limit=limit)

    def recent_legend_summaries(self, limit: int = 3) -> list[str]:
        return [legend.summary for legend in self.recent_legends(limit=limit)]

    def get_civilization(self, name: str) -> Civilization | None:
        for civilization in self.civilizations:
            if civilization.name == name:
                return civilization
        return None

    def civilization_for_region(self, region_name: str) -> Civilization | None:
        for civilization in self.civilizations:
            if civilization.region.name == region_name:
                return civilization
        return None

    def region_name_for(self, civilization_name: str) -> str | None:
        civilization = self.get_civilization(civilization_name)
        return civilization.region.name if civilization else None

    def get_route(self, civ_a: str, civ_b: str) -> TradeRoute | None:
        region_a = self.region_name_for(civ_a)
        region_b = self.region_name_for(civ_b)
        if region_a is None or region_b is None:
            return None
        return self.trade_routes.get(tuple(sorted((region_a, region_b))))

    def routes_for(self, civilization_name: str) -> list[TradeRoute]:
        region_name = self.region_name_for(civilization_name)
        if region_name is None:
            return []
        return [route for route in self.trade_routes.values() if region_name in route.key()]

    def route_partner_name(self, civilization_name: str, route: TradeRoute) -> str | None:
        region_name = self.region_name_for(civilization_name)
        if region_name is None:
            return None
        partner_region = route.endpoint_for(region_name)
        if partner_region is None:
            return None
        partner = self.civilization_for_region(partner_region)
        return partner.name if partner else None

    def refresh_route_states(self) -> None:
        for route in self.trade_routes.values():
            previous_state = route.state
            previous_disrupted_by = route.disrupted_by
            route.mark_open()
            civilization_a = self.civilization_for_region(route.region_a)
            civilization_b = self.civilization_for_region(route.region_b)
            if civilization_a is None or civilization_b is None:
                continue
            if civilization_a.collapsed or civilization_b.collapsed:
                continue
            if civilization_b.name in civilization_a.active_wars or civilization_a.name in civilization_b.active_wars:
                route.mark_severed(civilization_a.name, civilization_b.name)
            else:
                disrupted_by: list[str] = []
                if civilization_a.active_wars:
                    disrupted_by.append(civilization_a.name)
                if civilization_b.active_wars:
                    disrupted_by.append(civilization_b.name)
                if disrupted_by:
                    route.mark_contested(*disrupted_by)

            if route.state != previous_state or route.disrupted_by != previous_disrupted_by:
                self._record_route_state_transition(
                    route,
                    civilization_a.name,
                    civilization_b.name,
                    previous_state=previous_state,
                    previous_disrupted_by=previous_disrupted_by,
                )

    def _record_route_state_transition(
        self,
        route: TradeRoute,
        civilization_a: str,
        civilization_b: str,
        *,
        previous_state: str,
        previous_disrupted_by: tuple[str, ...],
    ) -> None:
        if route.state == previous_state and route.disrupted_by == previous_disrupted_by:
            return

        route_name = f"{civilization_a}<->{civilization_b}"
        if route.state == "severed":
            event_type = "route_severed"
            details = (
                f"War between {civilization_a} and {civilization_b} severed the {route_name} route, halting regular caravans and troop movement."
            )
            severity = "major"
        elif route.state == "contested":
            disrupted_names = ", ".join(route.disrupted_by) if route.disrupted_by else "nearby war"
            event_type = "route_contested"
            details = (
                f"Fighting involving {disrupted_names} turned the {route_name} route into a contested corridor, cutting safe capacity to "
                f"{route.effective_capacity}/{route.capacity}."
            )
            severity = "normal"
        elif previous_state in {"contested", "severed"}:
            event_type = "route_reopened"
            details = (
                f"The {route_name} route reopened after the fighting ebbed, restoring regular movement and caravan traffic."
            )
            severity = "normal"
        else:
            return

        self.history.record_event(
            HistoryEvent(
                year=self.year,
                season=self.current_season,
                event_type=event_type,
                civilization=civilization_a,
                other_civilization=civilization_b,
                details=details,
                severity=severity,
                data={
                    "route": route.key(),
                    "previous_state": previous_state,
                    "state": route.state,
                    "disrupted_by": route.disrupted_by,
                },
            )
        )

    def route_state_counts(self, civilization_name: str) -> tuple[int, int]:
        contested = 0
        severed = 0
        for route in self.routes_for(civilization_name):
            if route.state == "contested":
                contested += 1
            elif route.state == "severed":
                severed += 1
        return contested, severed

    def queue_shipment(
        self,
        *,
        origin: str,
        destination: str,
        resource_type: str,
        amount: int,
        kind: str,
        context: TickContext,
        sender_name: str | None = None,
        receiver_name: str | None = None,
        treasury_cost: int = 0,
    ) -> None:
        route = self.get_route(origin, destination)
        if route is None or amount <= 0 or route.state == "severed":
            return
        self.pending_shipments.append(
            Shipment(
                route_key=route.key(),
                origin=origin,
                destination=destination,
                resource_type=resource_type,
                amount=amount,
                kind=kind,
                season=context.season,
                year=context.year,
                sender_name=sender_name,
                receiver_name=receiver_name,
                treasury_cost=treasury_cost,
            )
        )

    def route_summaries(self) -> list[str]:
        summaries: list[str] = []
        for route in sorted(self.trade_routes.values(), key=lambda item: item.key()):
            civs = [civilization for civilization in self.civilizations if civilization.region.name in route.key()]
            if len(civs) != 2:
                continue
            summaries.append(
                f"{civs[0].name}<->{civs[1].name} dist={route.distance:.1f} cap={route.effective_capacity}/{route.capacity} "
                f"risk={route.effective_risk:.2f} state={route.state}"
            )
        return summaries

    def civilization_summaries(self) -> list[str]:
        return [civilization.status_line() for civilization in self.civilizations]

    def drift_culture_for(self, civilization: Civilization, *, suffix: str, years: int) -> str:
        base_culture_id = civilization.culture_origin_id or civilization.culture_id
        normalized_name = civilization.name.lower().replace("-", "_")
        new_culture_id = f"{base_culture_id}_{normalized_name}_{suffix}_{civilization.culture_generation + 1}"
        if new_culture_id not in self.name_registry.cultures:
            self.name_registry.drift_culture(base_culture_id, new_culture_id, years, self.rng)
        return new_culture_id

    def _build_step_result(
        self,
        *,
        simulated_year: int,
        simulated_season: str,
        tick: int,
        year_boundary: bool,
        events: list[HistoryEvent],
    ) -> SeasonStepResult:
        major_events = [event for event in events if event.severity in {"major", "catastrophic"}]
        return SeasonStepResult(
            year=simulated_year,
            season=simulated_season,
            tick=tick,
            year_boundary=year_boundary,
            world_year=self.year,
            events=list(events),
            major_events=major_events,
            civilization_snapshots=self._civilization_snapshots(),
            active_wars=self._active_war_pairs(),
            active_routes=self._route_snapshots(),
            event_snapshots=self._event_snapshots(events),
        )

    def _civilization_snapshots(self) -> list[CivilizationSnapshot]:
        snapshots: list[CivilizationSnapshot] = []
        for civilization in self.civilizations:
            contested_routes, severed_routes = self.route_state_counts(civilization.name)
            heir = civilization.court.heir
            heir_parent_id = heir.parent_ids[0] if heir.parent_ids else "unknown"
            heir_parent_name = self._resolve_agent_display_name(civilization, heir_parent_id)
            snapshots.append(
                CivilizationSnapshot(
                    name=civilization.name,
                    culture_id=civilization.culture_id,
                    population=civilization.population,
                    grain_stores=civilization.grain_stores,
                    food_stores=civilization.food_stores,
                    weapons_stockpile=civilization.military.weapons_stockpile,
                    supply_stockpile=civilization.military.supply_stockpile,
                    stability=civilization.stability,
                    legitimacy=civilization.legitimacy,
                    unrest=civilization.unrest,
                    at_war_with=tuple(sorted(civilization.active_wars)),
                    contested_routes=contested_routes,
                    severed_routes=severed_routes,
                    court=CourtSnapshot(
                        ruler_name=civilization.ruler.name,
                        ruler_dynasty=civilization.ruler.dynasty_name or "none",
                        heir_name=heir.name if heir.alive else None,
                        heir_agent_id=heir.agent_id if heir.alive else "",
                        general_name=civilization.court.general.name,
                        general_agent_id=civilization.court.general.agent_id,
                        diplomat_name=civilization.court.diplomat.name,
                        diplomat_agent_id=civilization.court.diplomat.agent_id,
                        heir_parent_id=heir_parent_id,
                        heir_parent_name=heir_parent_name,
                        ruler_needs=self._needs_snapshot(civilization.ruler),
                        ruler_agent_id=civilization.ruler.agent_id,
                        ruler_bio=self._agent_bio_snapshot(civilization, civilization.ruler),
                        heir_bio=self._agent_bio_snapshot(civilization, heir) if heir.alive else None,
                        general_bio=self._agent_bio_snapshot(civilization, civilization.court.general),
                        diplomat_bio=self._agent_bio_snapshot(civilization, civilization.court.diplomat),
                    ),
                    factions=tuple(
                        FactionSnapshot(
                            name=faction.name,
                            agenda=faction.agenda,
                            leader_name=faction.leader.name,
                            leader_agent_id=faction.leader.agent_id,
                            dynasty_name=faction.leader.dynasty_name or "none",
                            pressure=faction.pressure,
                            needs=self._needs_snapshot(faction.leader),
                            leader_bio=self._agent_bio_snapshot(civilization, faction.leader),
                        )
                        for faction in civilization.factions
                    ),
                    region_name=civilization.region.name,
                    terrain_name=civilization.region.terrain.name,
                    map_x=civilization.region.x,
                    map_y=civilization.region.y,
                )
            )
        return snapshots

    def _resolve_agent_display_name(self, civilization: Civilization, agent_id: str) -> str:
        if not agent_id or agent_id == "unknown":
            return "unknown"

        active_agents = [*civilization.court_members(), civilization.court.consort, *(faction.leader for faction in civilization.factions)]
        for agent in active_agents:
            if agent.agent_id == agent_id:
                return agent.name

        resolved_agent, _ = self._find_agent_anywhere(agent_id)
        if resolved_agent is not None:
            return resolved_agent.name

        return self._humanize_agent_id(agent_id)

    def _humanize_agent_id(self, agent_id: str) -> str:
        normalized = re.sub(r"_\d+$", "", agent_id)
        parts = normalized.split("_")
        if len(parts) >= 3:
            return " ".join(parts[2:])
        return agent_id.replace("_", " ")

    def _route_snapshots(self) -> list[RouteSnapshot]:
        snapshots: list[RouteSnapshot] = []
        for route in sorted(self.trade_routes.values(), key=lambda item: item.key()):
            civilization_a = self.civilization_for_region(route.region_a)
            civilization_b = self.civilization_for_region(route.region_b)
            if civilization_a is None or civilization_b is None:
                continue
            snapshots.append(
                RouteSnapshot(
                    civilization_a=civilization_a.name,
                    civilization_b=civilization_b.name,
                    distance=route.distance,
                    effective_capacity=route.effective_capacity,
                    capacity=route.capacity,
                    effective_risk=route.effective_risk,
                    state=route.state,
                    disrupted_by=route.disrupted_by,
                )
            )
        return snapshots

    def _active_war_pairs(self) -> list[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for civilization in self.civilizations:
            for target in civilization.active_wars:
                pairs.add(tuple(sorted((civilization.name, target))))
        return sorted(pairs)

    def _needs_snapshot(self, agent) -> NeedsSnapshot:
        return NeedsSnapshot(
            food=agent.needs.food,
            safety=agent.needs.safety,
            belonging=agent.needs.belonging,
            esteem=agent.needs.esteem,
        )

    def _event_snapshots(self, events: list[HistoryEvent]) -> tuple[EventSnapshot, ...]:
        return tuple(self._build_event_snapshot(event) for event in events)

    def _build_event_snapshot(self, event: HistoryEvent) -> EventSnapshot:
        civilization = self.get_civilization(event.civilization)
        actor = self._resolve_event_actor(civilization, event)
        relation_to_ruler = self._relation_to_ruler(civilization, actor) if civilization is not None and actor is not None else ""
        context_bits: list[str] = []
        if actor is not None:
            context_bits.append(f"Actor: {actor.name}")
            context_bits.append(actor.role)
            if relation_to_ruler:
                context_bits.append(relation_to_ruler)
        elif civilization is not None:
            context_bits.append(f"Court: {civilization.ruler.name}")

        context_bits.extend(self._event_context_bits(event))
        return EventSnapshot(
            event_type=event.event_type,
            label=event.label,
            civilization=event.civilization,
            details=event.details,
            severity=event.severity,
            actor_name=actor.name if actor is not None else "",
            actor_role=actor.role if actor is not None else "",
            relation_to_ruler=relation_to_ruler,
            context_summary=" · ".join(bit for bit in context_bits if bit),
            other_civilization=event.other_civilization,
            caused_by_events=tuple(self._event_caused_by_lines(event)),
            led_to_events=tuple(self._event_led_to_lines(event)),
        )

    def _resolve_event_actor(self, civilization: Civilization | None, event: HistoryEvent):
        actor_id = self._event_actor_id(event)
        if actor_id:
            actor, _ = self._find_agent_anywhere(actor_id)
            if actor is not None:
                return actor

        if civilization is None:
            return None

        if event.event_type in {"food_shortage", "famine", "unrest", "court_hoarding", "trade_chokepoint", "recovery", "war_declaration"}:
            return civilization.ruler
        if event.event_type in {"military_rationing", "battle"}:
            return civilization.court.general
        if event.event_type == "diplomatic_peace":
            return civilization.court.diplomat
        if event.event_type in {"succession", "faction_coup"}:
            return civilization.ruler
        if event.event_type == "faction_pressure":
            faction = civilization.faction_by_name(str(event.data.get("faction", "")))
            if faction is not None:
                return faction.leader
        return None

    def _event_actor_id(self, event: HistoryEvent) -> str:
        for key in (
            "actor_id",
            "leader_id",
            "new_ruler_id",
            "defector_id",
            "diplomat_id",
            "ruler_id",
            "general_id",
            "replacement_id",
            "deceased_id",
            "old_ruler_id",
        ):
            value = event.data.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _event_context_bits(self, event: HistoryEvent) -> list[str]:
        bits: list[str] = []
        if "faction" in event.data:
            bits.append(f"Faction: {event.data['faction']}")
        if "pressure" in event.data:
            bits.append(f"Pressure: {float(event.data['pressure']):.1f}")
        if "destination" in event.data:
            bits.append(f"To: {event.data['destination']}")
        if "old_ruler" in event.data:
            bits.append(f"Against: {event.data['old_ruler']}")
        if "target_ruler" in event.data:
            bits.append(f"Against ruler: {event.data['target_ruler']}")
        if "target_general" in event.data:
            bits.append(f"Against general: {event.data['target_general']}")
        if "opposing_general" in event.data:
            bits.append(f"Opposed by: {event.data['opposing_general']}")
        if "opposing_ruler" in event.data:
            bits.append(f"Enemy ruler: {event.data['opposing_ruler']}")
        if "counterpart_diplomat" in event.data:
            bits.append(f"Counterpart: {event.data['counterpart_diplomat']}")
        if "winner_general" in event.data:
            bits.append(f"After: {event.data['winner_general']} vs {event.data.get('loser_general', 'unknown')}")
        if "replacement" in event.data and event.event_type in {"court_death", "defection"}:
            bits.append(f"Replacement: {event.data['replacement']}")
        if event.other_civilization:
            bits.append(f"Other: {event.other_civilization}")
        return bits

    def _event_caused_by_lines(self, event: HistoryEvent, *, limit: int = 3) -> list[str]:
        if not event.caused_by:
            return []
        event_index = self._history_event_index()
        source = event_index.get(event.caused_by)
        if source is None:
            return []
        return [f"{event.label} <- {source.label} ({source.civilization})"][:limit]

    def _event_led_to_lines(self, event: HistoryEvent, *, limit: int = 3) -> list[str]:
        if not event.event_id:
            return []
        event_index = self._history_event_index()
        effect_map = self._history_effect_map()
        lines: list[str] = []
        for effect_id in effect_map.get(event.event_id, ()):
            effect = event_index.get(effect_id)
            if effect is None:
                continue
            lines.append(f"{event.label} -> {effect.label} ({effect.civilization})")
            if len(lines) >= limit:
                break
        return lines

    def _agent_bio_snapshot(self, civilization: Civilization, agent) -> AgentBioSnapshot:
        relevant_events = self._agent_relevant_events(civilization, agent, limit=6)
        return AgentBioSnapshot(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role,
            civilization=civilization.name,
            culture_id=agent.culture_id,
            dynasty_name=agent.dynasty_name or "none",
            age=agent.age,
            estimated_birth_year=max(1, self.year - agent.age),
            health=agent.health,
            loyalty=agent.loyalty,
            authority=agent.authority,
            grievance=agent.grievance,
            fatigue=agent.fatigue,
            relation_to_ruler=self._relation_to_ruler(civilization, agent),
            parent_names=tuple(self._resolve_agent_display_name(civilization, parent_id) for parent_id in agent.parent_ids),
            grudge_targets=tuple(
                f"{target} ({value:.0f})"
                for target, value in sorted(agent.grudges.items(), key=lambda item: item[1], reverse=True)[:3]
            ),
            needs=self._needs_snapshot(agent),
            recent_events=tuple(self._format_event_line(event) for event in relevant_events[:4]),
            caused_by_events=tuple(self._agent_caused_by_events(relevant_events)),
            led_to_events=tuple(self._agent_led_to_events(relevant_events)),
        )

    def _agent_relevant_events(self, civilization: Civilization, agent, *, limit: int = 6) -> list[HistoryEvent]:
        relevant: list[HistoryEvent] = []
        for event in reversed(self.history.recent(40)):
            if self._event_mentions_agent(event, agent) or self._is_governing_ruler_event(civilization, agent, event):
                relevant.append(event)
            if len(relevant) >= limit:
                break
        return relevant

    def _agent_caused_by_events(self, relevant_events: list[HistoryEvent], *, limit: int = 3) -> list[str]:
        event_index = self._history_event_index()
        lines: list[str] = []
        seen: set[str] = set()
        for event in relevant_events:
            if not event.caused_by:
                continue
            source = event_index.get(event.caused_by)
            if source is None:
                continue
            line = f"{event.label} <- {source.label} ({source.civilization})"
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    def _agent_led_to_events(self, relevant_events: list[HistoryEvent], *, limit: int = 3) -> list[str]:
        event_index = self._history_event_index()
        effect_map = self._history_effect_map()
        lines: list[str] = []
        seen: set[str] = set()
        for event in relevant_events:
            if not event.event_id:
                continue
            for effect_id in effect_map.get(event.event_id, ()): 
                effect = event_index.get(effect_id)
                if effect is None:
                    continue
                line = f"{event.label} -> {effect.label} ({effect.civilization})"
                if line in seen:
                    continue
                seen.add(line)
                lines.append(line)
                if len(lines) >= limit:
                    return lines
        return lines

    def _history_event_index(self) -> dict[str, HistoryEvent]:
        return {
            event.event_id: event
            for event in self.history.events
            if event.event_id is not None
        }

    def _history_effect_map(self) -> dict[str, list[str]]:
        effect_map: dict[str, list[str]] = {}
        for cause_id, effect_id in self.history.cause_effect_pairs():
            effect_map.setdefault(cause_id, []).append(effect_id)
        return effect_map

    def _format_event_line(self, event: HistoryEvent) -> str:
        return f"Y{event.year} {event.season.title()} · {event.label}: {event.details}"

    def _event_mentions_agent(self, event: HistoryEvent, agent) -> bool:
        for value in event.data.values():
            if value == agent.agent_id or value == agent.name:
                return True
            if isinstance(value, (tuple, list)) and (agent.agent_id in value or agent.name in value):
                return True
        return False

    def _is_governing_ruler_event(self, civilization: Civilization, agent, event: HistoryEvent) -> bool:
        if agent.agent_id != civilization.ruler.agent_id:
            return False
        if event.civilization != civilization.name:
            return False
        return event.event_type in {
            "food_shortage",
            "famine",
            "unrest",
            "court_hoarding",
            "trade_chokepoint",
            "military_rationing",
            "recovery",
            "war_declaration",
            "battle",
        }

    def _find_agent_anywhere(self, agent_id: str):
        for civilization in self.civilizations:
            for agent in [*civilization.court_members(), civilization.court.consort, *(faction.leader for faction in civilization.factions)]:
                if agent.agent_id == agent_id:
                    return agent, civilization
        return None, None

    def _relation_to_ruler(self, civilization: Civilization, agent) -> str:
        ruler = civilization.ruler
        if agent.agent_id == ruler.agent_id:
            return "ruler"
        if agent.agent_id == civilization.court.heir.agent_id:
            if ruler.agent_id in agent.parent_ids:
                return "heir, child of ruler"
            return "heir"
        if ruler.agent_id in agent.parent_ids:
            return "child of ruler"
        if any(member.agent_id == agent.agent_id for member in civilization.court_members()):
            return "court insider"
        if any(faction.leader.agent_id == agent.agent_id for faction in civilization.factions):
            return "outside court"
        return ""
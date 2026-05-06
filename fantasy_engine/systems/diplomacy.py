from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import DiplomacyWorld
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization


class DiplomacySystem:
    phase = Phase.DIPLOMACY

    def update(self, world: DiplomacyWorld, context: TickContext) -> None:
        civilizations = [civilization for civilization in world.civilizations if not civilization.collapsed]
        for civilization in civilizations:
            self._attempt_relief(world, civilization, context)
            self._externalize_crisis(world, civilization, context)

        self._drift_relations(world, civilizations, current_year=context.year)

    def _attempt_relief(self, world: DiplomacyWorld, civilization: "Civilization", context: TickContext) -> None:
        if civilization.food_stores >= civilization.seasonal_food_need():
            return

        donor = None
        donor_route = None
        best_score = -999.0
        for route in world.routes_for(civilization.name):
            if route.state == "severed":
                continue
            candidate_name = world.route_partner_name(civilization.name, route)
            if candidate_name is None:
                continue
            candidate = world.get_civilization(candidate_name)
            if candidate is None or candidate.collapsed:
                continue
            if candidate.name in civilization.active_wars:
                continue
            if candidate.relief_cooldown > 0:
                continue

            relation = civilization.relation_with(candidate.name)
            surplus = candidate.food_stores + candidate.grain_stores - candidate.seasonal_food_need()
            if surplus <= 0:
                continue

            score = (
                relation * 0.35
                + surplus * 0.20
                + candidate.court.diplomat.empathy * 0.25
                + route.effective_capacity * 0.20
                - route.distance * 1.2
                - route.effective_risk * 16.0
            )
            score += self._aid_memory_bonus(world, donor=candidate, recipient=civilization, current_year=context.year)
            if score > best_score:
                best_score = score
                donor = candidate
                donor_route = route

        if donor is None or donor_route is None or best_score <= 0.0:
            return

        aid_amount = min(
            max(3, civilization.seasonal_food_need() // 2),
            donor_route.effective_capacity,
            max(0, donor.food_stores + donor.grain_stores - donor.seasonal_food_need()),
        )
        if aid_amount <= 0:
            return

        donor_food = min(donor.food_stores, aid_amount)
        donor.food_stores -= donor_food
        remaining = aid_amount - donor_food
        if remaining > 0:
            donor.grain_stores = max(0, donor.grain_stores - remaining)
        donor.relief_cooldown = 3
        donor.adjust_relation(civilization.name, 8.0)
        civilization.adjust_relation(donor.name, 10.0)
        civilization.recovery_window = max(civilization.recovery_window, 2)
        civilization.last_relief_season = (context.year, context.season)
        world.queue_shipment(
            origin=donor.name,
            destination=civilization.name,
            resource_type="grain",
            amount=aid_amount,
            kind="aid",
            context=context,
            sender_name=donor.court.diplomat.name,
            receiver_name=civilization.court.diplomat.name,
        )

    def _externalize_crisis(self, world: DiplomacyWorld, civilization: "Civilization", context: TickContext) -> None:
        if civilization.active_wars:
            return
        if civilization.war_cooldown > 0:
            return

        ruler_need_pressure = (
            civilization.ruler.needs.food * 0.28
            + civilization.ruler.needs.safety * 0.30
            + civilization.ruler.needs.esteem * 0.22
            + civilization.ruler.needs.belonging * 0.12
        )
        general_need_pressure = (
            civilization.court.general.needs.safety * 0.45
            + civilization.court.general.needs.esteem * 0.25
            + civilization.court.general.needs.food * 0.15
        )
        crisis_pressure = civilization.unrest + civilization.unmet_food_pressure + max(0.0, 40.0 - civilization.legitimacy)
        military = civilization.faction_by_name("Military")
        military_pressure = military.pressure if military else 0.0
        foreign_backing_pressure = self._foreign_backing_pressure(world, civilization=civilization, current_year=context.year)
        confessional_pressure = self._confessional_pressure(civilization)
        aggression_pressure = crisis_pressure + ruler_need_pressure * 0.55 + general_need_pressure * 0.35 + foreign_backing_pressure + confessional_pressure
        if aggression_pressure < 78.0 and military_pressure + general_need_pressure * 0.40 + foreign_backing_pressure < 88.0:
            return
        if (
            civilization.ruler.crisis_aggression + ruler_need_pressure * 0.12 + general_need_pressure * 0.08 < 52.0
            and military_pressure + general_need_pressure * 0.35 + foreign_backing_pressure * 0.75 < 92.0
        ):
            return

        target = None
        best_score = -999.0
        for candidate in world.civilizations:
            if candidate is civilization or candidate.collapsed:
                continue
            relation = civilization.relation_with(candidate.name)
            if relation > 18.0:
                continue

            score = -relation + max(0.0, civilization.force_projection() - candidate.force_projection()) * 10.0
            score += civilization.court.general.grudge_toward(candidate.name) * 0.5
            score += ruler_need_pressure * 0.08 + general_need_pressure * 0.10
            score += self._foreign_backing_target_bonus(world, civilization=civilization, target=candidate, current_year=context.year)
            score += self._aggression_memory_bonus(world, civilization=civilization, target=candidate, current_year=context.year)
            score += self._confessional_target_bonus(civilization, candidate)
            if score > best_score:
                best_score = score
                target = candidate

        if target is None:
            return

        civilization.adjust_relation(target.name, -28.0)
        target.adjust_relation(civilization.name, -24.0)
        if civilization.relation_with(target.name) <= -22.0:
            civilization.active_wars.add(target.name)
            target.active_wars.add(civilization.name)
            civilization.war_cooldown = 3
            target.war_cooldown = max(target.war_cooldown, 2)
            war_event = world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="war_declaration",
                    civilization=civilization.name,
                    other_civilization=target.name,
                    details=(
                        f"Facing domestic pressure, {civilization.ruler.name} turned outward and declared war on {target.name}."
                    ),
                    severity="major",
                    data={
                        "ruler": civilization.ruler.name,
                        "ruler_id": civilization.ruler.agent_id,
                        "general": civilization.court.general.name,
                        "general_id": civilization.court.general.agent_id,
                        "target": target.name,
                        "target_ruler": target.ruler.name,
                        "target_ruler_id": target.ruler.agent_id,
                        "target_general": target.court.general.name,
                        "target_general_id": target.court.general.agent_id,
                    },
                )
            )
            self._maybe_record_holy_war(world, civilization=civilization, target=target, context=context, war_event=war_event)

    def _confessional_pressure(self, civilization: "Civilization") -> float:
        if civilization.schism_pressure <= 0.0:
            return 0.0
        ruler_alignment = 1.0 if civilization.ruler.faith_id == civilization.faith_id else 0.65
        return civilization.schism_pressure * 0.35 * ruler_alignment

    def _confessional_target_bonus(self, civilization: "Civilization", target: "Civilization") -> float:
        if civilization.faith_id == target.faith_id:
            return 0.0
        ruler_alignment = 1.0 if civilization.ruler.faith_id == civilization.faith_id else 0.55
        heroic_push = civilization.court.general.heroic_reputation * 0.20
        return civilization.schism_pressure * 0.60 * ruler_alignment + heroic_push

    def _maybe_record_holy_war(
        self,
        world: DiplomacyWorld,
        *,
        civilization: "Civilization",
        target: "Civilization",
        context: TickContext,
        war_event: HistoryEvent,
    ) -> None:
        if civilization.faith_id == target.faith_id:
            return
        if civilization.schism_pressure < 24.0:
            return

        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="holy_war",
                civilization=civilization.name,
                other_civilization=target.name,
                details=(
                    f"{civilization.ruler.name} cast the war against {target.name} as a defense of the {civilization.faith_id} faith "
                    f"against {target.faith_id} rivals."
                ),
                severity="major",
                caused_by=war_event.event_id,
                data={
                    "ruler": civilization.ruler.name,
                    "ruler_id": civilization.ruler.agent_id,
                    "faith": civilization.faith_id,
                    "target_faith": target.faith_id,
                },
            )
        )

    def _drift_relations(self, world: DiplomacyWorld, civilizations: list["Civilization"], *, current_year: int) -> None:
        for civilization in civilizations:
            for other in civilizations:
                if other is civilization:
                    continue
                relation = civilization.relation_with(other.name)
                if other.name in civilization.active_wars:
                    civilization.relations[other.name] = max(-100.0, relation - 1.0)
                else:
                    crisis_drag = 2.5 if civilization.unrest >= 55.0 else 0.0
                    memory_bias = self._alignment_memory_bias(
                        world,
                        civilization=civilization,
                        counterpart=other,
                        current_year=current_year,
                    )
                    civilization.relations[other.name] = max(
                        -100.0,
                        min(100.0, relation * 0.985 - crisis_drag + memory_bias),
                    )

    def _alignment_memory_bias(
        self,
        world: DiplomacyWorld,
        *,
        civilization: "Civilization",
        counterpart: "Civilization",
        current_year: int,
    ) -> float:
        score = 0.0
        for event in world.history.get_recent_pair_events(civilization.name, counterpart.name, years_back=8, current_year=current_year):
            recency = max(0.30, 1.0 - max(0, current_year - event.year) * 0.12)
            carryover = self._dynasty_carryover_factor(world, civilization_name=event.civilization, current_year=current_year)
            if event.event_type == "diplomatic_aid":
                if event.civilization == counterpart.name:
                    score += 1.4 * recency * carryover
                elif event.civilization == civilization.name:
                    score += 0.6 * recency * carryover
            elif event.event_type in {"diplomatic_peace", "route_reopened"}:
                score += 0.9 * recency * carryover
            elif event.event_type in {"battle", "war_declaration", "route_severed", "defection"}:
                score -= 1.8 * recency * carryover
        return score

    def _aid_memory_bonus(
        self,
        world: DiplomacyWorld,
        *,
        donor: "Civilization",
        recipient: "Civilization",
        current_year: int,
    ) -> float:
        score = 0.0
        carryover = self._dynasty_carryover_factor(world, civilization_name=donor.name, current_year=current_year)
        for event in world.history.get_recent_pair_events(donor.name, recipient.name, years_back=6, current_year=current_year):
            recency = max(0.35, 1.0 - max(0, current_year - event.year) * 0.15)
            if event.event_type == "diplomatic_aid" and event.civilization == donor.name:
                score += 12.0 * recency * carryover
            elif event.event_type in {"diplomatic_peace", "route_reopened"}:
                score += 4.0 * recency * carryover
            elif event.event_type in {"battle", "war_declaration", "route_severed"}:
                score -= 10.0 * recency * carryover
        return score

    def _foreign_backing_pressure(self, world: DiplomacyWorld, *, civilization: "Civilization", current_year: int) -> float:
        backing_events = world.history.get_recent_events(civilization.name, "foreign_backing", years_back=2, current_year=current_year)
        if not backing_events:
            return 0.0

        latest_backing = backing_events[-1]
        recency = max(0.45, 1.0 - max(0, current_year - latest_backing.year) * 0.25)
        pressure = float(latest_backing.data.get("pressure", 0.0))
        return min(16.0, 5.0 + pressure * 0.12) * recency

    def _foreign_backing_target_bonus(
        self,
        world: DiplomacyWorld,
        *,
        civilization: "Civilization",
        target: "Civilization",
        current_year: int,
    ) -> float:
        bonus = 0.0
        for event in world.history.get_recent_pair_events(
            civilization.name,
            target.name,
            event_types={"foreign_backing"},
            years_back=2,
            current_year=current_year,
        ):
            if event.other_civilization != target.name:
                continue
            recency = max(0.45, 1.0 - max(0, current_year - event.year) * 0.25)
            bonus += (10.0 + float(event.data.get("pressure", 0.0)) * 0.18) * recency
        return bonus

    def _dynasty_carryover_factor(self, world: DiplomacyWorld, *, civilization_name: str, current_year: int) -> float:
        civilization = world.get_civilization(civilization_name)
        if civilization is None:
            return 1.0

        for event in reversed(world.history.get_recent_events(civilization_name, years_back=10, current_year=current_year)):
            if event.event_type not in {"succession", "faction_coup"}:
                continue

            old_dynasty = event.data.get("old_ruler_dynasty")
            new_dynasty = event.data.get("new_ruler_dynasty")
            if new_dynasty is None or civilization.ruler.dynasty_name != new_dynasty:
                continue

            if event.event_type == "succession" and old_dynasty == new_dynasty:
                return 1.8

            if old_dynasty is not None and old_dynasty != new_dynasty:
                return 0.15

            return 0.55

        return 1.0

    def _aggression_memory_bonus(
        self,
        world: DiplomacyWorld,
        *,
        civilization: "Civilization",
        target: "Civilization",
        current_year: int,
    ) -> float:
        score = 0.0
        for event in world.history.get_recent_pair_events(civilization.name, target.name, years_back=8, current_year=current_year):
            recency = max(0.30, 1.0 - max(0, current_year - event.year) * 0.12)
            if event.event_type in {"battle", "war_declaration", "route_severed"}:
                score += 12.0 * recency
            elif event.event_type == "defection" and event.civilization == civilization.name and event.other_civilization == target.name:
                score += 8.0 * recency
            elif event.event_type in {"diplomatic_aid", "diplomatic_peace", "route_reopened"}:
                score -= 10.0 * recency
        return score
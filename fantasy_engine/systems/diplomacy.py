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

        self._drift_relations(civilizations)

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

        if donor is None or donor_route is None:
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
        aggression_pressure = crisis_pressure + ruler_need_pressure * 0.55 + general_need_pressure * 0.35
        if aggression_pressure < 78.0 and military_pressure + general_need_pressure * 0.40 < 88.0:
            return
        if (
            civilization.ruler.crisis_aggression + ruler_need_pressure * 0.12 + general_need_pressure * 0.08 < 52.0
            and military_pressure + general_need_pressure * 0.35 < 92.0
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
            score += self._aggression_memory_bonus(world, civilization=civilization, target=candidate, current_year=context.year)
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
            world.history.record_event(
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

    def _drift_relations(self, civilizations: list["Civilization"]) -> None:
        for civilization in civilizations:
            for other in civilizations:
                if other is civilization:
                    continue
                relation = civilization.relation_with(other.name)
                if other.name in civilization.active_wars:
                    civilization.relations[other.name] = max(-100.0, relation - 1.0)
                else:
                    crisis_drag = 2.5 if civilization.unrest >= 55.0 else 0.0
                    civilization.relations[other.name] = relation * 0.985 - crisis_drag

    def _aid_memory_bonus(
        self,
        world: DiplomacyWorld,
        *,
        donor: "Civilization",
        recipient: "Civilization",
        current_year: int,
    ) -> float:
        score = 0.0
        for event in world.history.get_recent_pair_events(donor.name, recipient.name, years_back=6, current_year=current_year):
            recency = max(0.35, 1.0 - max(0, current_year - event.year) * 0.15)
            if event.event_type == "diplomatic_aid" and event.civilization == donor.name:
                score += 12.0 * recency
            elif event.event_type in {"diplomatic_peace", "route_reopened"}:
                score += 4.0 * recency
            elif event.event_type in {"battle", "war_declaration", "route_severed"}:
                score -= 10.0 * recency
        return score

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
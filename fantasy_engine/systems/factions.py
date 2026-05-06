from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import FactionWorld
from fantasy_engine.characters.person import Agent
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization, Faction


class FactionSystem:
    phase = Phase.FACTIONS

    def update(self, world: FactionWorld, context: TickContext) -> None:
        for civilization in world.civilizations:
            if civilization.collapsed:
                continue

            if civilization.coup_cooldown > 0:
                civilization.coup_cooldown -= 1

            highest_pressure = 0.0
            leading_faction = None
            for faction in civilization.factions:
                faction.pressure = self._calculate_pressure(civilization, faction)
                if faction.pressure > highest_pressure:
                    highest_pressure = faction.pressure
                    leading_faction = faction

            if leading_faction is None:
                continue

            if highest_pressure >= 50.0:
                world.history.record_event(
                    HistoryEvent(
                        year=context.year,
                        season=context.season,
                        event_type="faction_pressure",
                        civilization=civilization.name,
                        details=(
                            f"{leading_faction.leader.name} rallied the {leading_faction.name.lower()} around {leading_faction.agenda}; "
                            f"their pressure reached {highest_pressure:.1f}."
                        ),
                        severity="major" if highest_pressure >= 70.0 else "normal",
                        data={
                            "faction": leading_faction.name,
                            "leader": leading_faction.leader.name,
                            "leader_id": leading_faction.leader.agent_id,
                            "leader_role": leading_faction.leader.role,
                            "pressure": round(highest_pressure, 1),
                        },
                    )
                )

            self._seek_foreign_backing(world, civilization, context, leading_faction, highest_pressure)

            foreign_coup_support = self._foreign_coup_support(
                world,
                civilization,
                faction=leading_faction,
                current_year=context.year,
            )

            if (
                civilization.coup_cooldown == 0
                and highest_pressure + self._coup_support(leading_faction, civilization) + foreign_coup_support >= 78.0
                and civilization.stability <= 32.0
                and civilization.legitimacy <= 38.0
                and leading_faction.leader is not civilization.ruler
            ):
                self._attempt_coup(
                    world,
                    civilization,
                    context,
                    leading_faction,
                    highest_pressure + self._coup_support(leading_faction, civilization) + foreign_coup_support,
                )

    def _calculate_pressure(self, civilization: "Civilization", faction: "Faction") -> float:
        leader = faction.leader
        food_term = civilization.unmet_food_pressure * (1.1 if faction.name == "Commoners" else 0.45)
        legitimacy_term = max(0.0, 55.0 - civilization.legitimacy) * (0.9 if faction.name == "Nobility" else 0.35)
        order_term = max(0.0, civilization.unrest - 22.0) * (0.95 if faction.name == "Military" else 0.30)
        leadership_term = leader.grievance * 0.35 + leader.ambition * 0.18 + leader.authority * 0.12
        need_term = self._need_pressure(faction)
        ruler_dampener = civilization.ruler.recovery_bias * 0.10 if faction.name != "Military" else civilization.ruler.authority * 0.08
        return min(
            100.0,
            max(0.0, faction.influence * 28.0 + food_term + legitimacy_term + order_term + leadership_term + need_term - ruler_dampener),
        )

    def _need_pressure(self, faction: "Faction") -> float:
        needs = faction.leader.needs
        if faction.name == "Commoners":
            return needs.food * 0.30 + needs.belonging * 0.18 + needs.safety * 0.10 + needs.esteem * 0.08
        if faction.name == "Nobility":
            return needs.esteem * 0.28 + needs.belonging * 0.16 + needs.safety * 0.12 + needs.food * 0.05
        return needs.safety * 0.32 + needs.esteem * 0.16 + needs.food * 0.10 + needs.belonging * 0.08

    def _coup_support(self, faction: "Faction", civilization: "Civilization") -> float:
        return self._need_pressure(faction) * 0.22 + civilization.ruler.needs.esteem * 0.05 + civilization.ruler.needs.belonging * 0.04

    def _foreign_coup_support(
        self,
        world: FactionWorld,
        civilization: "Civilization",
        *,
        faction: "Faction",
        current_year: int,
    ) -> float:
        backing = self._recent_foreign_backing(world, civilization, faction=faction, current_year=current_year)
        if backing is None:
            return 0.0

        pressure = float(backing.data.get("pressure", 0.0))
        hostility = max(0.0, -civilization.relation_with(backing.other_civilization or ""))
        agenda_bias = 1.15 if faction.name == "Military" else 1.0 if faction.name == "Nobility" else 0.45
        return (8.0 + pressure * 0.08 + hostility * 0.12) * agenda_bias

    def _recent_foreign_backing(
        self,
        world: FactionWorld,
        civilization: "Civilization",
        *,
        faction: "Faction",
        current_year: int,
    ) -> HistoryEvent | None:
        for event in reversed(world.history.get_recent_events(civilization.name, "foreign_backing", years_back=1, current_year=current_year)):
            if event.data.get("faction") == faction.name:
                return event
        return None

    def _seek_foreign_backing(
        self,
        world: FactionWorld,
        civilization: "Civilization",
        context: TickContext,
        faction: "Faction",
        pressure: float,
    ) -> None:
        if pressure < 58.0:
            return
        if civilization.stability > 45.0 and civilization.legitimacy > 45.0 and civilization.unrest < 28.0:
            return

        recent_backing = world.history.get_recent_events(civilization.name, "foreign_backing", years_back=1, current_year=context.year)
        if recent_backing:
            return

        supporter = None
        best_score = 0.0
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

            hostility = max(0.0, -civilization.relation_with(candidate.name)) + max(0.0, -candidate.relation_with(civilization.name)) * 0.8
            if hostility < 10.0:
                continue

            agenda_fit = 8.0 if faction.name == "Military" else 5.0 if faction.name == "Nobility" else 2.0
            score = (
                hostility
                + max(0.0, candidate.force_projection() - civilization.force_projection()) * 0.08
                + pressure * 0.15
                + faction.influence * 12.0
                + agenda_fit
                + route.effective_capacity * 0.5
                - route.distance
                - route.effective_risk * 12.0
            )
            if score > best_score:
                best_score = score
                supporter = candidate

        if supporter is None or best_score < 24.0:
            return

        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="foreign_backing",
                civilization=civilization.name,
                other_civilization=supporter.name,
                details=(
                    f"{faction.leader.name} opened covert contact with {supporter.name}, inviting foreign backing for the "
                    f"{faction.name.lower()} while {civilization.name}'s court faltered."
                ),
                severity="major",
                data={
                    "faction": faction.name,
                    "leader": faction.leader.name,
                    "leader_id": faction.leader.agent_id,
                    "pressure": round(pressure, 1),
                    "supporter": supporter.name,
                    "supporter_ruler": supporter.ruler.name,
                    "supporter_ruler_id": supporter.ruler.agent_id,
                },
            )
        )

    def _attempt_coup(
        self,
        world: FactionWorld,
        civilization: "Civilization",
        context: TickContext,
        faction: "Faction",
        pressure: float,
    ) -> None:
        success_threshold = 0.30 + max(0.0, pressure - 78.0) / 100.0 + faction.leader.regime_skill / 240.0
        success_roll = world.rng.random()
        if success_roll > success_threshold:
            civilization.stability = max(0.0, civilization.stability - 4.0)
            civilization.legitimacy = max(0.0, civilization.legitimacy - 2.5)
            civilization.unrest = min(100.0, civilization.unrest + 4.0)
            return

        old_ruler = civilization.ruler
        faction.leader.retitle("Ruler")
        new_ruler = faction.leader
        civilization.ruler = new_ruler
        civilization.court.ruler = new_ruler
        faction.leader = Agent.create(
            world.rng,
            civilization.name,
            self._faction_role(faction.name),
            culture_id=civilization.culture_id,
            parent=new_ruler,
            dynasty_name=new_ruler.dynasty_name,
        )
        civilization.replace_court_member(world.rng, "Heir", parent=new_ruler, dynasty_name=new_ruler.dynasty_name)
        civilization.stability = min(60.0, civilization.stability + 12.0)
        civilization.legitimacy = min(66.0, civilization.legitimacy + 12.0)
        civilization.unrest = max(14.0, civilization.unrest - 18.0)
        civilization.unmet_food_pressure = max(0.0, civilization.unmet_food_pressure - 10.0)
        civilization.treasury = max(0, civilization.treasury - 12)
        civilization.food_stores += max(4, int(new_ruler.recovery_bias / 12.0))
        civilization.coup_cooldown = 6
        civilization.recovery_window = 5

        foreign_backing = self._recent_foreign_backing(world, civilization, faction=faction, current_year=context.year)

        details = (
            f"{new_ruler.name} led the {faction.name.lower()} in overthrowing {old_ruler.name}. "
            f"The new regime promised emergency grain relief and tighter control of the court."
        )
        if foreign_backing is not None and foreign_backing.other_civilization:
            details = (
                f"{new_ruler.name} led the {faction.name.lower()} in overthrowing {old_ruler.name} after covert backing from "
                f"{foreign_backing.other_civilization} stiffened the faction's resolve. The new regime promised emergency grain relief "
                f"and tighter control of the court."
            )

        event_data = {
            "faction": faction.name,
            "pressure": round(pressure, 1),
            "new_ruler": new_ruler.name,
            "new_ruler_id": new_ruler.agent_id,
            "new_ruler_dynasty": new_ruler.dynasty_name,
            "old_ruler": old_ruler.name,
            "old_ruler_id": old_ruler.agent_id,
            "old_ruler_dynasty": old_ruler.dynasty_name,
        }
        if foreign_backing is not None and foreign_backing.other_civilization:
            event_data["supporter"] = foreign_backing.other_civilization
            event_data["supporting_ruler"] = foreign_backing.data.get("supporter_ruler", "")

        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="faction_coup",
                civilization=civilization.name,
                details=details,
                severity="catastrophic",
                data=event_data,
            )
        )

    def _faction_role(self, faction_name: str) -> str:
        if faction_name == "Military":
            return "Military Leader"
        if faction_name == "Nobility":
            return "Noble Speaker"
        return "Commoner Tribune"
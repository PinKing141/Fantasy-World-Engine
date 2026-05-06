from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import CharacterWorld
from fantasy_engine.characters.needs import update_agent_needs
from fantasy_engine.characters.person import clamp
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization, Faction


class CharacterSystem:
    phase = Phase.CHARACTERS

    def update(self, world: CharacterWorld, context: TickContext) -> None:
        for civilization in world.civilizations:
            if civilization.collapsed:
                continue

            self._update_ruler(civilization)
            self._update_court(world, civilization, context)
            for faction in civilization.factions:
                self._update_faction_leader(civilization, faction)

            if civilization.recovery_window > 0:
                civilization.recovery_window -= 1
            if civilization.relief_cooldown > 0:
                civilization.relief_cooldown -= 1
            if civilization.war_cooldown > 0:
                civilization.war_cooldown -= 1

            self._maybe_record_recovery(world, civilization, context)

    def _update_ruler(self, civilization: "Civilization") -> None:
        ruler = civilization.ruler
        needs = update_agent_needs(ruler, civilization)
        crisis_load = (
            civilization.unrest * 0.45
            + civilization.unmet_food_pressure * 0.60
            + needs.food * 0.18
            + needs.safety * 0.14
        )
        ruler.fatigue = clamp(ruler.fatigue + crisis_load * 0.03 - 1.0, 0.0, 100.0)
        ruler.grievance = clamp(ruler.grievance + needs.belonging * 0.018 + needs.esteem * 0.022 - civilization.legitimacy * 0.004)
        ruler.authority = clamp(
            ruler.authority
            + (civilization.legitimacy - 50.0) * 0.06
            - crisis_load * 0.05
            - needs.esteem * 0.020
        )
        ruler.loyalty = clamp(
            ruler.loyalty
            + (civilization.stability - 50.0) * 0.02
            - max(0.0, civilization.unrest - 30.0) * 0.04
            - needs.belonging * 0.020
        )

        if civilization.recovery_window > 0:
            ruler.authority = clamp(ruler.authority + 1.4)
            ruler.fatigue = clamp(ruler.fatigue - 1.8)

    def _update_faction_leader(self, civilization: "Civilization", faction: "Faction") -> None:
        grievance_push = civilization.unrest * 0.04 + civilization.unmet_food_pressure * 0.08
        if faction.name == "Commoners":
            grievance_push += max(0.0, 40.0 - civilization.food_stores) * 0.15
        elif faction.name == "Nobility":
            grievance_push += max(0.0, 45.0 - civilization.legitimacy) * 0.08
        elif faction.name == "Military":
            grievance_push += civilization.war_exhaustion * 0.03 + max(0.0, civilization.unrest - 25.0) * 0.05

        leader = faction.leader
        needs = update_agent_needs(leader, civilization)
        leader.grievance = clamp(
            leader.grievance
            + grievance_push
            + needs.food * 0.018
            + needs.belonging * 0.028
            + needs.esteem * 0.022
            - max(0.0, civilization.stability - 55.0) * 0.04
        )
        leader.authority = clamp(
            leader.authority
            + faction.influence * 1.5
            - leader.grievance * 0.03
            - needs.esteem * 0.015
        )
        leader.loyalty = clamp(
            leader.loyalty
            + civilization.legitimacy * 0.01
            - leader.grievance * 0.05
            - needs.belonging * 0.018
            - needs.safety * 0.010
        )

    def _update_court(self, world: CharacterWorld, civilization: "Civilization", context: TickContext) -> None:
        for member in civilization.court_members():
            if not member.alive:
                continue
            needs = member.needs if member is civilization.ruler else update_agent_needs(member, civilization)
            member.fatigue = clamp(
                member.fatigue
                + civilization.unrest * 0.01
                + civilization.war_exhaustion * 0.04
                + needs.food * 0.020
                + needs.safety * 0.014
                - 0.6
            )
            member.grievance = clamp(
                member.grievance
                + max(0.0, 45.0 - civilization.legitimacy) * 0.05
                + needs.belonging * 0.024
                + needs.esteem * 0.020
            )
            member.loyalty = clamp(
                member.loyalty
                + civilization.legitimacy * 0.008
                - member.grievance * 0.03
                - needs.belonging * 0.018
                - needs.esteem * 0.010
            )

            for enemy_name in civilization.active_wars:
                member.add_grudge(enemy_name, 2.0 if member.role in {"General", "Ruler"} else 0.8)

            if context.season == "winter":
                member.age += 1
                member.health = clamp(member.health - member.fatigue * 0.04 - max(0, member.age - 55) * 0.9, 0.0, 100.0)
                self._check_court_death(world, civilization, member, context)

        self._check_defection(world, civilization, context)

    def _check_court_death(self, world: CharacterWorld, civilization: "Civilization", member: "Agent", context: TickContext) -> None:
        if not member.alive:
            return
        death_risk = 0.0
        if member.health <= 0.0:
            death_risk = 1.0
        elif member.health < 26.0:
            death_risk = 0.25
        elif member.age > 68:
            death_risk = 0.18
        if world.rng.random() > death_risk:
            return

        member.alive = False
        if member.role == "Ruler":
            old_ruler, new_ruler = civilization.promote_heir(world.rng)
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="succession",
                    civilization=civilization.name,
                    details=f"{old_ruler.name} died, and {new_ruler.name} inherited the throne.",
                    severity="major",
                    data={
                        "old_ruler": old_ruler.name,
                        "old_ruler_id": old_ruler.agent_id,
                        "old_ruler_dynasty": old_ruler.dynasty_name,
                        "new_ruler": new_ruler.name,
                        "new_ruler_id": new_ruler.agent_id,
                        "new_ruler_dynasty": new_ruler.dynasty_name,
                    },
                )
            )
            return

        replacement = civilization.replace_court_member(world.rng, member.role, parent=member, dynasty_name=member.dynasty_name)
        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="court_death",
                civilization=civilization.name,
                details=f"{member.name}, serving as {member.role.lower()}, died and was replaced by {replacement.name}.",
                severity="normal",
                data={
                    "role": member.role,
                    "deceased": member.name,
                    "deceased_id": member.agent_id,
                    "replacement": replacement.name,
                    "replacement_id": replacement.agent_id,
                },
            )
        )

    def _check_defection(self, world: CharacterWorld, civilization: "Civilization", context: TickContext) -> None:
        for role in ("Diplomat", "General"):
            member = civilization.court_member(role)
            if member is None or not member.alive:
                continue
            need_pressure = self._defection_need_pressure(member)
            if member.loyalty > 42.0 and need_pressure < 46.0:
                continue
            if member.grievance < 35.0 and need_pressure < 54.0:
                continue
            if civilization.stability > 24.0 and civilization.legitimacy > 24.0 and need_pressure < 60.0:
                continue

            target = None
            best_score = -999.0
            for route in world.routes_for(civilization.name):
                if route.state == "severed":
                    continue
                candidate_name = world.route_partner_name(civilization.name, route)
                if candidate_name is None:
                    continue
                candidate = world.get_civilization(candidate_name)
                if candidate is None or candidate.collapsed or candidate_name in civilization.active_wars:
                    continue
                score = (
                    candidate.stability
                    - civilization.stability
                    + civilization.relation_with(candidate_name)
                    + member.grudge_toward(candidate_name) * 0.4
                    + route.effective_capacity
                    - route.effective_risk * 20.0
                    + need_pressure * 0.25
                )
                score += self._defection_memory_bonus(world, civilization=civilization, candidate=candidate, current_year=context.year)
                if score > best_score:
                    best_score = score
                    target = candidate

            escape_threshold = max(-6.0, 10.0 - need_pressure * 0.18)
            if target is None or best_score < escape_threshold:
                continue

            replacement = civilization.replace_court_member(
                world.rng,
                role,
                parent=civilization.ruler,
                dynasty_name=civilization.ruler.dynasty_name,
            )
            if role == "Diplomat":
                target.court.diplomat = member
            else:
                target.court.general = member
            member.home_civilization = target.name
            member.culture_id = target.culture_id
            member.loyalty = clamp(member.loyalty + 18.0)
            member.grievance = max(0.0, member.grievance - 20.0)
            target.adjust_relation(civilization.name, -4.0)
            civilization.adjust_relation(target.name, -12.0)
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="defection",
                    civilization=civilization.name,
                    other_civilization=target.name,
                    details=(
                        f"{member.name}, formerly {civilization.name}'s {role.lower()}, defected to {target.name}. "
                        f"{replacement.name} was elevated to fill the vacancy."
                    ),
                    severity="major",
                    data={
                        "role": role,
                        "defector": member.name,
                        "defector_id": member.agent_id,
                        "destination": target.name,
                        "replacement": replacement.name,
                        "replacement_id": replacement.agent_id,
                    },
                )
            )

    def _defection_need_pressure(self, member) -> float:
        return (
            member.needs.food * 0.18
            + member.needs.safety * 0.32
            + member.needs.belonging * 0.30
            + member.needs.esteem * 0.20
        )

    def _maybe_record_recovery(self, world: CharacterWorld, civilization: "Civilization", context: TickContext) -> None:
        if civilization.unrest > 35.0 or civilization.shortage_streak > 0:
            return
        if civilization.stability < 55.0 and civilization.legitimacy < 55.0:
            return
        if civilization.last_relief_season == (context.year, context.season):
            return

        if civilization.recovery_window > 0 or civilization.food_stores > civilization.seasonal_food_need():
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="recovery",
                    civilization=civilization.name,
                    details=(
                        f"{civilization.ruler.name} stabilized the court and reopened granaries, allowing "
                        f"{civilization.name} to recover its footing."
                    ),
                    severity="normal",
                    data={"ruler": civilization.ruler.name, "ruler_id": civilization.ruler.agent_id},
                )
            )
            civilization.last_relief_season = (context.year, context.season)

    def _defection_memory_bonus(
        self,
        world: CharacterWorld,
        *,
        civilization: "Civilization",
        candidate: "Civilization",
        current_year: int,
    ) -> float:
        score = 0.0
        for event in world.history.get_recent_pair_events(civilization.name, candidate.name, years_back=8, current_year=current_year):
            recency = max(0.30, 1.0 - max(0, current_year - event.year) * 0.12)
            if event.event_type == "diplomatic_aid" and event.civilization == candidate.name:
                score += 8.0 * recency
            elif event.event_type == "defection" and event.civilization == civilization.name and event.other_civilization == candidate.name:
                score += 6.0 * recency
            elif event.event_type in {"diplomatic_peace", "route_reopened"}:
                score += 3.0 * recency
            elif event.event_type in {"battle", "war_declaration", "route_severed"}:
                score -= 9.0 * recency
        return score
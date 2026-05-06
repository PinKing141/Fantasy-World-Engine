from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import SocietyWorld
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization


class SocietySystem:
    phase = Phase.SOCIETY

    def update(self, world: SocietyWorld, context: TickContext) -> None:
        for civilization in world.civilizations:
            if civilization.collapsed:
                continue

            if civilization.shortage_response_cooldown > 0:
                civilization.shortage_response_cooldown -= 1

            if civilization.culture_shift_cooldown > 0:
                civilization.culture_shift_cooldown -= 1

            food_need = civilization.seasonal_food_need()
            available_food = civilization.food_stores
            if available_food < food_need and civilization.grain_stores > 0:
                emergency_rations = min(civilization.grain_stores, food_need - available_food)
                civilization.grain_stores -= emergency_rations
                available_food += emergency_rations

            civilization.food_stores = max(0, civilization.food_stores - food_need)
            shortage = max(0, food_need - available_food)

            if shortage > 0:
                shortage = self._spend_relief(world, civilization, context, shortage, food_need)
                if shortage > 0:
                    self._apply_shortage(world, civilization, context, shortage, food_need)
                else:
                    self._apply_recovery_step(civilization, full=True)
            else:
                self._apply_recovery_step(civilization, full=True)

            self._apply_population_change(civilization, shortage)

            if context.season == "winter":
                world.history.record_event(
                    HistoryEvent(
                        year=context.year,
                        season=context.season,
                        event_type="annual_summary",
                        civilization=civilization.name,
                        details=(
                            f"The year closed with population at {civilization.population}, food stores at "
                            f"{civilization.food_stores}, and stability at {civilization.stability:.1f}."
                        ),
                        severity="minor",
                        data={
                            "population": civilization.population,
                            "food_stores": civilization.food_stores,
                            "stability": round(civilization.stability, 1),
                        },
                    )
                )
                self._maybe_shift_culture(world, civilization, context)

    def _spend_relief(
        self,
        world: SocietyWorld,
        civilization: "Civilization",
        context: TickContext,
        shortage: int,
        food_need: int,
    ) -> int:
        if shortage <= 0 or civilization.treasury <= 0:
            return shortage

        recovery_bias = civilization.ruler.recovery_bias
        if recovery_bias < 45.0 and civilization.recovery_window == 0:
            return shortage

        relief_budget = min(
            civilization.treasury,
            max(0, int(recovery_bias / 8.0 + civilization.recovery_window * 2)),
        )
        if relief_budget <= 0:
            return shortage

        relief_units = min(shortage, relief_budget)
        civilization.treasury -= relief_units
        civilization.food_stores += relief_units
        remaining_shortage = max(0, shortage - relief_units)
        civilization.last_relief_season = (context.year, context.season)

        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="relief_effort",
                civilization=civilization.name,
                details=(
                    f"{civilization.ruler.name} spent the treasury on emergency relief, covering {relief_units} "
                    f"ration units out of a need for {food_need}."
                ),
                severity="normal",
                data={"relief_units": relief_units},
            )
        )
        return remaining_shortage

    def _apply_shortage(
        self,
        world: SocietyWorld,
        civilization: "Civilization",
        context: TickContext,
        shortage: int,
        food_need: int,
    ) -> None:
        shortage_ratio = shortage / max(1, food_need)
        civilization.shortage_streak += 1
        recovery_shield = civilization.ruler.recovery_bias / 100.0
        civilization.unmet_food_pressure += 11.0 * shortage_ratio * (1.10 - recovery_shield * 0.35)
        civilization.stability = max(
            0.0,
            civilization.stability - (5.5 * shortage_ratio + civilization.shortage_streak * (1.0 - recovery_shield * 0.25)),
        )
        civilization.legitimacy = max(
            0.0,
            civilization.legitimacy - (3.4 * shortage_ratio + civilization.shortage_streak * (0.8 - recovery_shield * 0.18)),
        )
        civilization.unrest = min(
            100.0,
            civilization.unrest + 10.0 * shortage_ratio + civilization.shortage_streak * (3.1 - recovery_shield * 0.20),
        )

        shortage_event = world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="food_shortage",
                civilization=civilization.name,
                details=(
                    f"Granaries failed to meet demand in {civilization.name}; {shortage} ration units went unmet "
                    f"for a population of {civilization.population}."
                ),
                severity="major" if shortage_ratio >= 0.35 else "normal",
                data={
                    "shortage": shortage,
                    "need": food_need,
                    "ruler": civilization.ruler.name,
                    "ruler_id": civilization.ruler.agent_id,
                },
            )
        )

        self._apply_shortage_branch(world, civilization, context, shortage_ratio, shortage_event)

        if civilization.unrest >= 35.0:
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="unrest",
                    civilization=civilization.name,
                    details=(
                        f"Food insecurity drove unrest to {civilization.unrest:.1f} in {civilization.name}. "
                        f"Crowds openly blamed the court for empty markets."
                    ),
                    severity="major" if civilization.unrest >= 55.0 else "normal",
                    caused_by=shortage_event.event_id,
                    data={
                        "unrest": round(civilization.unrest, 1),
                        "ruler": civilization.ruler.name,
                        "ruler_id": civilization.ruler.agent_id,
                    },
                )
            )

        if civilization.shortage_streak >= 2 and shortage_ratio >= 0.30:
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="famine",
                    civilization=civilization.name,
                    details=(
                        f"A sustained shortage hardened into famine after {civilization.shortage_streak} bad seasons."
                    ),
                    severity="catastrophic" if shortage_ratio >= 0.50 else "major",
                    caused_by=shortage_event.event_id,
                    data={
                        "ruler": civilization.ruler.name,
                        "ruler_id": civilization.ruler.agent_id,
                        "shortage_streak": civilization.shortage_streak,
                    },
                )
            )

    def _apply_shortage_branch(
        self,
        world: SocietyWorld,
        civilization: "Civilization",
        context: TickContext,
        shortage_ratio: float,
        shortage_event: HistoryEvent,
    ) -> None:
        if shortage_ratio < 0.18 or civilization.shortage_response_cooldown > 0:
            return

        contested_routes = 0
        severed_routes = 0
        for route in world.routes_for(civilization.name):
            if route.state == "contested":
                contested_routes += 1
            elif route.state == "severed":
                severed_routes += 1

        trade_score = severed_routes * 22.0 + contested_routes * 10.0
        military_score = (
            (18.0 if civilization.active_wars else 0.0)
            + civilization.war_exhaustion * 0.65
            + max(0.0, 18.0 - civilization.military.supply_stockpile) * 1.1
        )
        court_score = max(0.0, 42.0 - civilization.legitimacy) * 0.85 + max(0.0, civilization.unrest - 25.0) * 0.25

        branch_scores = {
            "trade_chokepoint": trade_score,
            "military_rationing": military_score,
            "court_hoarding": court_score,
        }
        branch_name, branch_score = max(branch_scores.items(), key=lambda item: item[1])
        if branch_score <= 0.0:
            return

        civilization.shortage_response_cooldown = 2
        if branch_name == "trade_chokepoint":
            civilization.unrest = min(100.0, civilization.unrest + 5.0)
            civilization.stability = max(0.0, civilization.stability - 2.5)
            civilization.unmet_food_pressure += 5.0
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="trade_chokepoint",
                    civilization=civilization.name,
                    details=(
                        f"Route disruption trapped food movement around {civilization.name}; {contested_routes} routes were contested and "
                        f"{severed_routes} were severed while markets were already short."
                    ),
                    severity="major" if severed_routes > 0 else "normal",
                    caused_by=shortage_event.event_id,
                    data={
                        "contested_routes": contested_routes,
                        "severed_routes": severed_routes,
                        "ruler": civilization.ruler.name,
                        "ruler_id": civilization.ruler.agent_id,
                    },
                )
            )
            return

        if branch_name == "military_rationing":
            civilization.war_exhaustion += 7.0
            civilization.stability = max(0.0, civilization.stability - 3.0)
            civilization.court.general.fatigue = min(100.0, civilization.court.general.fatigue + 3.0)
            civilization.court.general.grievance = min(100.0, civilization.court.general.grievance + 5.0)
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="military_rationing",
                    civilization=civilization.name,
                    details=(
                        f"With the frontier under strain, {civilization.name} put garrisons and levies on tighter rations, deepening military exhaustion."
                    ),
                    severity="major" if civilization.active_wars else "normal",
                    caused_by=shortage_event.event_id,
                    data={
                        "war_exhaustion": round(civilization.war_exhaustion, 1),
                        "general": civilization.court.general.name,
                        "general_id": civilization.court.general.agent_id,
                    },
                )
            )
            return

        civilization.legitimacy = max(0.0, civilization.legitimacy - 6.5)
        civilization.unrest = min(100.0, civilization.unrest + 4.5)
        civilization.ruler.grievance = min(100.0, civilization.ruler.grievance + 4.0)
        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="court_hoarding",
                civilization=civilization.name,
                details=(
                    f"Rumors spread that court granaries and local elites were shielding favored households in {civilization.name}, worsening the legitimacy crisis."
                ),
                severity="major" if civilization.legitimacy <= 25.0 else "normal",
                caused_by=shortage_event.event_id,
                data={
                    "legitimacy": round(civilization.legitimacy, 1),
                    "ruler": civilization.ruler.name,
                    "ruler_id": civilization.ruler.agent_id,
                },
            )
        )

    def _apply_population_change(self, civilization: "Civilization", shortage: int) -> None:
        if shortage > 0:
            civilization.population = max(0, civilization.population - int(shortage * 12))
            return

        if civilization.food_stores > civilization.seasonal_food_need() * 2 and civilization.stability >= 55.0:
            civilization.population += max(25, int(civilization.population * 0.0035))

    def _apply_recovery_step(self, civilization: "Civilization", full: bool) -> None:
        civilization.shortage_streak = 0
        recovery_strength = civilization.ruler.recovery_bias / 100.0
        civilization.unmet_food_pressure = max(0.0, civilization.unmet_food_pressure - (8.0 if full else 4.0) * (1.0 + recovery_strength))
        civilization.stability = min(100.0, civilization.stability + (1.8 if full else 1.0) * (1.0 + recovery_strength * 0.35))
        civilization.legitimacy = min(100.0, civilization.legitimacy + (1.2 if full else 0.7) * (1.0 + recovery_strength * 0.30))
        civilization.unrest = max(0.0, civilization.unrest - (5.5 if full else 2.5) * (1.0 + recovery_strength * 0.25))
        if civilization.recovery_window > 0:
            civilization.unrest = max(0.0, civilization.unrest - 1.5)

    def _maybe_shift_culture(self, world: SocietyWorld, civilization: "Civilization", context: TickContext) -> None:
        if civilization.culture_generation >= 1:
            return
        if civilization.culture_shift_cooldown > 0:
            return

        migration_target = None
        migration_score = -999.0
        for route in world.routes_for(civilization.name):
            candidate_name = world.route_partner_name(civilization.name, route)
            if candidate_name is None:
                continue
            candidate = world.get_civilization(candidate_name)
            if candidate is None or candidate.collapsed or candidate.culture_id == civilization.culture_id:
                continue

            score = (
                candidate.food_stores
                - civilization.food_stores
                + (candidate.stability - civilization.stability) * 2.5
                + route.capacity * 1.1
                - route.distance * 4.0
                - route.risk * 30.0
            )
            if score > migration_score:
                migration_score = score
                migration_target = candidate

        migration_pressure = civilization.shortage_streak >= 2 or civilization.unrest >= 58.0
        if migration_pressure and migration_target is not None and migration_score >= 10.0:
            drift_years = max(80, int(context.year * 18 + civilization.shortage_streak * 40 + civilization.unrest))
            new_culture_id = world.drift_culture_for(civilization, suffix="migrated", years=drift_years)
            previous_culture = civilization.culture_id
            civilization.adopt_descendant_culture(new_culture_id)
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="migration",
                    civilization=civilization.name,
                    other_civilization=migration_target.name,
                    details=(
                        f"Caravans and refugee bands from {civilization.name} resettled along routes toward {migration_target.name}, "
                        f"drifting their naming customs from {previous_culture} into {new_culture_id}."
                    ),
                    severity="major",
                    data={"old_culture": previous_culture, "new_culture": new_culture_id, "target": migration_target.name},
                )
            )
            return

        split_pressure = context.year >= 10 and civilization.culture_generation == 0 and civilization.stability >= 54.0
        if not split_pressure:
            return
        if world.rng.random() > 0.12:
            return

        drift_years = max(60, int(context.year * 15 + civilization.legitimacy))
        new_culture_id = world.drift_culture_for(civilization, suffix="split", years=drift_years)
        previous_culture = civilization.culture_id
        civilization.adopt_descendant_culture(new_culture_id)
        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="culture_split",
                civilization=civilization.name,
                details=(
                    f"Court poets and local houses in {civilization.name} codified a distinct descendant culture, "
                    f"drifting names from {previous_culture} into {new_culture_id}."
                ),
                severity="normal",
                data={"old_culture": previous_culture, "new_culture": new_culture_id},
            )
        )
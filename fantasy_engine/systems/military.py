from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import MilitaryWorld
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization


class MilitarySystem:
    phase = Phase.MILITARY

    def update(self, world: MilitaryWorld, context: TickContext) -> None:
        resolved_pairs: set[tuple[str, str]] = set()
        for civilization in world.civilizations:
            if civilization.collapsed:
                continue
            for target_name in list(civilization.active_wars):
                pair = tuple(sorted((civilization.name, target_name)))
                if pair in resolved_pairs:
                    continue
                target = world.get_civilization(target_name)
                if target is None or target.collapsed:
                    civilization.active_wars.discard(target_name)
                    continue
                self._resolve_conflict(world, context, civilization, target)
                resolved_pairs.add(pair)

    def _resolve_conflict(self, world: MilitaryWorld, context: TickContext, civ_a: "Civilization", civ_b: "Civilization") -> None:
        route = world.get_route(civ_a.name, civ_b.name)
        if route is None:
            civ_a.active_wars.discard(civ_b.name)
            civ_b.active_wars.discard(civ_a.name)
            return

        power_a, troops_a, supply_cost_a, arms_loss_a = self._campaign_power(civ_a, route.distance, world)
        power_b, troops_b, supply_cost_b, arms_loss_b = self._campaign_power(civ_b, route.distance, world)
        if power_a >= power_b:
            winner, loser = civ_a, civ_b
            winning_power = power_a
            losing_power = power_b
            winning_troops, losing_troops = troops_a, troops_b
            winning_supply_cost, losing_supply_cost = supply_cost_a, supply_cost_b
            winning_arms_loss, losing_arms_loss = arms_loss_a, arms_loss_b
        else:
            winner, loser = civ_b, civ_a
            winning_power = power_b
            losing_power = power_a
            winning_troops, losing_troops = troops_b, troops_a
            winning_supply_cost, losing_supply_cost = supply_cost_b, supply_cost_a
            winning_arms_loss, losing_arms_loss = arms_loss_b, arms_loss_a

        winner.military.supply_stockpile = max(0, winner.military.supply_stockpile - winning_supply_cost)
        loser.military.supply_stockpile = max(0, loser.military.supply_stockpile - losing_supply_cost)
        winner.military.weapons_stockpile = max(0, winner.military.weapons_stockpile - winning_arms_loss)
        loser.military.weapons_stockpile = max(0, loser.military.weapons_stockpile - losing_arms_loss)

        raid_margin = max(1.0, winning_power - losing_power)
        seized_food = min(loser.food_stores + loser.grain_stores + loser.military.supply_stockpile, max(4, int(raid_margin * 2.0)))
        food_from_store = min(loser.food_stores, seized_food)
        loser.food_stores -= food_from_store
        remaining_capture = seized_food - food_from_store
        if remaining_capture > 0:
            grain_taken = min(loser.grain_stores, remaining_capture)
            loser.grain_stores -= grain_taken
            remaining_capture -= grain_taken
        if remaining_capture > 0:
            loser.military.supply_stockpile = max(0, loser.military.supply_stockpile - remaining_capture)
            winner.military.supply_stockpile += remaining_capture
        winner.food_stores += food_from_store

        casualty_scale = max(15, int(raid_margin * 10 + losing_troops * 0.04))
        loser.population = max(0, loser.population - casualty_scale)
        winner.population = max(0, winner.population - casualty_scale // 3)
        loser.military.standing_forces = max(0, loser.military.standing_forces - max(10, casualty_scale // 2))
        winner.military.standing_forces = max(0, winner.military.standing_forces - max(6, casualty_scale // 6))
        loser.military.levy_pool = max(0, loser.military.levy_pool - casualty_scale)
        winner.military.levy_pool = max(0, winner.military.levy_pool - casualty_scale // 3)

        loser.stability = max(0.0, loser.stability - 6.0)
        loser.legitimacy = max(0.0, loser.legitimacy - 5.0)
        loser.unrest = min(100.0, loser.unrest + 8.0)
        winner.war_exhaustion += 6.0
        loser.war_exhaustion += 10.0
        winner.court.general.add_grudge(loser.name, 6.0)
        loser.court.general.add_grudge(winner.name, 9.0)

        world.history.record_event(
            HistoryEvent(
                year=context.year,
                season=context.season,
                event_type="battle",
                civilization=winner.name,
                other_civilization=loser.name,
                details=(
                    f"{winner.court.general.name} led {winning_troops} troops over the route to {loser.name}, consuming "
                    f"{winning_supply_cost} supplies and seizing {seized_food} provisions after the battle."
                ),
                severity="major",
                data={
                    "general": winner.court.general.name,
                    "general_id": winner.court.general.agent_id,
                    "ruler": winner.ruler.name,
                    "ruler_id": winner.ruler.agent_id,
                    "opposing_general": loser.court.general.name,
                    "opposing_general_id": loser.court.general.agent_id,
                    "opposing_ruler": loser.ruler.name,
                    "opposing_ruler_id": loser.ruler.agent_id,
                    "seized_food": seized_food,
                    "loser": loser.name,
                    "troops": winning_troops,
                    "route": route.key(),
                },
            )
        )

        if self._should_make_peace(winner, loser):
            winner.active_wars.discard(loser.name)
            loser.active_wars.discard(winner.name)
            winner.adjust_relation(loser.name, 14.0)
            loser.adjust_relation(winner.name, 10.0)
            winner.war_exhaustion = max(0.0, winner.war_exhaustion - 8.0)
            loser.war_exhaustion = max(0.0, loser.war_exhaustion - 6.0)
            winner.war_cooldown = max(winner.war_cooldown, 3)
            loser.war_cooldown = max(loser.war_cooldown, 5)
            loser.recovery_window = max(loser.recovery_window, 3)
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="diplomatic_peace",
                    civilization=winner.name,
                    other_civilization=loser.name,
                    details=(
                        f"Exhaustion forced {winner.name} and {loser.name} to accept peace after a season of raiding."
                    ),
                    severity="normal",
                    data={
                        "diplomat": winner.court.diplomat.name,
                        "diplomat_id": winner.court.diplomat.agent_id,
                        "counterpart_diplomat": loser.court.diplomat.name,
                        "counterpart_diplomat_id": loser.court.diplomat.agent_id,
                        "winner_general": winner.court.general.name,
                        "winner_general_id": winner.court.general.agent_id,
                        "loser_general": loser.court.general.name,
                        "loser_general_id": loser.court.general.agent_id,
                    },
                )
            )

    def _should_make_peace(self, winner: "Civilization", loser: "Civilization") -> bool:
        if loser.population <= 0:
            return True
        if winner.war_exhaustion >= 32.0 or loser.war_exhaustion >= 26.0:
            return True
        if loser.food_stores + loser.grain_stores <= loser.seasonal_food_need() and loser.unrest >= 70.0:
            return True
        return False

    def _campaign_power(self, civilization: "Civilization", route_distance: float, world: "World") -> tuple[float, int, int, int]:
        base_troops = civilization.military.standing_forces + min(civilization.military.levy_pool // 4, max(60, civilization.population // 90))
        troops = max(80, base_troops)
        supply_cost = max(6, int((troops / 55.0) * max(1.0, route_distance / 2.0)))
        arms_loss = max(1, int(troops / 180))
        supply_ratio = min(1.1, max(0.35, civilization.military.supply_stockpile / max(1, supply_cost)))
        armed_ratio = min(1.05, max(0.40, civilization.military.weapons_stockpile / max(1, troops / 12)))
        command_ratio = (civilization.court.general.competence + civilization.ruler.authority) / 170.0
        fatigue_ratio = max(0.45, 1.0 - civilization.court.general.fatigue / 140.0)
        power = troops * supply_ratio * armed_ratio * command_ratio * fatigue_ratio * world.rng.uniform(0.88, 1.12) / 16.0
        return power, troops, supply_cost, arms_loss
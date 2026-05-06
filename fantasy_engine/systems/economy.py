from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import EconomyWorld
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent

if TYPE_CHECKING:
    from fantasy_engine.systems.civilization import Civilization


class EconomySystem:
    phase = Phase.ECONOMY

    def update(self, world: EconomyWorld, context: TickContext) -> None:
        for civilization in world.civilizations:
            if civilization.collapsed or civilization.outlook is None:
                continue

            self._harvest(world, civilization, context)
            self._mill_and_store(civilization)
            self._apply_spoilage(civilization)
            self._provision_court(civilization)
            self._provision_military(civilization)
            self._schedule_commerce(world, civilization, context)
            self._attempt_imports(world, civilization, context)

    def _harvest(self, world: EconomyWorld, civilization: "Civilization", context: TickContext) -> None:
        if context.season not in {"summer", "autumn"}:
            civilization.last_harvest = 0
            return

        outlook = civilization.outlook
        if outlook is None:
            civilization.last_harvest = 0
            return

        base_output = civilization.farmland * outlook.harvest_modifier
        seasonal_bias = 0.45 if context.season == "summer" else 0.95
        yield_amount = int(base_output * seasonal_bias * world.rng.uniform(0.72, 1.18))
        civilization.grain_stores += max(0, yield_amount)
        civilization.last_harvest = max(0, yield_amount)

        expected_harvest = int(civilization.farmland * civilization.region.harvest_potential * seasonal_bias)
        if expected_harvest > 0 and yield_amount < int(expected_harvest * 0.70):
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="harvest_shortfall",
                    civilization=civilization.name,
                    details=(
                        f"Harvests in {civilization.region.name} underperformed; only {yield_amount} grain was "
                        f"brought in against an expected {expected_harvest}."
                    ),
                    severity="major" if context.season == "autumn" else "normal",
                    data={"yield": yield_amount, "expected": expected_harvest},
                )
            )

    def _mill_and_store(self, civilization: "Civilization") -> None:
        milling_capacity = max(12, int(civilization.population / 500))
        milled_grain = min(civilization.grain_stores, milling_capacity)
        civilization.grain_stores -= milled_grain
        civilization.food_stores += int(milled_grain * 1.05)

    def _apply_spoilage(self, civilization: "Civilization") -> None:
        outlook = civilization.outlook
        if outlook is None:
            return

        spoilage = int(civilization.food_stores * max(0.02, (outlook.spoilage_modifier - 1.0) * 0.08))
        civilization.food_stores = max(0, civilization.food_stores - spoilage)

    def _provision_court(self, civilization: "Civilization") -> None:
        court_upkeep = max(3, len(civilization.court_members()))
        if civilization.food_stores >= court_upkeep:
            civilization.food_stores -= court_upkeep
        else:
            shortage = court_upkeep - civilization.food_stores
            civilization.food_stores = 0
            for member in civilization.court_members():
                member.grievance = min(100.0, member.grievance + shortage * 0.6)
                member.loyalty = max(0.0, member.loyalty - shortage * 0.4)

    def _provision_military(self, civilization: "Civilization") -> None:
        desired_supply_reserve = max(18, civilization.military.standing_forces // 6)
        if civilization.military.supply_stockpile >= desired_supply_reserve:
            forge_output = min(civilization.treasury // 4, max(1, civilization.population // 3000))
            if forge_output > 0:
                civilization.treasury -= forge_output * 4
                civilization.military.weapons_stockpile += forge_output
            return

        transferable_supplies = min(
            max(0, civilization.food_stores - civilization.seasonal_food_need()),
            max(3, desired_supply_reserve - civilization.military.supply_stockpile),
        )
        if transferable_supplies > 0:
            civilization.food_stores -= transferable_supplies
            civilization.military.supply_stockpile += transferable_supplies

        forge_output = min(civilization.treasury // 4, max(1, civilization.population // 3200))
        if forge_output > 0:
            civilization.treasury -= forge_output * 4
            civilization.military.weapons_stockpile += forge_output

    def _attempt_imports(self, world: EconomyWorld, civilization: "Civilization", context: TickContext) -> None:
        if civilization.food_stores >= civilization.seasonal_food_need():
            return

        best_partner = None
        best_score = -999.0
        for route in world.routes_for(civilization.name):
            if route.state == "severed":
                continue
            partner_name = world.route_partner_name(civilization.name, route)
            if partner_name is None:
                continue
            partner = world.get_civilization(partner_name)
            if partner is None or partner.collapsed or partner_name in civilization.active_wars:
                continue

            surplus = partner.food_stores + partner.grain_stores - partner.seasonal_food_need()
            if surplus <= 0:
                continue
            relation = civilization.relation_with(partner_name)
            travel_cost = route.effective_travel_cost
            score = (
                relation * 0.4
                + surplus * 0.25
                + route.effective_capacity * 0.30
                - travel_cost * 1.3
                - route.effective_risk * 18.0
                + partner.court.diplomat.empathy * 0.1
            )
            if score > best_score:
                best_partner = (partner, route, surplus)
                best_score = score

        if best_partner is None:
            return

        partner, route, surplus = best_partner
        amount = min(max(3, civilization.seasonal_food_need() // 2), route.effective_capacity, surplus)
        if amount <= 0:
            return

        cost_per_food = max(2, int(2 + route.effective_travel_cost * 0.6 + route.effective_risk * 10))
        affordable = max(0, civilization.treasury // cost_per_food)
        if affordable == 0 and civilization.court.steward.competence >= 58.0:
            affordable = min(amount, 3)
        bought_amount = min(amount, affordable)
        if bought_amount <= 0:
            return

        partner_food = min(partner.food_stores, bought_amount)
        partner.food_stores -= partner_food
        remainder = bought_amount - partner_food
        if remainder > 0:
            partner.grain_stores = max(0, partner.grain_stores - remainder)
        civilization.treasury -= bought_amount * cost_per_food
        partner.treasury += bought_amount * cost_per_food
        world.queue_shipment(
            origin=partner.name,
            destination=civilization.name,
            resource_type="grain",
            amount=bought_amount,
            kind="trade",
            context=context,
            sender_name=partner.court.diplomat.name,
            receiver_name=civilization.court.diplomat.name,
            treasury_cost=bought_amount * cost_per_food,
        )

    def _schedule_commerce(self, world: EconomyWorld, civilization: "Civilization", context: TickContext) -> None:
        own_stock = civilization.food_stores + civilization.grain_stores
        if own_stock <= civilization.seasonal_food_need() * 2:
            return

        for route in world.routes_for(civilization.name):
            if route.state == "severed":
                continue
            partner_name = world.route_partner_name(civilization.name, route)
            if partner_name is None:
                continue
            partner = world.get_civilization(partner_name)
            if partner is None or partner.collapsed or partner_name in civilization.active_wars:
                continue

            partner_stock = partner.food_stores + partner.grain_stores
            stock_gap = own_stock - partner_stock
            if stock_gap <= route.effective_capacity:
                continue

            shipment_amount = min(
                route.effective_capacity,
                max(3, stock_gap // 4),
                max(0, civilization.grain_stores - civilization.seasonal_food_need()),
            )
            if shipment_amount <= 0:
                continue

            civilization.grain_stores -= shipment_amount
            revenue = shipment_amount * max(1, int(1 + route.effective_travel_cost * 0.25))
            civilization.treasury += revenue
            partner.treasury = max(0, partner.treasury - revenue)
            world.queue_shipment(
                origin=civilization.name,
                destination=partner.name,
                resource_type="grain",
                amount=shipment_amount,
                kind="trade",
                context=context,
                sender_name=civilization.court.diplomat.name,
                receiver_name=partner.court.diplomat.name,
                treasury_cost=revenue,
            )
            break
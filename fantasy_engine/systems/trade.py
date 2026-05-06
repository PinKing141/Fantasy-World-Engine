from __future__ import annotations

from typing import TYPE_CHECKING

from fantasy_engine.app.protocols import TradeWorld
from fantasy_engine.core.engine import Phase, TickContext
from fantasy_engine.core.events import HistoryEvent
from fantasy_engine.world.routes import Shipment

if TYPE_CHECKING:
    from fantasy_engine.world.routes import TradeRoute


class TradeSystem:
    phase = Phase.TRADE

    def update(self, world: TradeWorld, context: TickContext) -> None:
        route_load: dict[tuple[str, str], int] = {}
        delivered_shipments: list[Shipment] = []
        remaining_shipments: list[Shipment] = []

        for shipment in world.pending_shipments:
            route = world.trade_routes.get(shipment.route_key)
            if route is None:
                continue
            if route.state == "severed":
                remaining_shipments.append(shipment)
                continue
            load = route_load.get(shipment.route_key, 0)
            available_capacity = max(0, route.effective_capacity - load)
            if available_capacity <= 0:
                remaining_shipments.append(shipment)
                continue

            moved_amount = min(shipment.amount, available_capacity)
            route_load[shipment.route_key] = load + moved_amount
            delivered_shipments.append(
                Shipment(
                    route_key=shipment.route_key,
                    origin=shipment.origin,
                    destination=shipment.destination,
                    resource_type=shipment.resource_type,
                    amount=moved_amount,
                    kind=shipment.kind,
                    season=shipment.season,
                    year=shipment.year,
                    sender_name=shipment.sender_name,
                    receiver_name=shipment.receiver_name,
                    treasury_cost=shipment.treasury_cost,
                )
            )
            if shipment.amount > moved_amount:
                shipment.amount -= moved_amount
                remaining_shipments.append(shipment)

        world.pending_shipments = remaining_shipments
        for shipment in delivered_shipments:
            self._deliver(world, context, shipment)

    def _deliver(self, world: TradeWorld, context: TickContext, shipment: "Shipment") -> None:
        route = world.trade_routes[shipment.route_key]
        destination = world.get_civilization(shipment.destination)
        if destination is None or destination.collapsed:
            return
        if route.state == "severed":
            return
        if shipment.destination in world.get_civilization(shipment.origin).active_wars:
            return

        seasonal_risk = route.effective_risk + (0.08 if context.season == "winter" else 0.0)
        losses = int(shipment.amount * seasonal_risk)
        delivered_amount = max(0, shipment.amount - losses)
        if delivered_amount <= 0:
            return

        if shipment.resource_type == "food":
            destination.food_stores += delivered_amount
        elif shipment.resource_type == "grain":
            destination.grain_stores += delivered_amount
        elif shipment.resource_type == "supplies":
            destination.military.supply_stockpile += delivered_amount
        elif shipment.resource_type == "arms":
            destination.military.weapons_stockpile += delivered_amount

        if shipment.kind == "trade":
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="trade_shipment",
                    civilization=shipment.origin,
                    other_civilization=shipment.destination,
                    details=(
                        f"A caravan reached {shipment.destination} from {shipment.origin} over the {route.state} {route.region_a}-{route.region_b} route, "
                        f"delivering {delivered_amount} {shipment.resource_type}."
                    ),
                    severity="major" if route.state == "contested" else "normal",
                    data={"route": shipment.route_key, "resource": shipment.resource_type, "delivered": delivered_amount},
                )
            )
        elif shipment.kind == "aid":
            world.history.record_event(
                HistoryEvent(
                    year=context.year,
                    season=context.season,
                    event_type="diplomatic_aid",
                    civilization=shipment.origin,
                    other_civilization=shipment.destination,
                    details=(
                        f"{shipment.sender_name} sent relief to {shipment.destination} by caravan over a {route.state} route, and "
                        f"{delivered_amount} {shipment.resource_type} arrived."
                    ),
                    severity="major" if delivered_amount >= 8 or route.state == "contested" else "normal",
                    data={"route": shipment.route_key, "resource": shipment.resource_type, "delivered": delivered_amount},
                )
            )
from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from fantasy_engine.core.events import HistoryArchive
from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.systems.civilization import Civilization
from fantasy_engine.world.routes import Shipment, TradeRoute


class HasCivilizations(Protocol):
    civilizations: Sequence[Civilization]


class HasHistory(Protocol):
    history: HistoryArchive


class HasRng(Protocol):
    rng: SeededRNG


class HasTradeRoutes(Protocol):
    trade_routes: Mapping[tuple[str, str], TradeRoute]


class HasPendingShipments(Protocol):
    pending_shipments: list[Shipment]


class HasCivilizationLookup(Protocol):
    def get_civilization(self, name: str) -> Civilization | None: ...


class HasRouteQueries(Protocol):
    def get_route(self, civ_a: str, civ_b: str) -> TradeRoute | None: ...

    def routes_for(self, civilization_name: str) -> list[TradeRoute]: ...

    def route_partner_name(self, civilization_name: str, route: TradeRoute) -> str | None: ...


class HasShipmentQueue(Protocol):
    def queue_shipment(
        self,
        *,
        origin: str,
        destination: str,
        resource_type: str,
        amount: int,
        kind: str,
        context,
        sender_name: str | None = None,
        receiver_name: str | None = None,
        treasury_cost: int = 0,
    ) -> None: ...


class HasCultureDrift(Protocol):
    def drift_culture_for(self, civilization: Civilization, *, suffix: str, years: int) -> str: ...


class CharacterWorld(HasCivilizations, HasHistory, HasRng, HasRouteQueries, HasCivilizationLookup, Protocol):
    pass


class EconomyWorld(HasCivilizations, HasHistory, HasRng, HasRouteQueries, HasCivilizationLookup, HasShipmentQueue, Protocol):
    pass


class DiplomacyWorld(HasCivilizations, HasHistory, HasRouteQueries, HasCivilizationLookup, HasShipmentQueue, Protocol):
    pass


class FactionWorld(HasCivilizations, HasHistory, HasRng, HasRouteQueries, HasCivilizationLookup, Protocol):
    pass


class MilitaryWorld(HasCivilizations, HasHistory, HasRng, HasRouteQueries, HasCivilizationLookup, Protocol):
    pass


class SocietyWorld(HasCivilizations, HasHistory, HasRng, HasRouteQueries, HasCivilizationLookup, HasCultureDrift, Protocol):
    pass


class TradeWorld(HasHistory, HasTradeRoutes, HasPendingShipments, HasCivilizationLookup, Protocol):
    pass


class DashboardWorldView(HasCivilizations, HasTradeRoutes, Protocol):
    def route_state_counts(self, civilization_name: str) -> tuple[int, int]: ...
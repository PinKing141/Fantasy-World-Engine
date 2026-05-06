from __future__ import annotations

from fantasy_engine.app.protocols import DashboardWorldView
from fantasy_engine.world.world import World


class WorldDashboardAdapter(DashboardWorldView):
    def __init__(self, world: World) -> None:
        self._world = world
        self.civilizations = world.civilizations
        self.trade_routes = world.trade_routes

    def route_state_counts(self, civilization_name: str) -> tuple[int, int]:
        return self._world.route_state_counts(civilization_name)
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RouteTerrain:
    name: str
    travel_difficulty: float
    exposure: float
    chokepoint: float


@dataclass(slots=True)
class TradeRoute:
    region_a: str
    region_b: str
    distance: float
    capacity: int
    risk: float
    terrain: RouteTerrain
    state: str = "open"
    disrupted_by: tuple[str, ...] = ()

    def key(self) -> tuple[str, str]:
        return tuple(sorted((self.region_a, self.region_b)))

    def connects(self, name_a: str, name_b: str) -> bool:
        return self.key() == tuple(sorted((name_a, name_b)))

    def endpoint_for(self, name: str) -> str | None:
        if name == self.region_a:
            return self.region_b
        if name == self.region_b:
            return self.region_a
        return None

    @property
    def effective_capacity(self) -> int:
        if self.state == "severed":
            return 0
        if self.state == "contested":
            return max(1, int(self.capacity * 0.45))
        return self.capacity

    @property
    def effective_risk(self) -> float:
        if self.state == "severed":
            return 1.0
        if self.state == "contested":
            return min(0.95, self.risk + 0.18)
        return self.risk

    @property
    def effective_travel_cost(self) -> float:
        if self.state == "severed":
            return self.distance * self.terrain.travel_difficulty * 2.0
        if self.state == "contested":
            return self.distance * self.terrain.travel_difficulty * 1.35
        return self.distance * self.terrain.travel_difficulty

    def mark_open(self) -> None:
        self.state = "open"
        self.disrupted_by = ()

    def mark_contested(self, *civilizations: str) -> None:
        self.state = "contested"
        self.disrupted_by = tuple(sorted({civilization for civilization in civilizations if civilization}))

    def mark_severed(self, *civilizations: str) -> None:
        self.state = "severed"
        self.disrupted_by = tuple(sorted({civilization for civilization in civilizations if civilization}))


@dataclass(slots=True)
class Shipment:
    route_key: tuple[str, str]
    origin: str
    destination: str
    resource_type: str
    amount: int
    kind: str
    season: str
    year: int
    sender_name: str | None = None
    receiver_name: str | None = None
    treasury_cost: int = 0
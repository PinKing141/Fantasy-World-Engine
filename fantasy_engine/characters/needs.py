from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


@dataclass(slots=True)
class AgentNeeds:
    food: float = 0.0
    safety: float = 0.0
    belonging: float = 0.0
    esteem: float = 0.0

    @property
    def total(self) -> float:
        return self.food + self.safety + self.belonging + self.esteem

    def set_levels(self, *, food: float, safety: float, belonging: float, esteem: float) -> None:
        self.food = _clamp(food)
        self.safety = _clamp(safety)
        self.belonging = _clamp(belonging)
        self.esteem = _clamp(esteem)


@dataclass(frozen=True, slots=True)
class NeedWeights:
    food: float = 1.0
    safety: float = 1.0
    belonging: float = 1.0
    esteem: float = 1.0


DEFAULT_WEIGHTS = NeedWeights()
ROLE_WEIGHTS: dict[str, NeedWeights] = {
    "Ruler": NeedWeights(food=0.90, safety=1.05, belonging=0.95, esteem=1.30),
    "Heir": NeedWeights(food=0.95, safety=1.00, belonging=1.10, esteem=1.15),
    "General": NeedWeights(food=0.95, safety=1.25, belonging=0.95, esteem=1.10),
    "Diplomat": NeedWeights(food=0.90, safety=0.95, belonging=1.20, esteem=1.05),
    "Steward": NeedWeights(food=1.20, safety=0.95, belonging=1.00, esteem=0.95),
    "Military Leader": NeedWeights(food=0.95, safety=1.20, belonging=0.90, esteem=1.10),
    "Noble Speaker": NeedWeights(food=0.85, safety=0.95, belonging=1.00, esteem=1.25),
    "Commoner Tribune": NeedWeights(food=1.25, safety=1.00, belonging=1.10, esteem=1.00),
}


def update_agent_needs(agent: "Agent", civilization: "Civilization") -> AgentNeeds:
    weights = ROLE_WEIGHTS.get(agent.role, DEFAULT_WEIGHTS)
    needs = agent.needs

    seasonal_need = max(1, civilization.seasonal_food_need())
    food_buffer = civilization.food_stores + civilization.grain_stores * 0.45
    food_cover = food_buffer / seasonal_need
    food_target = (
        civilization.unmet_food_pressure * 0.90
        + max(0.0, 1.40 - food_cover) * 34.0
        + civilization.shortage_streak * 7.0
    ) * weights.food
    if civilization.recovery_window > 0:
        food_target -= 8.0

    safety_target = (
        civilization.unrest * 0.55
        + civilization.war_exhaustion * 0.42
        + (16.0 if civilization.active_wars else 0.0)
        + max(0.0, 42.0 - civilization.stability) * 0.75
    ) * weights.safety
    if civilization.recovery_window > 0:
        safety_target -= 5.0

    belonging_target = (
        max(0.0, 55.0 - civilization.legitimacy) * 0.55
        + civilization.unrest * 0.28
        + max(0.0, 50.0 - agent.loyalty) * 0.35
        + agent.grievance * 0.12
    ) * weights.belonging
    if civilization.recovery_window > 0:
        belonging_target -= 4.0

    esteem_target = (
        max(0.0, 52.0 - civilization.legitimacy) * 0.30
        + max(0.0, 48.0 - agent.authority) * 0.45
        + max(0.0, 50.0 - agent.competence) * 0.20
        + agent.grievance * 0.18
    ) * weights.esteem
    if agent.role == "Ruler":
        esteem_target += max(0.0, 50.0 - civilization.stability) * 0.20
    if civilization.recovery_window > 0:
        esteem_target -= 4.0

    needs.set_levels(
        food=_move_toward(needs.food, food_target),
        safety=_move_toward(needs.safety, safety_target),
        belonging=_move_toward(needs.belonging, belonging_target),
        esteem=_move_toward(needs.esteem, esteem_target),
    )
    return needs


def _move_toward(current: float, target: float) -> float:
    target = _clamp(target)
    if target >= current:
        return _clamp(current + (target - current) * 0.34)
    return _clamp(current - (current - target) * 0.22)
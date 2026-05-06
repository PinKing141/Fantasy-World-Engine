from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_engine.characters.needs import AgentNeeds
from fantasy_engine.characters.names import get_default_name_registry
from fantasy_engine.core.rng import SeededRNG


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


@dataclass(slots=True)
class Agent:
    agent_id: str
    name: str
    given_name: str
    byname: str | None
    dynasty_name: str | None
    home_civilization: str
    gender: str
    culture_id: str
    role: str
    age: int
    health: float
    competence: float
    ambition: float
    caution: float
    empathy: float
    aggression: float
    loyalty: float
    authority: float
    grievance: float = 0.0
    fatigue: float = 0.0
    alive: bool = True
    parent_ids: tuple[str, ...] = ()
    grudges: dict[str, float] = field(default_factory=dict)
    needs: AgentNeeds = field(default_factory=AgentNeeds)

    @classmethod
    def create(
        cls,
        rng: SeededRNG,
        civilization_name: str,
        role: str,
        *,
        culture_id: str = "frontier",
        parent: "Agent" | None = None,
        co_parent: "Agent" | None = None,
        parent_name: str | None = None,
        dynasty_name: str | None = None,
    ) -> "Agent":
        gender = "male" if rng.random() < 0.55 else "female"
        parent_given_name = parent.given_name if parent is not None else (parent_name.split()[0] if parent_name else None)
        inherited_dynasty = dynasty_name or (parent.dynasty_name if parent is not None else None) or (co_parent.dynasty_name if co_parent is not None else None)
        generated_name = get_default_name_registry().generate(
            culture_id,
            rng,
            gender=gender,
            role=role,
            parent_given_name=parent_given_name,
            lineage_name=inherited_dynasty,
        )
        age = rng.randint(14, 22) if role == "Heir" else rng.randint(24, 58)
        health = rng.uniform(55.0, 100.0)

        competence = rng.uniform(40.0, 82.0)
        ambition = rng.uniform(25.0, 85.0)
        caution = rng.uniform(20.0, 80.0)
        empathy = rng.uniform(20.0, 85.0)
        aggression = rng.uniform(15.0, 85.0)
        loyalty = rng.uniform(30.0, 88.0)
        authority = rng.uniform(42.0, 78.0)

        if role == "Ruler":
            authority += 8.0
            loyalty += 6.0
        elif role == "Military Leader":
            aggression += 10.0
            competence += 5.0
        elif role == "Commoner Tribune":
            empathy += 10.0
        elif role == "Noble Speaker":
            ambition += 8.0

        return cls(
            agent_id=f"{civilization_name}_{role}_{generated_name.full_name.replace(' ', '_')}_{rng.randint(1000, 9999)}",
            name=generated_name.full_name,
            given_name=generated_name.given_name,
            byname=generated_name.byname,
            dynasty_name=generated_name.lineage_name,
            home_civilization=civilization_name,
            gender=generated_name.gender,
            culture_id=generated_name.culture_id,
            role=role,
            age=age,
            health=clamp(health),
            competence=clamp(competence),
            ambition=clamp(ambition),
            caution=clamp(caution),
            empathy=clamp(empathy),
            aggression=clamp(aggression),
            loyalty=clamp(loyalty),
            authority=clamp(authority),
            parent_ids=tuple(
                ancestor.agent_id
                for ancestor in (parent, co_parent)
                if ancestor is not None
            ),
        )

    @property
    def recovery_bias(self) -> float:
        return clamp((self.competence + self.caution + self.empathy + self.loyalty - self.ambition * 0.25) / 3.2)

    @property
    def crisis_aggression(self) -> float:
        return clamp((self.aggression + self.ambition + max(0.0, 55.0 - self.empathy)) / 2.4)

    @property
    def regime_skill(self) -> float:
        return clamp((self.competence + self.authority + self.loyalty) / 3.0)

    def retitle(self, role: str) -> None:
        self.role = role
        if role == "Ruler":
            self.authority = clamp(self.authority + 10.0)
            self.loyalty = clamp(self.loyalty + 6.0)

    def add_grudge(self, target: str, amount: float) -> None:
        self.grudges[target] = clamp(self.grudges.get(target, 0.0) + amount)

    def grudge_toward(self, target: str) -> float:
        return self.grudges.get(target, 0.0)
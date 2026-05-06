from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_engine.characters.person import Agent, clamp
from fantasy_engine.core.rng import SeededRNG
from fantasy_engine.world.climate import SeasonalOutlook
from fantasy_engine.world.map import Region


@dataclass(slots=True)
class Faction:
    name: str
    agenda: str
    influence: float
    leader: Agent
    pressure: float = 0.0


@dataclass(slots=True)
class MilitaryState:
    standing_forces: int
    levy_pool: int
    weapons_stockpile: int
    supply_stockpile: int
    campaigning_troops: int = 0


@dataclass(slots=True)
class CourtRoster:
    ruler: Agent
    heir: Agent
    general: Agent
    diplomat: Agent
    steward: Agent


@dataclass(slots=True)
class Civilization:
    REGION_CULTURES = {
        "Greenreach Vale": "frontier",
        "Ashen Steppe": "highland",
        "Ironroot Basin": "imperial",
        "Stormcoast March": "coastal",
        "Frostmere": "northlands",
        "Sunscar Flats": "desert",
    }

    name: str
    region: Region
    culture_id: str
    population: int
    farmland: int
    grain_stores: int
    food_stores: int
    treasury: int
    stability: float
    legitimacy: float
    ruler: Agent
    court: CourtRoster
    military: MilitaryState
    factions: list[Faction] = field(default_factory=list)
    relations: dict[str, float] = field(default_factory=dict)
    active_wars: set[str] = field(default_factory=set)
    outlook: SeasonalOutlook | None = None
    unmet_food_pressure: float = 0.0
    unrest: float = 0.0
    shortage_streak: int = 0
    shortage_response_cooldown: int = 0
    last_harvest: int = 0
    coup_cooldown: int = 0
    relief_cooldown: int = 0
    recovery_window: int = 0
    war_exhaustion: float = 0.0
    war_cooldown: int = 0
    last_relief_season: tuple[int, str] | None = None
    culture_origin_id: str | None = None
    culture_generation: int = 0
    culture_shift_cooldown: int = 0

    @classmethod
    def from_region(cls, name: str, region: Region, rng: SeededRNG) -> "Civilization":
        culture_id = cls.REGION_CULTURES.get(region.name, "frontier")
        farmland = rng.randint(55, 105)
        population = rng.randint(7000, 17000)
        grain_stores = rng.randint(70, 140)
        food_stores = rng.randint(40, 95)
        treasury = rng.randint(75, 150)
        stability = rng.uniform(48.0, 72.0)
        legitimacy = rng.uniform(42.0, 76.0)
        ruler = Agent.create(rng, name, "Ruler", culture_id=culture_id)
        court = CourtRoster(
            ruler=ruler,
            heir=Agent.create(rng, name, "Heir", culture_id=culture_id, parent=ruler, dynasty_name=ruler.dynasty_name),
            general=Agent.create(rng, name, "General", culture_id=culture_id),
            diplomat=Agent.create(rng, name, "Diplomat", culture_id=culture_id),
            steward=Agent.create(rng, name, "Steward", culture_id=culture_id),
        )
        military = MilitaryState(
            standing_forces=rng.randint(420, 920),
            levy_pool=rng.randint(900, 2200),
            weapons_stockpile=rng.randint(80, 160),
            supply_stockpile=rng.randint(20, 55),
        )
        factions = [
            Faction(
                name="Commoners",
                agenda="food security",
                influence=rng.uniform(0.35, 0.55),
                leader=Agent.create(rng, name, "Commoner Tribune", culture_id=culture_id),
            ),
            Faction(
                name="Nobility",
                agenda="legitimacy",
                influence=rng.uniform(0.20, 0.35),
                leader=Agent.create(rng, name, "Noble Speaker", culture_id=culture_id),
            ),
            Faction(
                name="Military",
                agenda="order",
                influence=rng.uniform(0.18, 0.30),
                leader=Agent.create(rng, name, "Military Leader", culture_id=culture_id),
            ),
        ]
        return cls(
            name=name,
            region=region,
            culture_id=culture_id,
            population=population,
            farmland=farmland,
            grain_stores=grain_stores,
            food_stores=food_stores,
            treasury=treasury,
            stability=stability,
            legitimacy=legitimacy,
            ruler=ruler,
            court=court,
            military=military,
            factions=factions,
            culture_origin_id=culture_id,
        )

    @property
    def route_cost(self) -> float:
        return self.region.route_cost

    @property
    def collapsed(self) -> bool:
        return self.population <= 0

    def faction_by_name(self, name: str) -> Faction | None:
        for faction in self.factions:
            if faction.name == name:
                return faction
        return None

    def relation_with(self, other_name: str) -> float:
        return self.relations.get(other_name, 0.0)

    def adjust_relation(self, other_name: str, delta: float) -> None:
        self.relations[other_name] = clamp(self.relation_with(other_name) + delta, -100.0, 100.0)

    def court_members(self) -> list[Agent]:
        return [self.court.ruler, self.court.heir, self.court.general, self.court.diplomat, self.court.steward]

    def court_member(self, role: str) -> Agent | None:
        normalized = role.lower()
        if normalized == "ruler":
            return self.court.ruler
        if normalized == "heir":
            return self.court.heir
        if normalized == "general":
            return self.court.general
        if normalized == "diplomat":
            return self.court.diplomat
        if normalized == "steward":
            return self.court.steward
        return None

    def replace_court_member(
        self,
        rng: SeededRNG,
        role: str,
        *,
        parent: Agent | None = None,
        parent_name: str | None = None,
        dynasty_name: str | None = None,
    ) -> Agent:
        lineage_parent = parent or self.court_member(role) or self.ruler
        inherited_dynasty = dynasty_name or (lineage_parent.dynasty_name if lineage_parent is not None else self.ruler.dynasty_name)
        replacement = Agent.create(
            rng,
            self.name,
            role,
            culture_id=self.culture_id,
            parent=lineage_parent,
            parent_name=parent_name,
            dynasty_name=inherited_dynasty,
        )
        if role == "Ruler":
            self.court.ruler = replacement
            self.ruler = replacement
        elif role == "Heir":
            self.court.heir = replacement
        elif role == "General":
            self.court.general = replacement
        elif role == "Diplomat":
            self.court.diplomat = replacement
        elif role == "Steward":
            self.court.steward = replacement
        return replacement

    def promote_heir(self, rng: SeededRNG) -> tuple[Agent, Agent]:
        old_ruler = self.ruler
        new_ruler = self.court.heir
        new_ruler.retitle("Ruler")
        self.court.ruler = new_ruler
        self.ruler = new_ruler
        self.replace_court_member(rng, "Heir", parent=new_ruler, dynasty_name=new_ruler.dynasty_name)
        return old_ruler, new_ruler

    def adopt_descendant_culture(self, new_culture_id: str) -> None:
        self.culture_id = new_culture_id
        self.culture_generation += 1
        self.culture_shift_cooldown = 12
        for member in self.court_members():
            member.culture_id = new_culture_id
        for faction in self.factions:
            faction.leader.culture_id = new_culture_id

    def force_projection(self) -> float:
        commanded_troops = self.military.standing_forces + min(self.military.levy_pool // 5, max(0, self.population // 60))
        armed_ratio = min(1.0, self.military.weapons_stockpile / max(1, commanded_troops // 10))
        supply_ratio = min(1.2, max(0.35, self.military.supply_stockpile / max(1, commanded_troops // 12)))
        command_factor = (self.court.general.competence + self.ruler.authority) / 180.0
        exhaustion_term = max(0.35, 1.0 - self.war_exhaustion / 120.0)
        order_term = max(0.25, self.stability / 100.0)
        return commanded_troops * armed_ratio * supply_ratio * command_factor * exhaustion_term * order_term / 12.0

    def seasonal_food_need(self) -> int:
        outlook = self.outlook.consumption_modifier if self.outlook else 1.0
        return max(10, int((self.population / 450.0) * outlook))

    def status_line(self) -> str:
        return (
            f"{self.name}: culture={self.culture_id}, ruler={self.ruler.name}, pop={self.population}, grain={self.grain_stores}, "
            f"food={self.food_stores}, arms={self.military.weapons_stockpile}, supplies={self.military.supply_stockpile}, "
            f"stability={self.stability:.1f}, legitimacy={self.legitimacy:.1f}, unrest={self.unrest:.1f}, wars={len(self.active_wars)}"
        )
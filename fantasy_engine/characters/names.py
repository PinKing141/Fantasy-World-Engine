from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from fantasy_engine.core.rng import SeededRNG


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.strip().split())


@dataclass(frozen=True, slots=True)
class GeneratedName:
    full_name: str
    given_name: str
    byname: str | None
    lineage_name: str | None
    gender: str
    culture_id: str


class MarkovNameGenerator:
    def __init__(self, order: int = 3) -> None:
        self.order = max(1, order)
        self._chains: dict[str, list[str | None]] = defaultdict(list)
        self._starts: list[str] = []
        self._trained_names: set[str] = set()
        self._fallback_names: list[str] = []

    def train(self, names: list[str]) -> None:
        for raw_name in names:
            normalized = "".join(character for character in raw_name.lower().strip() if character.isalpha())
            if len(normalized) <= self.order:
                continue

            self._trained_names.add(normalized)
            self._fallback_names.append(_title_case(raw_name))
            self._starts.append(normalized[: self.order])

            for index in range(len(normalized) - self.order):
                key = normalized[index : index + self.order]
                self._chains[key].append(normalized[index + self.order])

            end_key = normalized[-self.order :]
            self._chains[end_key].append(None)

    def generate(
        self,
        rng: SeededRNG,
        *,
        min_length: int = 4,
        max_length: int = 10,
        blocked: set[str] | None = None,
    ) -> str:
        blocked_names = blocked or set()
        if not self._starts:
            return "Nameless"

        for _ in range(80):
            current = rng.choice(self._starts)
            name = current
            while len(name) < max_length:
                key = name[-self.order :]
                next_options = self._chains.get(key, [None])
                next_character = rng.choice(next_options)
                if next_character is None:
                    break
                name += next_character

            if len(name) < min_length:
                continue

            candidate = _title_case(name)
            candidate_key = candidate.lower()
            if candidate_key in blocked_names:
                continue
            if candidate_key in self._trained_names and rng.random() < 0.70:
                continue
            return candidate

        for fallback in self._fallback_names:
            if fallback.lower() not in blocked_names:
                return fallback
        return _title_case(rng.choice(self._fallback_names))


class CultureNameSystem:
    def __init__(self, culture_id: str, data: dict[str, Any], order: int = 3) -> None:
        self.culture_id = culture_id
        self.order = order
        self.structure = data.get("structure", "family")
        self.family_name_first = bool(data.get("family_name_first", False))
        self.patronymic_style = data.get("patronymic_style", "suffix")
        self.patronymic_suffixes = data.get("patronymic_suffixes", {"male": "son", "female": "dottir"})
        self.patronymic_particles = data.get("patronymic_particles", {"male": "ibn", "female": "bint"})
        self.epithets = data.get("epithets", {})
        self.seed_data = deepcopy(data)

        self._given_generators = {
            "male": self._build_generator(data.get("male", []), order),
            "female": self._build_generator(data.get("female", []), order),
        }

        family_seeds = data.get("family") or data.get("clans") or data.get("male", []) + data.get("female", [])
        self._family_generator = self._build_generator(family_seeds, order)
        clan_seeds = data.get("clans") or family_seeds
        self._clan_generator = self._build_generator(clan_seeds, order)

    def _build_generator(self, names: list[str], order: int) -> MarkovNameGenerator:
        generator = MarkovNameGenerator(order=order)
        generator.train(list(names))
        return generator

    def generate_person_name(
        self,
        rng: SeededRNG,
        *,
        gender: str,
        role: str = "Commoner",
        parent_given_name: str | None = None,
        lineage_name: str | None = None,
        blocked: set[str] | None = None,
    ) -> GeneratedName:
        given_generator = self._given_generators[gender]
        given_name = given_generator.generate(rng, blocked=blocked)

        if self.structure == "patronymic":
            return self._generate_patronymic_name(rng, gender, given_name, parent_given_name, lineage_name)
        if self.structure == "clan":
            return self._generate_clan_name(rng, gender, given_name, lineage_name, blocked)
        if self.structure == "epithet":
            return self._generate_epithet_name(rng, gender, given_name, role, lineage_name)
        return self._generate_family_name(rng, gender, given_name, lineage_name, blocked)

    def generate_dynasty_name(self, rng: SeededRNG, blocked: set[str] | None = None) -> str:
        blocked_names = blocked or set()
        if self.structure == "clan":
            return self._clan_generator.generate(rng, blocked=blocked_names)
        return self._family_generator.generate(rng, blocked=blocked_names)

    def _generate_family_name(
        self,
        rng: SeededRNG,
        gender: str,
        given_name: str,
        lineage_name: str | None,
        blocked: set[str] | None,
    ) -> GeneratedName:
        family_name = lineage_name or self._family_generator.generate(rng, blocked=blocked)
        if self.family_name_first:
            full_name = f"{family_name} {given_name}"
        else:
            full_name = f"{given_name} {family_name}"
        return GeneratedName(
            full_name=full_name,
            given_name=given_name,
            byname=family_name,
            lineage_name=family_name,
            gender=gender,
            culture_id=self.culture_id,
        )

    def _generate_clan_name(
        self,
        rng: SeededRNG,
        gender: str,
        given_name: str,
        lineage_name: str | None,
        blocked: set[str] | None,
    ) -> GeneratedName:
        clan_name = lineage_name or self._clan_generator.generate(rng, blocked=blocked)
        full_name = f"{clan_name} {given_name}" if self.family_name_first else f"{given_name} {clan_name}"
        return GeneratedName(
            full_name=full_name,
            given_name=given_name,
            byname=clan_name,
            lineage_name=clan_name,
            gender=gender,
            culture_id=self.culture_id,
        )

    def _generate_patronymic_name(
        self,
        rng: SeededRNG,
        gender: str,
        given_name: str,
        parent_given_name: str | None,
        lineage_name: str | None,
    ) -> GeneratedName:
        parent_source = parent_given_name or self._given_generators["male"].generate(rng)
        if self.patronymic_style == "particle":
            particle = self.patronymic_particles.get(gender, self.patronymic_particles.get("male", "ibn"))
            byname = f"{particle} {parent_source}"
        else:
            suffix = self.patronymic_suffixes.get(gender, self.patronymic_suffixes.get("male", "son"))
            root = self._derive_patronymic_root(parent_source)
            byname = f"{root}{suffix}"
        return GeneratedName(
            full_name=f"{given_name} {byname}",
            given_name=given_name,
            byname=byname,
            lineage_name=lineage_name,
            gender=gender,
            culture_id=self.culture_id,
        )

    def _generate_epithet_name(
        self,
        rng: SeededRNG,
        gender: str,
        given_name: str,
        role: str,
        lineage_name: str | None,
    ) -> GeneratedName:
        category = self._epithet_category(role)
        pool = self.epithets.get(category) or self.epithets.get("general") or ["the Unknown"]
        epithet = rng.choice(pool)
        return GeneratedName(
            full_name=f"{given_name} {epithet}",
            given_name=given_name,
            byname=epithet,
            lineage_name=lineage_name,
            gender=gender,
            culture_id=self.culture_id,
        )

    def _epithet_category(self, role: str) -> str:
        lowered = role.lower()
        if "military" in lowered or "general" in lowered:
            return "combat"
        if "ruler" in lowered or "noble" in lowered:
            return "nobility"
        if "priest" in lowered:
            return "faith"
        if "scholar" in lowered or "scribe" in lowered:
            return "learning"
        if "diplomat" in lowered:
            return "diplomacy"
        return "general"

    def _derive_patronymic_root(self, name: str) -> str:
        cleaned = "".join(character for character in name.lower() if character.isalpha())
        if len(cleaned) > 7:
            cleaned = cleaned[:7]
        if cleaned.endswith("r"):
            return _title_case(cleaned)
        if cleaned.endswith(("a", "i", "u", "y")):
            return _title_case(cleaned[:-1])
        return _title_case(cleaned)


class NameEvolution:
    SOUND_SHIFTS = {
        "th": ["d", "t", "f"],
        "ae": ["e", "a", "ai"],
        "ei": ["i", "e", "ey"],
        "kh": ["k", "h", "q"],
        "v": ["b", "w", "f"],
        "tt": ["t", "th"],
        "ck": ["k", "g"],
    }

    def drift(self, culture: CultureNameSystem, years: int, rng: SeededRNG, *, culture_id: str | None = None) -> CultureNameSystem:
        intensity = min(1.0, years / 500.0)
        drifted = deepcopy(culture.seed_data)
        for key in ("male", "female", "family", "clans"):
            if key in drifted:
                drifted[key] = [self._mutate_name(value, intensity, rng) for value in drifted[key]]
        new_culture_id = culture_id or f"{culture.culture_id}_drifted_{years}"
        return CultureNameSystem(new_culture_id, drifted, order=culture.order)

    def _mutate_name(self, name: str, intensity: float, rng: SeededRNG) -> str:
        mutated = name.lower()
        for source, variants in self.SOUND_SHIFTS.items():
            if source in mutated and rng.random() < intensity:
                mutated = mutated.replace(source, rng.choice(variants), 1)
        return _title_case(mutated)


class NameRegistry:
    def __init__(self, seed_data: dict[str, Any], order: int = 3) -> None:
        cultures = seed_data.get("cultures", seed_data)
        self.default_culture = seed_data.get("default_culture") or next(iter(cultures))
        self.cultures = {
            culture_id: CultureNameSystem(culture_id, culture_data, order=order)
            for culture_id, culture_data in cultures.items()
        }
        self._used_full_names: dict[str, set[str]] = defaultdict(set)

    @classmethod
    def from_json(cls, file_path: str | Path, *, order: int = 3) -> "NameRegistry":
        with Path(file_path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(data, order=order)

    def generate(
        self,
        culture_id: str,
        rng: SeededRNG,
        *,
        gender: str | None = None,
        role: str = "Commoner",
        parent_given_name: str | None = None,
        lineage_name: str | None = None,
        ensure_unique: bool = True,
    ) -> GeneratedName:
        culture = self.cultures.get(culture_id) or self.cultures[self.default_culture]
        chosen_gender = gender or ("male" if rng.random() < 0.5 else "female")
        used_names = self._used_full_names[culture.culture_id] if ensure_unique else set()

        for _ in range(40):
            candidate = culture.generate_person_name(
                rng,
                gender=chosen_gender,
                role=role,
                parent_given_name=parent_given_name,
                lineage_name=lineage_name,
                blocked=used_names,
            )
            resolved_lineage = candidate.lineage_name or lineage_name or culture.generate_dynasty_name(rng)
            if candidate.lineage_name != resolved_lineage:
                candidate = GeneratedName(
                    full_name=candidate.full_name,
                    given_name=candidate.given_name,
                    byname=candidate.byname,
                    lineage_name=resolved_lineage,
                    gender=candidate.gender,
                    culture_id=candidate.culture_id,
                )
            if candidate.full_name.lower() not in used_names:
                used_names.add(candidate.full_name.lower())
                return candidate

        candidate = culture.generate_person_name(
            rng,
            gender=chosen_gender,
            role=role,
            parent_given_name=parent_given_name,
            lineage_name=lineage_name,
        )
        resolved_lineage = candidate.lineage_name or lineage_name or culture.generate_dynasty_name(rng)
        if candidate.lineage_name != resolved_lineage:
            candidate = GeneratedName(
                full_name=candidate.full_name,
                given_name=candidate.given_name,
                byname=candidate.byname,
                lineage_name=resolved_lineage,
                gender=candidate.gender,
                culture_id=candidate.culture_id,
            )
        used_names.add(candidate.full_name.lower())
        return candidate

    def drift_culture(self, base_culture_id: str, new_culture_id: str, years: int, rng: SeededRNG) -> CultureNameSystem:
        base_culture = self.cultures.get(base_culture_id) or self.cultures[self.default_culture]
        drifted = NameEvolution().drift(base_culture, years, rng, culture_id=new_culture_id)
        self.cultures[new_culture_id] = drifted
        return drifted


_DEFAULT_REGISTRY: NameRegistry | None = None


def get_default_name_registry() -> NameRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        data_path = Path(__file__).resolve().parents[1] / "data" / "names.json"
        _DEFAULT_REGISTRY = NameRegistry.from_json(data_path)
    return _DEFAULT_REGISTRY
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Sequence, TypeVar

ChoiceT = TypeVar("ChoiceT")


@dataclass(slots=True)
class SeededRNG:
    seed: int
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def randint(self, start: int, stop: int) -> int:
        return self._random.randint(start, stop)

    def uniform(self, start: float, stop: float) -> float:
        return self._random.uniform(start, stop)

    def random(self) -> float:
        return self._random.random()

    def choice(self, values: Sequence[ChoiceT]) -> ChoiceT:
        return self._random.choice(list(values))

    def shuffle(self, values: list[ChoiceT]) -> None:
        self._random.shuffle(values)
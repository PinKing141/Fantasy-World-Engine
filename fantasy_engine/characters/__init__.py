"""Character-level simulation primitives."""

from .names import GeneratedName, NameEvolution, NameRegistry, get_default_name_registry
from .person import Agent

__all__ = ["Agent", "GeneratedName", "NameEvolution", "NameRegistry", "get_default_name_registry"]
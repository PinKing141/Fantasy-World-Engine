# Legacy Archive

This folder contains older Fantasy Engine snapshots and prototypes that are not part of the current runtime path.

The active engine lives in `main.py` and the `fantasy_engine/` package at the workspace root.

## Layout

- `releases/`: numbered pre-alpha milestones in rough evolution order.
- `prototypes/`: side branches, experiments, and variant exports that informed later releases.

## Release Path

- `releases/pa01_foundation.txt` `[PA01 | foundation]`: earliest core prototype with world map, climate, civilization growth, and save/load basics.
- `releases/pa02_diplomacy.txt` `[PA02 | diplomacy]`: adds relationship tracking and a first diplomacy interaction system.
- `releases/pa03_economy.txt` `[PA03 | economy]`: introduces resource production, consumption, storage, and economy-aware diplomacy.
- `releases/pa04_societal_integration.txt` `[PA04 | society]`: expands the simulation with social classes, happiness, and stability.
- `releases/pa07_leader_system.py` `[PA07 | rulers]`: adds ruler personalities, succession, and leader-driven diplomacy and crisis handling.
- `releases/pa08_deep_history_legends.txt` `[PA08 | history]`: integrates deep history, cause-effect event tracking, and legends-style narrative views.
- `releases/pa10_culture_religion.py` `[PA10 | culture-religion]`: merges culture and religion systems on top of the history scaffold.
- `releases/pa11_individuals_heroes.py` `[PA11 | individuals]`: introduces individuals, dynasties, professions, and heroes.
- `releases/pa11_4_final_interactive.txt` `[PA11.4 | interactive-final]`: final interactive Pre-Alpha 11.4 snapshot with factions, regency, holy wars, and menus.

## Prototype Branches

- `prototypes/proto_legends_and_lore.py` `[prototype | legends]`: standalone legends/history prototype that appears to be a precursor to later merged history systems.
- `prototypes/pa11_deepseek_deterministic_variant.py` `[variant | deterministic-pa11]`: separate PA11-era export with deterministic RNG cleanup; not an exact duplicate of `releases/pa11_individuals_heroes.py`.

## Duplicate Cleanup

- The exact duplicate `pa11_4_final_interactive_duplicate.txt` was removed after hash verification against `releases/pa11_4_final_interactive.txt`.
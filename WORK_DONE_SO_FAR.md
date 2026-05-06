# Work Done So Far

This file summarizes the major work completed so far on the current modular Fantasy Engine prototype.

## Active Runtime Surface

- Active entry point: `main.py`
- Active package root: `fantasy_engine/`
- Verified runtime command: `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe main.py`
- Verified batch launcher: `run_fantasy_engine.bat`
- Current simulation phases: `climate -> economy -> trade -> society -> characters -> factions -> diplomacy -> military`
- Current live runtime stack: `World -> SeasonStepResult -> SimulationController -> Rich runner -> Rich renderer`
- Watch mode can now run open-ended when `--years` is omitted and stop only when the user quits.

## Core Engine And World Scaffold

- Built a modular package under `fantasy_engine/` separate from the older monolithic pre-alpha files.
- Added a deterministic phase-based engine in `fantasy_engine/core/engine.py`.
- Added slim runtime DTOs in `fantasy_engine/core/engine.py`, including `SeasonStepResult` and snapshot dataclasses for civilizations, routes, factions, and court state.
- Added a seeded RNG wrapper in `fantasy_engine/core/rng.py` and kept simulation decisions on seeded randomness.
- Added structured world history and event recording in `fantasy_engine/core/events.py`.
- Added event labels in `fantasy_engine/data/event_types.json`.
- Built the active world orchestrator in `fantasy_engine/world/world.py`.
- Updated the world orchestrator so seasonal advancement returns structured step results instead of only mutating state invisibly.
- Added region generation and explicit route topology in `fantasy_engine/world/map.py`.
- Added explicit trade route and shipment data models in `fantasy_engine/world/routes.py`.
- Added climate updates in `fantasy_engine/world/climate.py`.

## Live Runtime, Controller, And Rich Watch Mode

- Added `fantasy_engine/runner/controller.py` with a `SimulationController` layer above the deterministic core.
- Added curated autopause logic so major events pause the watch runner without contaminating engine code.
- Added `fantasy_engine/runner/rich_runner.py` for paced live watching on top of the controller API.
- Added manual Rich controls for pause/resume, slower, faster, single-step, skip-to-next-major-event, and quit.
- Made watch mode open-ended by default when `--years` is omitted.
- Added a root-level batch launcher `run_fantasy_engine.bat` that runs `main.py` through the workspace virtual environment.

## Civilization, Court, Factions, And Military

- Built the modular civilization model in `fantasy_engine/systems/civilization.py`.
- Added a `CourtRoster` with ruler, heir, general, diplomat, and steward.
- Added faction modeling for commoners, nobility, and military.
- Added military stockpile state with standing forces, levy pool, weapons, and supplies.
- Replaced generic force projection with supply-, arms-, and command-based military power.
- Added succession support through heir promotion.
- Added court replacement rules for dead or replaced office holders.
- Added coup handling and faction pressure in `fantasy_engine/systems/factions.py`.
- Fixed coup behavior so promoted faction leaders are replaced rather than causing self-coup loops.

## Economy, Society, Diplomacy, Trade, And War

- Added harvest, milling, spoilage, court provisioning, and military provisioning in `fantasy_engine/systems/economy.py`.
- Added shortage, famine, recovery, relief spending, unrest, and population change in `fantasy_engine/systems/society.py`.
- Added diplomacy and crisis externalization in `fantasy_engine/systems/diplomacy.py`.
- Added explicit route-based shipment delivery in `fantasy_engine/systems/trade.py`.
- Added campaign and logistics-driven warfare in `fantasy_engine/systems/military.py`.
- Tuned long-crisis recovery so collapse is not purely one-way.
- Added diplomatic aid as explicit shipments over routes instead of abstract transfer.

## Route Model Fixes

- Identified and fixed the root cause preventing route traffic: route endpoints were keyed by region names while systems were asking for endpoints by civilization names.
- Added world-level route partner resolution in `fantasy_engine/world/world.py`.
- Updated route consumers in economy, diplomacy, and characters to resolve route partners through the world layer.
- Fixed a runtime import issue in `fantasy_engine/systems/trade.py` so shipment objects are available during the trade phase.
- Validated that trade shipments and diplomatic aid now appear in simulation history.
- Added explicit route disruption and reopening history events so contested, severed, and reopened links are legible in both history and the live dashboard.

## Characters, Names, Lineage, And Cultural Drift

- Added the agent model in `fantasy_engine/characters/person.py`.
- Expanded agents with identity and simulation fields including `agent_id`, `gender`, `culture_id`, `role`, `grudges`, and lifecycle data.
- Added lineage metadata to agents: `given_name`, `byname`, `dynasty_name`, and `parent_ids`.
- Built procedural naming in `fantasy_engine/characters/names.py`.
- Added `MarkovNameGenerator`, `CultureNameSystem`, `NameEvolution`, and `NameRegistry`.
- Replaced hardcoded name pools with culture-aware name generation.
- Expanded `fantasy_engine/data/names.json` from starter seed sets to much larger historical seed corpora for each culture.
- Increased the Markov order to keep generated names closer to the expanded historical seed sets.
- Threaded real parent and dynasty data through agent creation instead of only passing fallback parent strings.
- Updated court succession and replacement paths so lineage continuity uses actual simulation ancestry.
- Added one-time descendant culture drift through `migration` and `culture_split` events in `fantasy_engine/systems/society.py`.
- Added world-level drifted culture creation through `World.drift_culture_for()`.
- Ensured drifted naming systems are registered in the active name registry.
- Prevented runaway repeated culture drift by limiting each civilization to a single descendant shift.

## Defection And Court Continuity Rules

- Added court death and defection handling in `fantasy_engine/systems/characters.py`.
- Made defecting court members keep dynasty lineage but adopt the destination civilization's culture.
- Re-anchored origin replacements after defection to the origin ruler's dynasty and parentage.
- Preserved the existing heir branch across defections.
- Added a follow-up continuity rule so later replacements on the origin court branch remain tied to the origin ruling dynasty.

## Demo Output Improvements

- Updated `main.py` from a simple yearly printout into a more readable dashboard-style demo.
- Replaced the earlier yearly-only printout path with a Rich live dashboard driven by structured snapshots instead of direct world reads.
- Added route, status, court, faction, event, and controls panels to the live dashboard.
- Added row markers for court and faction panels so actual turnovers are visible without flagging routine numeric drift.
- Added culture drift lines to highlight descendant culture IDs when `migration` or `culture_split` occurs.
- Fixed the controls footer so literal square-bracket key labels render safely in Rich.
- Removed per-frame console clearing and redundant paused-frame redraws to reduce visible CMD flicker.
- Added width-aware compact table rendering so narrow terminals drop nonessential columns.
- Added height-aware summary rendering so short terminals keep controls visible instead of clipping the bottom of the frame.
- Updated the court `Parent` display to show readable parent names instead of internal agent IDs.

## Regression Tests

- Added `tests/test_lineage_and_culture.py` using `unittest`.
- Added `tests/test_step_result_and_controller.py` for the live runtime, controller, renderer, and watch controls.
- Current regression coverage includes:
  - ruler succession preserves dynasty continuity and heir parent linkage
  - migration creates exactly one drifted descendant culture and registers it
  - culture split updates the court to the new descendant culture
  - defector keeps dynasty while the origin replacement reanchors to the origin ruler branch
  - follow-up post-defection court replacement remains on the origin ruling dynasty branch
  - seasonal stepping returns snapshot-rich `SeasonStepResult` objects
  - controller autopause tagging and major-event skipping
  - Rich manual controls for step, skip, and speed changes
  - literal control-hint rendering in the footer
  - compact and short-terminal layout behavior
  - readable parent-name rendering in the court panel

## Legacy Archive Cleanup

- Moved legacy monolith and pre-alpha files out of the workspace root into `legacy/`.
- Renamed legacy files into a more consistent lower_snake_case scheme.
- Split the legacy archive into:
  - `legacy/releases/`
  - `legacy/prototypes/`
- Added archive documentation in `legacy/README.md`.
- Identified and removed the exact duplicate `pa11_4_final_interactive_duplicate.txt`.

## Validation Performed So Far

- Repeated direct simulation probes using the workspace venv Python.
- Confirmed trade shipments and diplomatic aid now occur in the simulation.
- Confirmed court deaths, defections, and longer-horizon succession behavior are reachable.
- Confirmed names load and generate from the expanded historical corpora.
- Confirmed descendant culture drift events can be created and are bounded.
- Confirmed the Rich dashboard demo output runs successfully in watch mode and non-watch mode.
- Confirmed the open-ended watch path runs until quit when no year limit is supplied.
- Confirmed the batch launcher runs the project through the workspace virtual environment.
- Confirmed focused live-runner and controller regressions pass.
- Confirmed the broader regression suite passes.

## Useful Commands Used For Validation

- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe main.py`
- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe -m unittest tests.test_lineage_and_culture`
- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe -m unittest tests.test_step_result_and_controller`
- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe -c "import main; main.run_demo(years=2)"`
- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe -c "import main; main.run_demo(years=2, watch=False)"`
- `c:/Users/Favour/Documents/Fantasy Engine/.venv/Scripts/python.exe -c "from collections import Counter; from fantasy_engine.world.world import World; world = World(seed=4242, num_civilizations=4); world.simulate(12); counts = Counter(event.event_type for event in world.history.events); print(counts)"`
- `run_fantasy_engine.bat`
- `run_fantasy_engine.bat --years 1 --no-watch`

## Current Key Files

- `main.py`
- `run_fantasy_engine.bat`
- `fantasy_engine/core/engine.py`
- `fantasy_engine/core/events.py`
- `fantasy_engine/core/rng.py`
- `fantasy_engine/runner/controller.py`
- `fantasy_engine/runner/rich_runner.py`
- `fantasy_engine/world/world.py`
- `fantasy_engine/world/map.py`
- `fantasy_engine/world/routes.py`
- `fantasy_engine/world/climate.py`
- `fantasy_engine/systems/civilization.py`
- `fantasy_engine/systems/economy.py`
- `fantasy_engine/systems/society.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/systems/factions.py`
- `fantasy_engine/systems/diplomacy.py`
- `fantasy_engine/systems/trade.py`
- `fantasy_engine/systems/military.py`
- `fantasy_engine/characters/person.py`
- `fantasy_engine/characters/names.py`
- `fantasy_engine/data/names.json`
- `fantasy_engine/data/event_types.json`
- `tests/test_lineage_and_culture.py`
- `tests/test_step_result_and_controller.py`
- `legacy/README.md`

## Notes

- The active engine no longer depends on the old monolithic pre-alpha files in `legacy/`.
- The active watch mode is intentionally layered above the deterministic simulation core rather than embedding wall-clock behavior into the engine.
- The Rich dashboard is intended for terminal observation, not archival reporting.
- The tests now cover lineage/culture behavior plus the live runner and controller surface, but broader economic or military regression coverage is still limited.
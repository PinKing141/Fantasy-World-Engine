# Fantasy Engine

Fantasy Engine is a modular history-simulation prototype focused on generating readable, causally legible fantasy histories.

The active engine is built under `fantasy_engine/` and centers on a deterministic seasonal simulation, a controller layer, and a Rich-based terminal watch mode for observing court, faction, route, and event dynamics in real time.

## Current Focus

The current roadmap is tracked in `ROADMAP_NEXT.md`.

The active development direction is to make the simulation's personal and political consequences more legible without breaking the deterministic core or widening scope beyond the current roadmap phase.

## Project Layout

- `fantasy_engine/` - active modular engine code
- `tests/` - focused regression coverage
- `legacy/` - archived pre-modular prototypes and releases
- `main.py` - terminal entrypoint
- `run_fantasy_engine.bat` - convenience launcher for the workspace venv
- `ROADMAP_NEXT.md` - active roadmap and phase boundaries
- `WORK_DONE_SO_FAR.md` - current implementation status summary

## Run The Demo

From the workspace root:

```powershell
& ".\.venv\Scripts\python.exe" .\main.py
```

Open-ended Rich watch mode is the default. You can also run a bounded simulation:

```powershell
& ".\.venv\Scripts\python.exe" .\main.py --years 2
```

Run without watch mode:

```powershell
& ".\.venv\Scripts\python.exe" .\main.py --years 2 --no-watch
```

Use the batch launcher if you want a simpler entrypoint:

```powershell
.\run_fantasy_engine.bat --years 1 --no-watch
```

## Watch Controls

- `Space` pause or resume
- `Left` slower
- `Right` faster
- `S` single-step
- `E` skip to next major event
- `Up` and `Down` select actor
- `[` and `]` select event
- `B` toggle biography panel
- `Q` quit

## Tests

Run the focused regression suites from the workspace root:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_lineage_and_culture
& ".\.venv\Scripts\python.exe" -m unittest tests.test_step_result_and_controller
```

## Design Notes

- The deterministic simulation core stays separate from wall-clock runtime behavior.
- The Rich dashboard is for live observation, not archival output.
- Active work is meant to follow the roadmap phase order rather than broad speculative feature growth.

## Status

This repository contains the active modular engine plus a `legacy/` archive of earlier prototype files.

---
description: "Use when working in Fantasy Engine source files with roadmap-first execution, architecture-aware changes, narrow validation, simulation systems, runtime UI, or test-backed implementation."
name: "Roadmap-First Fantasy Engine"
applyTo: "fantasy_engine/**"
---
# Roadmap-First Rules

- Read `ROADMAP_NEXT.md` before planning, editing, or proposing implementation inside `fantasy_engine/**`.
- Read `WORK_DONE_SO_FAR.md` when current implementation status or existing runtime architecture affects the task.
- Derive the active phase, non-goals, scope boundaries, and validation shape before making changes.
- If the requested work conflicts with the active roadmap phase, say so clearly before proceeding.

# Architecture Rules

- Preserve the layered runtime shape: deterministic world and engine logic first, controller/runtime/watch behavior above it, renderer and dashboard concerns at the edge.
- Prefer changes at the controlling code path instead of patching symptoms at wiring layers.
- Keep features legible in the live runtime when they affect narrative clarity, observability, or interaction.
- Avoid broad refactors unless they unblock the active roadmap slice or fix a concrete bug.

# Execution Rules

- Implement the smallest complete roadmap-consistent slice.
- Add or update only focused regressions for the touched behavior.
- Run the narrowest validation that can falsify the change.
- Stop after the validated slice instead of opportunistically expanding scope.

# Non-Goals

- Do not add speculative systems outside the active phase.
- Do not do documentation churn unrelated to the current slice.
- Do not weaken existing architectural boundaries for convenience.
- Do not jump to broad cleanup just because a local change touches older code.

# Response Shape

- State the roadmap or architecture constraint that governed the work.
- State the narrow slice being changed.
- State the focused validation run for that slice.
- State any remaining risk, ambiguity, or approval-needed roadmap conflict.
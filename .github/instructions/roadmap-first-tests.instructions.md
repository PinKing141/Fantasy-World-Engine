---
description: "Use when editing Fantasy Engine tests with roadmap-first validation, focused regressions, phase-aware scope control, and architecture-aware test coverage."
name: "Roadmap-First Tests"
applyTo: "tests/**"
---
# Test-Side Roadmap Rules

- Read `ROADMAP_NEXT.md` before adding, expanding, or reshaping tests under `tests/**`.
- Read `WORK_DONE_SO_FAR.md` when existing runtime surfaces, controller behavior, or prior coverage matter.
- Align test work to the active roadmap phase and current slice instead of broad speculative coverage.
- If a requested test suite expands beyond the active phase, call that out before editing.

# Validation Rules

- Prefer focused regressions that prove the exact active slice.
- Test the smallest causal chain that can falsify the intended behavior.
- Avoid broad integration growth unless the roadmap slice explicitly requires it.
- Keep fixtures narrow and local to the behavior being validated.

# Architecture Rules

- Match the layered runtime shape of the engine rather than collapsing unrelated systems into one oversized test.
- Validate the controlling behavior at the correct layer: world, controller, runner, renderer, or system.
- Prefer tests that preserve deterministic simulation assumptions and stable causal expectations.

# Non-Goals

- Do not add coverage for deferred roadmap phases unless the active slice directly depends on it.
- Do not convert focused tests into general regression sweeps without a concrete reason.
- Do not use tests as a back door for roadmap drift or architecture churn.

# Response Shape

- State which roadmap phase or constraint the test work supports.
- State the exact behavior or causal chain the test proves.
- State the narrow validation command or suite used.
- State any remaining coverage gap that is intentionally deferred.
---
description: "Review a Fantasy Engine feature idea against the active roadmap phase and return active now, later, or reject."
name: "Feature Fit Review"
argument-hint: "Feature idea, proposed system change, or design direction to evaluate"
agent: "Roadmap Design Reviewer"
tools: [read, search]
---
Read `ROADMAP_NEXT.md` first, then evaluate the proposed feature idea against the active roadmap phase, explicit non-goals, and current architecture.

Use `WORK_DONE_SO_FAR.md` when implementation status matters.

Return exactly these sections:

## Verdict

Return exactly one of:
- active now
- later
- reject

## Why

Explain which roadmap constraints, active-phase boundaries, or architecture facts drove the verdict.

## Smallest Approved Slice

If the verdict is `active now`, name the smallest acceptable slice.

If the verdict is `later` or `reject`, either name a narrower active-phase-compatible reformulation or say `None in current phase`.

## Validation Shape

List the narrowest tests or checks that would prove the approved slice, or explain what validation should wait for a later phase.

## Risks Or Open Questions

Call out the main dependency, ambiguity, or sequencing risk.

Bias toward rejection when the idea does not clearly fit the active phase.
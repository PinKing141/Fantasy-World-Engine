---
description: "Turn a Fantasy Engine roadmap phase or sub-phase into a minimal implementation and test checklist with clear scope boundaries and validation." 
name: "Phase Slice Planning"
argument-hint: "Roadmap phase, sub-phase, or feature slice to plan"
agent: "Roadmap Design Reviewer"
tools: [read, search]
---
Read `ROADMAP_NEXT.md` first, then turn the requested roadmap phase, sub-phase, or feature slice into a minimal implementation checklist.

Use `WORK_DONE_SO_FAR.md` when current implementation status matters.

Output exactly these sections:

## Goal

State the phase objective in one short paragraph.

## In Scope

List only the smallest implementation items needed for the next shippable slice.

## Do Not Touch

List explicit non-goals and nearby temptations that should be deferred.

## Likely Files

List the most probable files or subsystems to inspect first.

## Implementation Checklist

Produce a short, ordered checklist of concrete coding steps.

## Test Checklist

Produce a short, ordered checklist of focused regressions or validations.

## Stop Condition

State what must be true before expanding scope.

Keep the output narrow, phase-aligned, and biased toward the smallest complete validated slice.
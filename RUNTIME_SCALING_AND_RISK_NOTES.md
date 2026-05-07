# Runtime Scaling And Risk Notes

This file records the concrete future-failure risks in the current observer stack and in the new FMG transition direction.

The point is not to predict every problem.

The point is to identify where the system is structurally fragile so the next slices can harden the right seams before scale turns a local annoyance into a rewrite.

## 1. Hidden Or Off-Screen Panels Can Masquerade As Dead Clicks

Current risk:

- The runtime lets users minimize and drag panels.
- Panel positions are persisted in `localStorage`.
- Before the current fix, selecting a province only updated the ruler data model. It did not guarantee the ruler panel was visible.
- That meant a valid province click could succeed internally while producing no visible result for the user.
- The same class of issue can recur whenever a new floating panel is added without a reveal-and-clamp path.

Why it gets worse later:

- Larger UI surface area means more floating panels, more persisted positions, and more chances for a viewport change to strand a panel off-screen.
- Once the runtime gets denser, users will not reliably notice a minimized dock tab as the explanation for "nothing happened."

What to watch:

- any action that updates hidden UI without also surfacing it
- any new panel that stores absolute position but is not clamped on resize
- any restore path that trusts stale viewport-relative coordinates from a previous resolution

Recommended direction:

- keep one shared reveal-and-clamp helper for all floating panels
- treat viewport resize as a layout-correction event, not only a canvas-resize event
- if more panels become actionable, add an explicit focus or pulse state when a hidden panel is restored

## 2. Delegated DOM Clicks Are Fragile If They Assume Element Targets

Current risk:

- The ruler tabs render with `innerHTML`, so delegation is the right approach.
- Delegation becomes brittle when the handler assumes `event.target` always supports `closest(...)`.
- In practice, browser event targets can be text nodes or other non-Element nodes depending on click location and browser behavior.

Why it gets worse later:

- The more inline typography, nested spans, icons, and badges the UI gets, the more likely clicks land on nested or non-Element nodes.
- Richer markup increases the odds of silent failures that look like dead UI.

What to watch:

- any delegated handler that calls DOM traversal methods directly on `event.target`
- any new click surface generated through `innerHTML` on a polling-driven container

Recommended direction:

- normalize event targets before DOM traversal
- prefer delegated handlers on stable parents for polling-driven content
- add browser-facing regression coverage once a JS test harness exists

## 3. The Legacy Province Picking Path Does Not Survive The FMG Roadmap Unchanged

Current risk:

- The procedural-world runtime uses a pixel-grid pickmap where each pixel maps directly to a province ID.
- That works because the current geography stack is raster-first.
- FMG saves are not raster-first. They are Voronoi-cell based.
- The FMG bridge note already calls this out: there is no direct replacement for `province_id_grid[y, x]`.

Why it gets worse later:

- If the codebase quietly keeps the current pickmap assumptions, province selection will become the next major integration break once FMG-backed observation starts.
- The failure mode will not be subtle. Either clicks will stop resolving, or the project will build an expensive compatibility shim too late.

What to watch:

- any roadmap work that treats the current procedural pickmap as reusable without a spatial index plan
- any UI feature request that assumes province identity is a trivial pixel lookup in the future architecture

Recommended direction:

- create a dedicated spatial query layer in the FMG path before building the FMG-backed runtime
- do not let observer code talk directly to raw FMG arrays once point queries are needed
- treat province picking as an architecture seam, not as a rendering detail

## 4. Polling-Driven Re-Renders Will Accumulate UI And Performance Debt

Current risk:

- The frontend polls every ~600 ms.
- Multiple panels rebuild with `innerHTML` on poll.
- Realm rows are rebound each render.
- Chronicle rendering currently redraws the whole visible feed when the tail changes.

Why it gets worse later:

- More civilizations, richer court rows, denser faction blocks, and larger chronicles mean more DOM churn per poll.
- DOM churn increases GC pressure and makes click timing bugs harder to reason about.
- Once the runtime adds more hover, tooltip, or expanded-inspector surfaces, repeated teardown and rebuild becomes a real responsiveness problem.

What to watch:

- repeated event listener attachment in render paths
- increasing polling payload size without corresponding UI diffing
- more image reloads or layout thrash on the same poll cadence

Recommended direction:

- keep delegation where rows are ephemeral
- move expensive panels toward keyed incremental updates when their complexity grows
- revisit polling cadence and payload shape before adding large narrative or relationship surfaces

## 5. Full Ownership Arrays And Full PNG Reloads Will Eventually Become A Throughput Problem

Current risk:

- The session currently sends a full `province_owners` array in initial and state payloads.
- Political ownership changes currently reload a full political overlay PNG.
- This is acceptable at the current scale.

Why it gets worse later:

- Higher province counts, more frequent ownership flips, or larger map sizes multiply both JSON and image transfer cost.
- Once observation becomes multi-user or remote rather than local-dev only, these full-snapshot updates get expensive fast.

What to watch:

- province count growth beyond the current procedural range
- frequent ownership changes during war or collapse
- plans to stream this runtime over slower networks

Recommended direction:

- keep the current simple full-snapshot model while counts remain modest
- introduce versioned deltas only when a measured bottleneck exists
- if FMG adoption raises province counts sharply, prioritize delta ownership updates before visual polish

## 6. SimulationSession Lock Scope Can Become A Contention Hotspot

Current risk:

- The web session uses a single re-entrant lock for tick advancement, payload reads, and image-version state.
- That keeps correctness simple today.

Why it gets worse later:

- Larger payload serialization, more frequent observer requests, or heavier image rebuilds all extend lock hold time.
- Once the lock window grows, UI polling can start fighting the tick thread.
- That produces apparent runtime lag that looks like rendering slowness even when the real bottleneck is session lock contention.

What to watch:

- image-generation work happening while holding the same lock used by state polling
- payloads that walk larger and larger slices of world state each poll
- plans for more than one active session per process

Recommended direction:

- keep derived observer caches small and explicit
- separate expensive derived-image work from the narrowest critical sections when profiling proves it necessary
- avoid widening `SimulationSession` into a catch-all mutable service

## 7. Browser-Side Regression Coverage Is Still The Biggest Reliability Gap

Current risk:

- There is backend coverage for province-owner coverage.
- There is no true browser automation proving province click selection, delegated person clicks, dock restoration, or panel visibility recovery.

Why it gets worse later:

- Observer bugs are disproportionately about interaction timing, layout, and browser behavior.
- Those are exactly the bugs static analysis and backend tests will miss.
- The more the project depends on a live observer for inspection, the more expensive manual-only validation becomes.

What to watch:

- repeated regressions in click behavior after seemingly unrelated UI edits
- fixes that only receive syntax checks or code audit rather than browser execution

Recommended direction:

- add a narrow browser integration harness once the observation surface stabilizes enough to justify it
- start with a tiny suite: province click selects realm, family-row click opens person card, hidden ruler panel is restored on selection
- do not wait for a full UI rewrite before introducing that coverage

## 8. Persisted Layout State Needs Versioning Or Reset Strategy

Current risk:

- Panel positions are stored without a schema version or viewport fingerprint.
- A stale saved layout can outlive a major CSS or panel-size change.

Why it gets worse later:

- As the observer evolves, panel geometry will change.
- Old saved coordinates will produce harder-to-diagnose layout bugs after updates.

What to watch:

- major CSS changes to panel size or anchor logic
- support requests that only reproduce on one machine or one browser profile

Recommended direction:

- add a layout version key when panel geometry changes materially
- clear or migrate persisted positions when the panel model changes

## 9. FMG Import Semantics Can Leak Into Core Simulation If The Adapter Boundary Slips

Current risk:

- FMG has sentinel indices, pack/grid splits, and save-format assumptions that are external to the simulation's own domain model.
- If those details leak into core systems directly, every later feature becomes harder to reason about and test.

Why it gets worse later:

- External format quirks become permanent engine quirks if they cross the adapter boundary too early.
- That raises long-term test cost and increases the odds of format-coupled bugs.

What to watch:

- core systems reading raw FMG arrays directly
- business logic branching on FMG sentinel conventions instead of adapter-level normalized concepts

Recommended direction:

- normalize imported data at the adapter seam
- keep raw FMG structures close to the ingestion layer unless a read-only tool explicitly needs them

## 10. The Legacy Procedural Runtime Is Now A Maintenance Surface, Not The Strategic Architecture

Current risk:

- The repo already has active FMG-ingestion work and a note explicitly marking the procedural map stack as obsolete for the chosen direction.
- If the team keeps expanding the legacy runtime because it is visible and convenient, the roadmap will drift in two directions at once.

Why it gets worse later:

- Every extra feature added to the legacy observer raises the migration cost to the FMG-backed path.
- The team ends up paying twice: once for the legacy surface, once again for the actual target architecture.

What to watch:

- requests that add large new observer features before the FMG bridge phases are complete
- fixes that quietly become feature work instead of keeping the legacy path merely usable

Recommended direction:

- keep legacy observer work limited to bug fixes and inspection-critical clarity
- put new architecture effort into the FMG ingestion, adapter, and spatial-query seams instead

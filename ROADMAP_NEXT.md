# Roadmap Next

This file defines the exact execution order for the active modular Fantasy Engine prototype.

The goal is to keep work narrow, testable, and sequential so new features are added only when the current slice is complete.

## North Star

The engine is not being built to produce procedural status updates.

It is being built to generate histories worth reading: lives worth mourning, dynasties worth tracing, and empires worth studying, without writing the stories by hand.

The target is a world that produces stories that feel discovered rather than authored. The simulation should create outcomes that were not predicted in advance, but that feel inevitable in hindsight because the causal chain is legible.

## End Goal In Practice

The final form of the project is a history engine where:

- the world keeps moving whether or not it is being watched
- individuals carry the weight of earlier events, not just current stats
- the most interesting stories are found by reading the archaeology of the simulation after the fact

Civilization-scale change matters, but only because it eventually lands on specific people. Famine, migration, trade rivalry, war, succession, schism, and cultural drift should all become personal somewhere in the chain.

## Three Layers To Build Toward

### 1. The World Is Alive Without Observation

Civilizations, dynasties, faiths, economies, and cultures should keep colliding even when no one is following a single actor closely.

### 2. Individuals Carry The Weight Of History

The past must become present pressure. Old wars, betrayals, famines, dynastic losses, and cultural trauma should shape current decisions rather than surviving only as log entries.

### 3. Stories Are Discovered, Not Designed

The long-term product is a simulation you can run for centuries and then read back through a Legends-style layer, following threads across people, houses, and civilizations until a meaningful story emerges.

## Feature Admission Rule

Every feature must justify itself against this question:

Does this make generated histories richer, more surprising, more legible, or more emotionally grounded?

If the answer is no, it does not belong on the active path.

## Current Strategic Gap

The architecture is already strong enough to support the goal.

The current weakness is experiential depth at the personal layer. The engine can already produce civilization-scale movement better than it can produce personal stories with weight. That is why needs, route disruption, memory as decision input, and later legends reading remain the critical path.

The next architecture hardening target is no longer dependency cleanup. That work is in a good enough place for the active path. The later tightening work is about reducing how much mutable shared state each system can touch directly.

## Working Rule

For each phase:

1. Implement the smallest complete slice.
2. Add focused regressions for only that slice.
3. Run narrow validation.
4. Stop and report before expanding scope.

## Global Non-Goals

Do not do these unless explicitly requested:

- broad refactors that do not unblock the active phase
- extra dashboard polish beyond what is needed to observe the phase
- archive cleanup or documentation churn unrelated to the active phase
- side systems that are interesting but outside the current phase
- Legends rebuild work before Phase 5
- terrain-depth work before Phase 6

## Deferred Hardening Track

This is not the active phase order.

Do not interrupt feature phases to do this unless a concrete bug, scaling pain, or testing blocker forces it.

When architecture tightening resumes, focus on these in order:

1. Replace broad direct world mutation with narrower write paths for each system.
2. Introduce system-specific state views so reads are explicit and easier to test.
3. Move high-risk writes behind small intent or service boundaries where invariants can be checked.
4. Reduce direct cross-system mutation of nested civilization, court, faction, and route state.
5. Add invariant checks around route state, succession state, active wars, and shipment lifecycle.

Success criteria for later hardening:

- a system can read only the slice of state it actually needs
- important mutations happen through a small number of explicit boundaries
- invalid state transitions are caught close to the write site
- focused tests can exercise system behavior without constructing the full world

Examples of the right kind of hardening later:

- a diplomacy-facing relation writer instead of open-ended mutation of war and relation fields
- a shipment gateway instead of many systems appending or mutating shipment state directly
- court or succession services that own promotion, replacement, and lineage invariants

Examples of the wrong kind of hardening later:

- broad rewrites with no immediate pressure from features or bugs
- abstract interfaces that do not reduce mutation risk or test cost
- architectural churn that delays memory, legends, or shortage cascade work

## Phase 2A: Stabilize Needs And Route Disruption

Status: Complete

Scope:

- `fantasy_engine/characters/needs.py`
- `fantasy_engine/characters/person.py`
- `fantasy_engine/world/routes.py`
- `fantasy_engine/world/world.py`
- `fantasy_engine/systems/economy.py`
- `fantasy_engine/systems/trade.py`
- `fantasy_engine/systems/military.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/systems/factions.py`
- `fantasy_engine/systems/diplomacy.py`
- `main.py`
- focused tests only

Success criteria:

- route disruption emits explicit history events
- severed and contested routes are covered by dedicated tests
- peace correctly reopens routes
- needs and route pressure are visible in the demo without extra clutter
- regressions pass

Do not touch:

- legends systems
- physical terrain expansion
- cross-civilization faction networks
- naming systems unless a bug blocks this phase

Deliverables:

- explicit route disruption event types
- route reopen behavior under peace
- focused route-state regressions
- stable dashboard visibility for needs and route stress

## Phase 2B: Shortage Cascade Into Politics

Status: Complete

Scope:

- `fantasy_engine/systems/society.py`
- `fantasy_engine/systems/economy.py`
- `fantasy_engine/systems/factions.py`
- `fantasy_engine/systems/characters.py`
- event types and focused tests

Success criteria:

- route-caused shortages visibly raise faction pressure
- import or relief failure feeds unrest and court stress in a traceable way
- at least 3 regressions prove a cascade such as:
  - route cut -> shortage -> faction pressure
  - route cut -> shortage -> defection pressure
  - route cut -> shortage -> war pressure

Do not touch:

- foreign faction diplomacy
- legends output
- map generation or terrain rules

Deliverables:

- stronger shortage propagation from route failure
- explicit political consequences from economic interruption
- focused cascade tests

## Phase 3: Memory As Decision Input

Status: Complete

Scope:

- `fantasy_engine/core/events.py`
- `fantasy_engine/systems/diplomacy.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/systems/civilization.py` if strictly needed
- focused tests

Success criteria:

- archive history changes diplomacy weights
- grudges and prior betrayals affect aid, alignment, and war choices
- dynasty continuity can carry some hostility or caution forward
- tests prove the same current-state civ can choose differently because of memory

Do not touch:

- legends prose rendering
- terrain work
- unrelated UI work

Deliverables:

- event-memory weighting rules
- dynasty-memory carryover where appropriate
- focused diplomacy and character regressions

## Phase 4: Cross-Civilization Faction Interaction

Status: Complete

Scope:

- `fantasy_engine/systems/factions.py`
- `fantasy_engine/systems/diplomacy.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/world/world.py` if needed
- focused tests

Success criteria:

- factions can seek foreign backing
- foreign powers can exploit domestic crises
- at least one regression proves internal crisis can become external war through faction channels

Do not touch:

- terrain systems
- legends rebuild, except for event wiring if absolutely necessary

Deliverables:

- faction-to-foreign contact path
- foreign exploitation of faction unrest
- focused cross-border political regressions

## Phase 5: Legends Rebuild

Status: Complete

Scope:

- new active legends module under `fantasy_engine/`
- `fantasy_engine/core/events.py`
- minimal output integration
- focused tests

Success criteria:

- active modular engine has a Legends reader
- it follows cause/effect links instead of filling templates
- legacy Legends code remains legacy only

Do not touch:

- terrain depth
- unrelated system tuning unless required by the reader

Deliverables:

- chain-reader based legends generation
- focused tests around causal narrative output

## Phase 6: Physical Terrain Properties

Status: Complete

Scope:

- `fantasy_engine/world/map.py`
- climate, economy, and military integration points
- focused tests

Success criteria:

- terrain affects movement, fertility, and campaign constraints beyond the current simple scalar model
- geography materially changes decisions rather than just decorating flavor text

Do not touch:

- unrelated character systems unless terrain constraints require direct integration

Deliverables:

- richer terrain property model
- integration with economy and war movement
- focused terrain regressions

## Phase 7: Faith Formation And Schism Pressure

Scope:

- `fantasy_engine/systems/civilization.py`
- `fantasy_engine/systems/society.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/world/world.py` if needed for initialization only
- event types and focused tests

Success criteria:

- civilizations hold an explicit active faith identity in the modular engine
- belief pressure can diverge from court and ruler legitimacy instead of remaining invisible flavor
- at least one regression proves a material crisis can push a civilization toward faith instability or schism pressure
- at least one regression proves the same present-day civilization can react differently because court or dynastic faith alignment differs

Do not touch:

- heroes or profession systems
- holy war expansion
- broad legends prose upgrades
- full culture-religion rewrite beyond the smallest active faith slice

Deliverables:

- explicit faith identity and alignment state
- legitimacy and social pressure hooks for belief instability
- focused schism-pressure regressions

## Current Immediate Task Order

Next approved phase: Phase 7 - Faith Formation And Schism Pressure

Follow these next, in order:

1. Add one focused regression proving a concrete pressure path can push an otherwise stable civilization into faith instability or schism pressure.
2. Add the smallest explicit faith state to the modular civilization layer without importing a full religion subsystem.
3. Connect that faith state to legitimacy, ruler or court alignment, and social pressure so belief fracture can become a visible causal factor.
4. Stop and report before widening into holy wars, hero units, or broad narrative rewrite.

These tasks matter because the roadmap already promises faith and schism as part of meaningful history. The next gap is making belief a live source of pressure instead of leaving dynasties and crises to operate without a religious layer.

## Stop Conditions

Stop after the current phase when:

- the listed success criteria are met
- focused regressions pass
- the compact demo still runs
- no new unrelated scope has been introduced

Do not automatically continue into the next phase without a fresh go-ahead.

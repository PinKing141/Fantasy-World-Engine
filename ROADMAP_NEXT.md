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

Status: Complete

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

## Phase 8: Court Bonds, Bereavement, And Personal Consequence

Status: Complete

Scope:

- `fantasy_engine/characters/person.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/core/events.py` if needed for relationship-linked event chaining
- `fantasy_engine/world/world.py` only if biography or snapshot visibility needs a minimal extension
- focused tests only

Success criteria:

- at least one explicit personal bond or kinship signal exists beyond raw dynasty label
- a court death or defection can create a traceable bereavement or loyalty shock in related agents
- at least one regression proves the same present-day court behaves differently because one branch experienced personal loss
- the resulting chain remains legible through existing event history and legends without a prose rewrite

Do not touch:

- hero units
- profession systems
- broad household or population-family simulation
- romance or marriage simulation
- holy war expansion
- broad legends rewrite
- broad diplomacy retuning unless a focused regression requires one narrow hook

Deliverables:

- minimal court-bond state
- bereavement or loyalty-shock consequences tied to court death or defection
- focused personal-consequence regressions

## Phase 9: Kin Fallout And Defection Consequence

Status: Complete

Scope:

- `fantasy_engine/characters/person.py`
- `fantasy_engine/systems/civilization.py` if needed for kinship refresh only
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/core/events.py` if needed for kinship-linked event chaining
- focused tests only

Success criteria:

- court members can recognize at least one broader kin signal beyond direct parent-child or explicit bond pairs
- a defection can create a traceable personal-loss or estrangement consequence in related court members
- at least one regression proves the same present-day court can react differently because kin fallout from defection is present
- the chain remains visible through the existing event history and legends stack without a broad narrative rewrite

Do not touch:

- marriage systems
- household simulation
- hero units
- profession systems
- holy war expansion
- broad UI work beyond minimal visibility required by the tests

Deliverables:

- minimal broader kin-network state or inference
- defection-linked estrangement or kin-loss consequences
- focused kin-fallout regressions

## Phase 10: Marriage And Household Formation

Status: Complete

Scope:

- `fantasy_engine/characters/person.py`
- `fantasy_engine/systems/civilization.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/world/world.py` if needed for minimal snapshot visibility
- focused tests only

Success criteria:

- the active engine can form explicit marriages or household ties in the ruling and court layer
- heirs and replacements can emerge from household context instead of only generic lineage fallback
- at least one regression proves household state can change succession or court continuity outcomes

Do not touch:

- hero units
- profession systems
- holy war expansion
- broad population-scale family simulation

Deliverables:

- minimal marriage or household state
- household-aware continuity rules
- focused household regressions

## Phase 11: Professions And Hero Emergence

Status: Complete

Scope:

- `fantasy_engine/characters/person.py`
- `fantasy_engine/systems/characters.py`
- `fantasy_engine/systems/civilization.py` if needed for appointment surfaces
- `fantasy_engine/world/world.py` if needed for minimal visibility
- focused tests only

Success criteria:

- notable agents can hold explicit professions or callings beyond court title alone
- at least one hero-like figure can emerge from pressure, achievement, or survival rather than being pre-scripted
- at least one regression proves professions or hero status change later decisions or remembered history

Do not touch:

- holy war expansion except for data plumbing required later
- broad combat rewrite
- broad UI overhaul

Deliverables:

- minimal profession state
- minimal hero-emergence path
- focused profession and hero regressions

## Phase 12: Holy War And Confessional Conflict

Status: Complete

Scope:

- `fantasy_engine/systems/diplomacy.py`
- `fantasy_engine/systems/military.py`
- `fantasy_engine/systems/characters.py` if needed for ruler or hero influence
- `fantasy_engine/core/events.py`
- event types and focused tests

Success criteria:

- faith conflict can explicitly contribute to war selection or escalation instead of remaining domestic-only pressure
- at least one regression proves faith-aligned or faith-opposed actors can choose differently because of confessional stakes
- holy war remains grounded in the existing deterministic diplomacy and war layers rather than becoming a separate ad hoc minigame

Do not touch:

- broad religion rewrite
- broad military overhaul beyond the smallest confessional-war slice
- unrelated household tuning

Deliverables:

- confessional war pressure hooks
- explicit faith-war event chain
- focused holy-war regressions

## Phase 13: Static World Map Visualization

Status: Complete

Scope:

- `fantasy_engine/world/world.py`
- `fantasy_engine/world/map.py` only if minor read helpers are needed
- a new visualization or export module under `fantasy_engine/`
- `main.py` only if minimal non-watch export wiring is needed
- focused tests only

Success criteria:

- the engine can render a deterministic static map image for a seeded world
- regions are shown in their current positions with distinct civilization ownership or labels
- routes are shown with visible route state differences such as open, contested, or severed
- the map remains an observer or export surface rather than replacing the current Rich runtime
- the output is useful for quickly understanding world geography and political state

Do not touch:

- procedural terrain generation
- polygon border math
- territorial Voronoi ownership systems
- pygame or a second interactive rendering runtime
- broad UI rewrites

Deliverables:

- `matplotlib` dependency
- one static map renderer or export path
- focused deterministic map-output regressions

## Phase 14: Procedural Geography Foundation

Status: Complete

Scope:

- `fantasy_engine/world/map.py`
- `fantasy_engine/world/world.py` only if world construction needs a narrow geometry handoff
- `fantasy_engine/visual/world_map.py` only if minimal preview support is needed for validation
- focused tests only

Success criteria:

- seeded world generation no longer depends only on shuffled fixed blueprints for region placement and terrain assignment
- `noise` drives at least one deterministic geography layer such as elevation, moisture, fertility bias, or regional clustering
- the same seed produces the same geography while different seeds can produce meaningfully different map layouts or terrain distributions
- generated geography still respects the engine's current need for legible routes, region ownership, and stable simulation startup

Do not touch:

- shapely border or polygon work
- territorial ownership geometry
- pygame or live interactive map controls
- broad climate or economy rewrites beyond what the geography generator strictly needs

Deliverables:

- `noise` dependency
- minimal procedural geography generator replacing the current fixed map shuffle at the approved seam
- focused deterministic geography regressions

## Phase 15: Territorial Borders And Geometry

Status: Complete

Scope:

- `fantasy_engine/world/` geometry helpers
- static map export layers that need border shapes
- focused tests only

Success criteria:

- civilizations can expose explicit border or territory geometry instead of only point-based region ownership
- `shapely` is used only where real geometry operations are required, such as clipping, merging, adjacency cleanup, or route intersection logic
- territory visualization remains compatible with the existing static export path before any interactive runtime is considered

Do not touch:

- pygame runtime work
- broad political simulation rewrites unrelated to geometry
- speculative province or settlement micro-systems

Deliverables:

- `shapely` dependency
- explicit territory or border geometry surface
- focused border-geometry regressions

## Phase 16: Static Terrain Surface And Cartography

Status: Approved

Scope:

- `fantasy_engine/world/map.py`
- `fantasy_engine/world/territories.py` only if terrain-to-territory alignment needs a narrow geometry hook
- `fantasy_engine/visual/world_map.py`
- focused tests only

Success criteria:

- the static export can render a deterministic terrain surface that reads more like real geography than abstract colored polygons alone
- the same seed produces the same terrain surface while different seeds can materially change coastlines, landmass shape, terrain bands, or water distribution
- the export clearly separates land, sea, and at least one higher-relief terrain class such as hills or mountains
- existing territory polygons, labels, and route overlays remain compatible with the new terrain surface instead of being replaced by it

Do not touch:

- interactive runtime work
- broad political simulation rewrites
- province or settlement micro-systems
- hydrology, weather, or erosion simulation beyond the smallest cartography-facing slice

Deliverables:

- deterministic land and water surface generation for the static exporter
- coastline and terrain-band rendering layered under existing political geometry
- focused terrain-surface regressions

## Phase 17: Interactive Map Runtime

Status: Deferred

Scope:

- a separate interactive map runtime layer
- controller integration only where needed to observe existing simulation state
- focused tests only

Success criteria:

- `pygame-ce` powers an interactive observation surface rather than replacing the deterministic simulation core
- the runtime can inspect geography, routes, and later territory state without breaking the existing Rich watcher or static export path
- input, camera, and rendering concerns stay outside the simulation core and snapshot construction layers

Do not touch:

- core simulation ownership rules beyond what the interactive observer needs to read
- broad UI duplication of every existing Rich panel
- speculative gameplay systems unrelated to observation

Deliverables:

- `pygame-ce` dependency
- separate interactive map observer runtime
- focused runtime interaction regressions

## Current Immediate Task Order

Phase 15 is complete.

Next approved phase: Phase 16 - Static Terrain Surface And Cartography

Follow these next, in order:

1. Add one focused regression proving the same seed yields the same terrain-surface signature while different seeds can materially change land, water, or relief layout.
2. Add the smallest static terrain layer under the current territory export: land and water mask first, then coastline and basic relief banding.
3. Keep current territory polygons, routes, and labels as overlay layers rather than rewriting the political map surface.
4. Stop and report before widening into interactive runtime work.

These tasks matter because the engine now has deterministic procedural geography and static political territories, but it still does not render a terrain surface that reads like real land and water. The next gap is cartographic terrain rendering, not interactive runtime work.

## Stop Conditions

Stop after the current phase when:

- the listed success criteria are met
- focused regressions pass
- the compact demo still runs
- no new unrelated scope has been introduced

Do not automatically continue into the next phase without a fresh go-ahead.

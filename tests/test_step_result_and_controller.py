from __future__ import annotations

import unittest
from unittest import mock

from fantasy_engine.core.engine import AgentBioSnapshot, CivilizationSnapshot, CourtSnapshot, EventSnapshot, FactionSnapshot, NeedsSnapshot, RouteSnapshot, SeasonStepResult
from fantasy_engine.core.events import HistoryEvent
from fantasy_engine.runner.controller import SimulationController
from fantasy_engine.runner.rich_runner import _compose_runtime_frame, _handle_control, run_with_rich
from rich.console import Console
from fantasy_engine.visual.dashboard import make_dashboard_snapshot
from fantasy_engine.visual.rich_renderer import RichDashboardRenderer
from fantasy_engine.world.world import World


class StepResultAndControllerTests(unittest.TestCase):
    def test_advance_season_returns_step_result_with_snapshots(self) -> None:
        world = World(seed=4242, num_civilizations=4)

        result = world.advance_season()

        self.assertIsInstance(result, SeasonStepResult)
        self.assertEqual(result.tick, 1)
        self.assertEqual(result.year, 1)
        self.assertEqual(result.season, "spring")
        self.assertTrue(result.civilization_snapshots)
        self.assertTrue(result.active_routes)
        self.assertIsInstance(result.civilization_snapshots[0], CivilizationSnapshot)
        self.assertIsInstance(result.active_routes[0], RouteSnapshot)

    def test_dashboard_uses_readable_court_parent_names(self) -> None:
        world = World(seed=4242, num_civilizations=4)

        snapshot = make_dashboard_snapshot(world.snapshot_current_state())

        self.assertTrue(snapshot.court_rows)
        for row in snapshot.court_rows:
            self.assertNotIn("_Ruler_", row.heir_parent_name)
            self.assertNotIn("_", row.heir_parent_name)

    def test_controller_marks_autopause_fields(self) -> None:
        world = _StaticStepWorld(
            SeasonStepResult(
                year=2,
                season="winter",
                tick=8,
                year_boundary=True,
                world_year=3,
                events=[
                    HistoryEvent(
                        year=2,
                        season="winter",
                        event_type="famine",
                        civilization="Sylgard",
                        details="Stores failed through the winter.",
                        severity="catastrophic",
                    )
                ],
                major_events=[],
                civilization_snapshots=[],
                active_wars=[],
                active_routes=[],
            )
        )
        controller = SimulationController(world)

        result = controller.step()

        self.assertTrue(result.should_pause)
        self.assertIn("Famine", result.pause_reason)

    def test_skip_to_next_major_event_returns_first_eligible_step(self) -> None:
        world = _SequenceWorld(
            [
                SeasonStepResult(
                    year=1,
                    season="spring",
                    tick=1,
                    year_boundary=False,
                    world_year=1,
                    events=[],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                ),
                SeasonStepResult(
                    year=1,
                    season="summer",
                    tick=2,
                    year_boundary=False,
                    world_year=1,
                    events=[
                        HistoryEvent(
                            year=1,
                            season="summer",
                            event_type="war_declaration",
                            civilization="Sylgard",
                            other_civilization="Quor-Thal",
                            details="A remembered rivalry broke into war.",
                            severity="major",
                        )
                    ],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                ),
            ]
        )
        controller = SimulationController(world)

        result = controller.skip_to_next_major_event()

        self.assertEqual(result.tick, 2)
        self.assertTrue(result.should_pause)

    def test_skip_to_next_major_event_honors_stop_year(self) -> None:
        world = _WorldWithYearBoundary(
            year=3,
            result=SeasonStepResult(
                year=3,
                season="spring",
                tick=9,
                year_boundary=False,
                world_year=3,
                events=[],
                major_events=[],
                civilization_snapshots=[],
                active_wars=[],
                active_routes=[],
            ),
        )
        controller = SimulationController(world)

        result = controller.skip_to_next_major_event(stop_year=3)

        self.assertEqual(result.tick, 9)

    def test_faster_and_slower_adjust_speed(self) -> None:
        world = _StaticStepWorld(
            SeasonStepResult(
                year=1,
                season="spring",
                tick=0,
                year_boundary=False,
                world_year=1,
                events=[],
                major_events=[],
                civilization_snapshots=[],
                active_wars=[],
                active_routes=[],
            )
        )
        controller = SimulationController(world, initial_speed=1.0)

        faster_speed = controller.faster()
        slower_speed = controller.slower()

        self.assertEqual(faster_speed, 2.0)
        self.assertEqual(slower_speed, 1.0)

    def test_rich_runner_step_control_steps_once_and_pauses(self) -> None:
        world = _SequenceWorld(
            [
                SeasonStepResult(
                    year=1,
                    season="spring",
                    tick=1,
                    year_boundary=False,
                    world_year=1,
                    events=[],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                )
            ]
        )
        controller = SimulationController(world)

        result, status, quit_requested = _handle_control("step", controller, target_year=3)

        self.assertFalse(quit_requested)
        self.assertEqual(status, "Stepped one season")
        self.assertTrue(controller.paused)
        self.assertIsNotNone(result)
        self.assertEqual(result.tick, 1)

    def test_rich_runner_skip_control_uses_bounded_major_skip(self) -> None:
        world = _SequenceWorld(
            [
                SeasonStepResult(
                    year=1,
                    season="spring",
                    tick=1,
                    year_boundary=False,
                    world_year=1,
                    events=[],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                ),
                SeasonStepResult(
                    year=1,
                    season="summer",
                    tick=2,
                    year_boundary=False,
                    world_year=1,
                    events=[
                        HistoryEvent(
                            year=1,
                            season="summer",
                            event_type="war_declaration",
                            civilization="Sylgard",
                            details="War broke out.",
                            severity="major",
                        )
                    ],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                ),
            ]
        )
        controller = SimulationController(world)

        result, status, quit_requested = _handle_control("skip_major", controller, target_year=3)

        self.assertFalse(quit_requested)
        self.assertEqual(status, "Skipped to next major event")
        self.assertIsNotNone(result)
        self.assertEqual(result.tick, 2)

    def test_rich_runner_speed_controls_adjust_controller_speed(self) -> None:
        world = _StaticStepWorld(
            SeasonStepResult(
                year=1,
                season="spring",
                tick=0,
                year_boundary=False,
                world_year=1,
                events=[],
                major_events=[],
                civilization_snapshots=[],
                active_wars=[],
                active_routes=[],
            )
        )
        controller = SimulationController(world, initial_speed=1.0)

        _, faster_status, _ = _handle_control("faster", controller, target_year=3)
        _, slower_status, _ = _handle_control("slower", controller, target_year=3)

        self.assertEqual(faster_status, "Speed set to 2x")
        self.assertEqual(slower_status, "Speed set to 1x")

    def test_runtime_frame_renders_literal_control_hints(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        controller = SimulationController(world)
        renderer = RichDashboardRenderer()

        frame = _compose_runtime_frame(
            renderer,
            title="render check",
            snapshot=make_dashboard_snapshot(controller.current_result()),
            paused=True,
            speed=1.0,
            status_message="Autopause: Famine · Sylgard",
        )

        with renderer.console.capture() as capture:
            renderer.console.print(frame)

        rendered = capture.get()
        self.assertIn("[space] pause/resume", rendered)
        self.assertIn("[<-] slower", rendered)
        self.assertIn("[->] faster", rendered)
        self.assertIn("[up]/[down] select actor", rendered)
        self.assertIn("select event", rendered)
        self.assertIn("[b] biography", rendered)

    def test_dashboard_visible_actors_include_heir_and_faction_leader(self) -> None:
        step_result = SeasonStepResult(
            year=2,
            season="summer",
            tick=6,
            year_boundary=False,
            world_year=2,
            events=[],
            major_events=[],
            civilization_snapshots=[
                CivilizationSnapshot(
                    name="Sylgard",
                    culture_id="desert",
                    population=15000,
                    grain_stores=0,
                    food_stores=0,
                    weapons_stockpile=40,
                    supply_stockpile=20,
                    stability=49.5,
                    legitimacy=38.0,
                    unrest=61.0,
                    at_war_with=(),
                    contested_routes=1,
                    severed_routes=0,
                    court=_mock_court_snapshot(),
                    factions=(_mock_faction_snapshot(),),
                )
            ],
            active_wars=[],
            active_routes=[],
        )

        snapshot = make_dashboard_snapshot(step_result)

        self.assertEqual(
            [actor.actor_name for actor in snapshot.visible_actors],
            ["Nadi ibn Malim", "Jabib ibn Nadi", "Faris ibn Nadi", "Samira bint Nadi", "Karid ibn Nadi"],
        )
        self.assertEqual(snapshot.visible_actors[1].relation_label, "heir")
        self.assertEqual(snapshot.visible_actors[2].relation_label, "general")
        self.assertEqual(snapshot.visible_actors[3].relation_label, "diplomat")
        self.assertEqual(snapshot.visible_actors[4].section, "faction")

    def test_dashboard_event_rows_include_actor_context(self) -> None:
        step_result = SeasonStepResult(
            year=3,
            season="spring",
            tick=9,
            year_boundary=False,
            world_year=3,
            events=[],
            major_events=[],
            civilization_snapshots=[],
            active_wars=[],
            active_routes=[],
            event_snapshots=(
                EventSnapshot(
                    event_type="faction_pressure",
                    label="Faction Pressure",
                    civilization="Sylgard",
                    details="Karid ibn Nadi rallied the commoners around food security.",
                    severity="major",
                    actor_name="Karid ibn Nadi",
                    actor_role="Commoner Tribune",
                    relation_to_ruler="child of ruler",
                    context_summary="Actor: Karid ibn Nadi · Commoner Tribune · child of ruler · Faction: Commoners · Pressure: 77.3",
                ),
            ),
        )

        snapshot = make_dashboard_snapshot(step_result)

        self.assertEqual(len(snapshot.key_events), 1)
        self.assertIn("Karid ibn Nadi", snapshot.key_events[0].summary)
        self.assertIn("Commoner Tribune", snapshot.key_events[0].context)
        self.assertIn("child of ruler", snapshot.key_events[0].context)

    def test_renderer_status_thresholds_return_expected_styles(self) -> None:
        renderer = RichDashboardRenderer()

        self.assertEqual(renderer._store_style(0), "bold red")
        self.assertEqual(renderer._store_style(10), "yellow")
        self.assertEqual(renderer._store_style(50), "green")
        self.assertEqual(renderer._high_good_style(25.0), "bold red")
        self.assertEqual(renderer._high_good_style(45.0), "yellow")
        self.assertEqual(renderer._high_good_style(70.0), "green")
        self.assertEqual(renderer._low_good_style(65.0), "bold red")
        self.assertEqual(renderer._low_good_style(40.0), "yellow")
        self.assertEqual(renderer._low_good_style(10.0), "green")

    def test_runtime_frame_can_render_biography_panel_for_selected_visible_actor(self) -> None:
        world = _StaticStepWorld(
            SeasonStepResult(
                year=2,
                season="summer",
                tick=6,
                year_boundary=False,
                world_year=2,
                events=[],
                major_events=[],
                civilization_snapshots=[
                    CivilizationSnapshot(
                        name="Sylgard",
                        culture_id="desert",
                        population=15000,
                        grain_stores=0,
                        food_stores=0,
                        weapons_stockpile=40,
                        supply_stockpile=20,
                        stability=49.5,
                        legitimacy=38.0,
                        unrest=61.0,
                        at_war_with=(),
                        contested_routes=1,
                        severed_routes=0,
                        court=_mock_court_snapshot(),
                        factions=(_mock_faction_snapshot(),),
                    )
                ],
                active_wars=[],
                active_routes=[],
            )
        )
        controller = SimulationController(world)
        renderer = RichDashboardRenderer()

        frame = _compose_runtime_frame(
            renderer,
            title="bio check",
            snapshot=make_dashboard_snapshot(controller.current_result()),
            paused=True,
            speed=1.0,
            status_message="Biography open",
            selected_actor_index=3,
            biography_visible=True,
        )

        with renderer.console.capture() as capture:
            renderer.console.print(frame)

        rendered = capture.get()
        self.assertIn("Biography", rendered)
        self.assertIn("Samira bint Nadi", rendered)
        self.assertIn("Born ~ Year", rendered)
        self.assertIn("Caused by:", rendered)
        self.assertIn("Led to:", rendered)

    def test_court_row_shows_explicit_selected_actor_label(self) -> None:
        renderer = RichDashboardRenderer(console=Console(record=True, width=140, height=80))
        frame = renderer.compose_frame(
            title="court label check",
            snapshot=make_dashboard_snapshot(
                SeasonStepResult(
                    year=2,
                    season="summer",
                    tick=6,
                    year_boundary=False,
                    world_year=2,
                    events=[],
                    major_events=[],
                    civilization_snapshots=[
                        CivilizationSnapshot(
                            name="Sylgard",
                            culture_id="desert",
                            population=15000,
                            grain_stores=0,
                            food_stores=0,
                            weapons_stockpile=40,
                            supply_stockpile=20,
                            stability=49.5,
                            legitimacy=38.0,
                            unrest=61.0,
                            at_war_with=(),
                            contested_routes=1,
                            severed_routes=0,
                            court=_mock_court_snapshot(),
                            factions=(_mock_faction_snapshot(),),
                        )
                    ],
                    active_wars=[],
                    active_routes=[],
                )
            ),
            selected_actor_index=2,
        )

        with renderer.console.capture() as capture:
            renderer.console.print(frame)

        rendered = capture.get()
        self.assertIn("General", rendered)

    def test_events_panel_expands_selected_event_chain(self) -> None:
        renderer = RichDashboardRenderer(console=Console(record=True, width=140, height=80))
        frame = renderer.compose_frame(
            title="event chain check",
            snapshot=make_dashboard_snapshot(
                SeasonStepResult(
                    year=3,
                    season="spring",
                    tick=9,
                    year_boundary=False,
                    world_year=3,
                    events=[],
                    major_events=[],
                    civilization_snapshots=[],
                    active_wars=[],
                    active_routes=[],
                    event_snapshots=(
                        EventSnapshot(
                            event_type="faction_pressure",
                            label="Faction Pressure",
                            civilization="Sylgard",
                            details="Karid ibn Nadi rallied the commoners around food security.",
                            severity="major",
                            actor_name="Karid ibn Nadi",
                            actor_role="Commoner Tribune",
                            relation_to_ruler="child of ruler",
                            context_summary="Actor: Karid ibn Nadi · Commoner Tribune · child of ruler",
                            caused_by_events=("Faction Pressure <- Famine (Sylgard)",),
                            led_to_events=("Faction Pressure -> Faction Coup (Sylgard)",),
                        ),
                    ),
                )
            ),
            selected_event_index=0,
        )

        with renderer.console.capture() as capture:
            renderer.console.print(frame)

        rendered = capture.get()
        self.assertIn("Caused by:", rendered)
        self.assertIn("Faction Pressure <- Famine", rendered)
        self.assertIn("Led to:", rendered)
        self.assertIn("Faction Pressure -> Faction Coup", rendered)

    def test_world_event_snapshot_enriches_war_context_with_named_people(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        attacker = world.civilizations[0]
        defender = world.civilizations[1]

        war_event = HistoryEvent(
            year=1,
            season="summer",
            event_type="war_declaration",
            civilization=attacker.name,
            other_civilization=defender.name,
            details=f"Facing domestic pressure, {attacker.ruler.name} turned outward and declared war on {defender.name}.",
            severity="major",
            data={
                "ruler": attacker.ruler.name,
                "ruler_id": attacker.ruler.agent_id,
                "general": attacker.court.general.name,
                "general_id": attacker.court.general.agent_id,
                "target": defender.name,
                "target_ruler": defender.ruler.name,
                "target_ruler_id": defender.ruler.agent_id,
                "target_general": defender.court.general.name,
                "target_general_id": defender.court.general.agent_id,
            },
        )

        snapshot = world._build_event_snapshot(war_event)

        self.assertEqual(snapshot.actor_name, attacker.ruler.name)
        self.assertIn(defender.ruler.name, snapshot.context_summary)
        self.assertIn(defender.court.general.name, snapshot.context_summary)

    def test_runtime_frame_uses_summary_layout_on_short_console(self) -> None:
        world = World(seed=4242, num_civilizations=4)
        controller = SimulationController(world)
        for _ in range(6):
            step = controller.step()

        renderer = RichDashboardRenderer(
            console=Console(record=True, width=100, force_terminal=False, color_system=None)
        )
        frame = _compose_runtime_frame(
            renderer,
            title="fit check",
            snapshot=make_dashboard_snapshot(step),
            paused=True,
            speed=1.0,
            status_message="Autopause: Famine · Sylgard",
        )

        with renderer.console.capture() as capture:
            renderer.console.print(frame)

        rendered_lines = capture.get().splitlines()
        self.assertTrue(rendered_lines)
        rendered = "\n".join(rendered_lines)
        self.assertIn("Status", rendered)
        self.assertIn("Pop", rendered)
        self.assertIn("Events", rendered)
        self.assertIn("[s] step  [e] skip major  [q] quit", rendered)
        self.assertNotIn("Court", rendered)
        self.assertNotIn("Factions", rendered)
        self.assertNotIn("Culture    ", rendered)
        self.assertNotIn("Dynasty    ", rendered)

    def test_run_with_rich_does_not_clear_console_each_frame(self) -> None:
        world = _LiveLoopWorld()
        controller = SimulationController(world)
        controller.paused = True
        renderer = RichDashboardRenderer(console=Console(record=True, width=120))
        renderer.console.clear = mock.Mock()

        with mock.patch(
            "fantasy_engine.runner.rich_runner._poll_control",
            side_effect=[None, "quit"],
        ):
            run_with_rich(
                controller,
                renderer,
                years=1,
                clear_between_frames=True,
            )

        renderer.console.clear.assert_not_called()


class _StaticStepWorld:
    def __init__(self, result: SeasonStepResult) -> None:
        self._result = result

    def snapshot_current_state(self) -> SeasonStepResult:
        return self._result

    def advance_season(self) -> SeasonStepResult:
        return self._result


class _SequenceWorld:
    def __init__(self, results: list[SeasonStepResult]) -> None:
        self._results = iter(results)

    def snapshot_current_state(self) -> SeasonStepResult:
        return SeasonStepResult(
            year=1,
            season="spring",
            tick=0,
            year_boundary=False,
            world_year=1,
            events=[],
            major_events=[],
            civilization_snapshots=[],
            active_wars=[],
            active_routes=[],
        )

    def advance_season(self) -> SeasonStepResult:
        return next(self._results)


class _WorldWithYearBoundary:
    def __init__(self, *, year: int, result: SeasonStepResult) -> None:
        self.year = year
        self._result = result

    def snapshot_current_state(self) -> SeasonStepResult:
        return self._result

    def advance_season(self) -> SeasonStepResult:
        raise AssertionError("advance_season should not be called when stop_year is already reached")


class _LiveLoopWorld:
    def __init__(self) -> None:
        self.seed = 4242
        self.year = 1
        self.history = _EmptyHistory()

    def snapshot_current_state(self) -> SeasonStepResult:
        return SeasonStepResult(
            year=1,
            season="spring",
            tick=0,
            year_boundary=False,
            world_year=1,
            events=[],
            major_events=[],
            civilization_snapshots=[],
            active_wars=[],
            active_routes=[],
        )

    def advance_season(self) -> SeasonStepResult:
        raise AssertionError("advance_season should not be called in this paused live-loop test")

    def recent_legend_summaries(self, limit: int = 3) -> list[str]:
        return []


class _EmptyHistory:
    def cause_effect_pairs(self) -> list[tuple[str, str]]:
        return []


def _mock_court_snapshot() -> CourtSnapshot:
    return CourtSnapshot(
        ruler_name="Nadi ibn Malim",
        ruler_dynasty="Malim",
        heir_name="Jabib ibn Nadi",
        heir_agent_id="Sylgard_Heir_Jabib_ibn_Nadi_5678",
        general_name="Faris ibn Nadi",
        general_agent_id="Sylgard_General_Faris_ibn_Nadi_2468",
        diplomat_name="Samira bint Nadi",
        diplomat_agent_id="Sylgard_Diplomat_Samira_bint_Nadi_1357",
        heir_parent_id="Sylgard_Ruler_Nadi_ibn_Malim_1234",
        heir_parent_name="Nadi ibn Malim",
        ruler_needs=NeedsSnapshot(food=43.0, safety=4.0, belonging=4.0, esteem=0.0),
        ruler_agent_id="Sylgard_Ruler_Nadi_ibn_Malim_1234",
        ruler_bio=AgentBioSnapshot(
            agent_id="Sylgard_Ruler_Nadi_ibn_Malim_1234",
            name="Nadi ibn Malim",
            role="Ruler",
            civilization="Sylgard",
            culture_id="desert",
            dynasty_name="Malim",
            age=42,
            estimated_birth_year=1,
            health=72.0,
            loyalty=51.0,
            authority=46.0,
            grievance=22.0,
            fatigue=17.0,
            relation_to_ruler="ruler",
            parent_names=("Malim",),
            grudge_targets=("Quor-Thal (12)",),
            needs=NeedsSnapshot(food=43.0, safety=4.0, belonging=4.0, esteem=0.0),
            recent_events=("Y2 Summer · Famine: A sustained shortage hardened into famine.",),
            caused_by_events=("Famine <- Food Shortage (Sylgard)",),
            led_to_events=("Famine -> Faction Pressure (Sylgard)",),
        ),
        heir_bio=AgentBioSnapshot(
            agent_id="Sylgard_Heir_Jabib_ibn_Nadi_5678",
            name="Jabib ibn Nadi",
            role="Heir",
            civilization="Sylgard",
            culture_id="desert",
            dynasty_name="Malim",
            age=18,
            estimated_birth_year=25,
            health=86.0,
            loyalty=60.0,
            authority=41.0,
            grievance=8.0,
            fatigue=5.0,
            relation_to_ruler="heir, child of ruler",
            parent_names=("Nadi ibn Malim",),
            grudge_targets=(),
            needs=NeedsSnapshot(food=12.0, safety=3.0, belonging=4.0, esteem=5.0),
            recent_events=("Y2 Summer · Food Shortage: Granaries failed to meet demand.",),
            caused_by_events=(),
            led_to_events=(),
        ),
        general_bio=AgentBioSnapshot(
            agent_id="Sylgard_General_Faris_ibn_Nadi_2468",
            name="Faris ibn Nadi",
            role="General",
            civilization="Sylgard",
            culture_id="desert",
            dynasty_name="Malim",
            age=34,
            estimated_birth_year=9,
            health=78.0,
            loyalty=48.0,
            authority=57.0,
            grievance=16.0,
            fatigue=22.0,
            relation_to_ruler="court insider",
            parent_names=("Nadi ibn Malim",),
            grudge_targets=("Quor-Thal (9)",),
            needs=NeedsSnapshot(food=10.0, safety=17.0, belonging=6.0, esteem=8.0),
            recent_events=("Y2 Autumn · Battle: Faris ibn Nadi led troops over the route.",),
            caused_by_events=("Battle <- War Declaration (Sylgard)",),
            led_to_events=("Battle -> Diplomatic Peace (Sylgard)",),
        ),
        diplomat_bio=AgentBioSnapshot(
            agent_id="Sylgard_Diplomat_Samira_bint_Nadi_1357",
            name="Samira bint Nadi",
            role="Diplomat",
            civilization="Sylgard",
            culture_id="desert",
            dynasty_name="Malim",
            age=31,
            estimated_birth_year=12,
            health=82.0,
            loyalty=54.0,
            authority=44.0,
            grievance=12.0,
            fatigue=9.0,
            relation_to_ruler="court insider",
            parent_names=("Nadi ibn Malim",),
            grudge_targets=(),
            needs=NeedsSnapshot(food=8.0, safety=6.0, belonging=11.0, esteem=9.0),
            recent_events=("Y2 Winter · Diplomatic Peace: Exhaustion forced peace after raiding.",),
            caused_by_events=("Diplomatic Peace <- Battle (Sylgard)",),
            led_to_events=("Diplomatic Peace -> Route Reopened (Sylgard)",),
        ),
    )


def _mock_faction_snapshot() -> FactionSnapshot:
    return FactionSnapshot(
        name="Commoners",
        agenda="food security",
        leader_name="Karid ibn Nadi",
        leader_agent_id="Sylgard_Commoner_Tribune_Karid_ibn_Nadi_9012",
        dynasty_name="Malim",
        pressure=77.3,
        needs=NeedsSnapshot(food=31.0, safety=12.0, belonging=18.0, esteem=7.0),
        leader_bio=AgentBioSnapshot(
            agent_id="Sylgard_Commoner_Tribune_Karid_ibn_Nadi_9012",
            name="Karid ibn Nadi",
            role="Commoner Tribune",
            civilization="Sylgard",
            culture_id="desert",
            dynasty_name="Malim",
            age=29,
            estimated_birth_year=14,
            health=80.0,
            loyalty=37.0,
            authority=52.0,
            grievance=41.0,
            fatigue=11.0,
            relation_to_ruler="outside court",
            parent_names=("Nadi ibn Malim",),
            grudge_targets=("Sylgard court (18)",),
            needs=NeedsSnapshot(food=31.0, safety=12.0, belonging=18.0, esteem=7.0),
            recent_events=("Y3 Spring · Faction Pressure: Karid ibn Nadi rallied the commoners.",),
            caused_by_events=("Faction Pressure <- Famine (Sylgard)",),
            led_to_events=("Faction Pressure -> Faction Coup (Sylgard)",),
        ),
    )


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

from typing import Protocol, Sequence

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from fantasy_engine.visual.dashboard import CourtRow, DashboardSnapshot, EventRow, FactionRow, NeedsView, VisibleActorRow


class DashboardRenderer(Protocol):
    def render_run_start(self, *, seed: int, years: int | None, snapshot: DashboardSnapshot) -> None: ...

    def render_year_close(self, *, year: int, snapshot: DashboardSnapshot) -> None: ...

    def render_run_end(self, cause_effect_pairs: Sequence[tuple[str, str]]) -> None: ...


class RichDashboardRenderer:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render_run_start(self, *, seed: int, years: int | None, snapshot: DashboardSnapshot) -> None:
        years_label = years if years is not None else "open-ended"
        self.console.print(self.compose_frame(title=f"Fantasy Engine vertical slice | seed={seed} | years={years_label}", snapshot=snapshot))

    def render_year_close(self, *, year: int, snapshot: DashboardSnapshot) -> None:
        self.console.print(self.compose_frame(title=f"Year {year} close", snapshot=snapshot, rule_style="bold green"))

    def render_run_end(self, cause_effect_pairs: Sequence[tuple[str, str]]) -> None:
        table = Table(title="Recent Cause-Effect Links", show_header=True, header_style="bold yellow")
        table.add_column("Cause")
        table.add_column("Effect")
        for source_id, target_id in cause_effect_pairs:
            table.add_row(source_id, target_id)
        self.console.print(table)

    def compose_frame(
        self,
        *,
        title: str,
        snapshot: DashboardSnapshot,
        rule_style: str = "bold cyan",
        selected_actor_index: int = 0,
        selected_event_index: int = 0,
        biography_visible: bool = False,
    ) -> Group:
        compact = self._is_compact_width()
        detail_mode = self._detail_mode()
        selected_actor = self._selected_actor(snapshot, selected_actor_index)
        renderables = [
            Rule(title, style=rule_style),
            self._status_table(snapshot, title="Status", compact=compact),
        ]
        if detail_mode != "minimal":
            renderables.insert(1, self._routes_table(snapshot))
        if detail_mode in {"full", "court"}:
            renderables.append(self._court_table(snapshot, title="Court", compact=compact, selected_actor=selected_actor))
        if detail_mode == "full":
            renderables.append(self._factions_table(snapshot, title="Factions", compact=compact, selected_actor=selected_actor))
        event_lines = self._event_lines(snapshot, detail_mode=detail_mode)
        if event_lines:
            renderables.append(Panel(self._event_panel_text(event_lines, selected_event_index=selected_event_index), title="Events", border_style="magenta"))
        if biography_visible and selected_actor is not None and detail_mode != "minimal":
            biography_panel = self._biography_panel(selected_actor)
            if biography_panel is not None:
                renderables.append(biography_panel)
        return Group(*renderables)

    def _routes_table(self, snapshot: DashboardSnapshot) -> Table:
        table = Table(title="Routes", show_header=True, header_style="bold yellow")
        table.add_column("Link")
        table.add_column("Dist", justify="right")
        table.add_column("Cap", justify="right")
        table.add_column("Risk", justify="right")
        table.add_column("State")
        for route in snapshot.route_rows:
            state_style = self._route_style(route.state)
            table.add_row(
                f"{route.civilization_a}<->{route.civilization_b}",
                f"{route.distance:.1f}",
                f"{route.effective_capacity}/{route.capacity}",
                f"{route.effective_risk:.2f}",
                Text(route.state, style=state_style),
            )
        return table

    def _status_table(self, snapshot: DashboardSnapshot, *, title: str, compact: bool) -> Table:
        table = Table(title=title, show_header=True, header_style="bold yellow")
        table.add_column("Civ")
        if not compact:
            table.add_column("Culture")
        table.add_column("Pop", justify="right")
        table.add_column("Grn", justify="right")
        table.add_column("Food", justify="right")
        if not compact:
            table.add_column("Arm", justify="right")
            table.add_column("Sup", justify="right")
        table.add_column("Stb", justify="right")
        table.add_column("Leg", justify="right")
        table.add_column("Unr", justify="right")
        if not compact:
            table.add_column("W", justify="right")
        table.add_column("Rt", justify="right")
        for row in snapshot.status_rows:
            route_pressure = f"{row.contested_routes}/{row.severed_routes}"
            cells = [
                row.civilization,
                self._status_value(str(row.population), self._population_style(row.population)),
                self._status_value(str(row.grain_stores), self._store_style(row.grain_stores)),
                self._status_value(str(row.food_stores), self._store_style(row.food_stores)),
            ]
            if not compact:
                cells.insert(1, row.culture_id)
                cells.extend([
                    self._status_value(str(row.weapons_stockpile), self._stockpile_style(row.weapons_stockpile)),
                    self._status_value(str(row.supply_stockpile), self._stockpile_style(row.supply_stockpile)),
                ])
            cells.extend([
                self._status_value(f"{row.stability:.1f}", self._high_good_style(row.stability)),
                self._status_value(f"{row.legitimacy:.1f}", self._high_good_style(row.legitimacy)),
                self._status_value(f"{row.unrest:.1f}", self._low_good_style(row.unrest)),
            ])
            if not compact:
                cells.append(self._status_value(str(row.war_count), self._war_style(row.war_count)))
            cells.append(self._status_value(route_pressure, self._route_pressure_style(row.contested_routes, row.severed_routes)))
            table.add_row(*cells)
        return table

    def _court_table(self, snapshot: DashboardSnapshot, *, title: str, compact: bool, selected_actor: VisibleActorRow | None) -> Table:
        table = Table(title=title, show_header=True, header_style="bold yellow")
        table.add_column("M", justify="center")
        table.add_column("Sel")
        table.add_column("Civ")
        table.add_column("Ruler")
        table.add_column("Heir")
        if not compact:
            table.add_column("Culture")
            table.add_column("Dynasty")
            table.add_column("Parent")
        table.add_column("Need F/S/B/E")
        for index, row in enumerate(snapshot.court_rows):
            selected = selected_actor is not None and selected_actor.section == "court" and selected_actor.row_index == index
            style = self._court_row_style(row, selected)
            cells = [
                self._court_marker(row, selected, selected_actor),
                self._court_selection_label(selected, selected_actor),
                row.civilization,
                row.ruler_name,
                row.heir_name,
            ]
            if not compact:
                cells.extend([row.culture_id, row.dynasty_name, row.heir_parent_name])
            cells.append(self._needs_summary(row.needs))
            table.add_row(*cells, style=style)
        return table

    def _factions_table(self, snapshot: DashboardSnapshot, *, title: str, compact: bool, selected_actor: VisibleActorRow | None) -> Table:
        table = Table(title=title, show_header=True, header_style="bold yellow")
        table.add_column("M", justify="center")
        table.add_column("Civ")
        table.add_column("Faction" if not compact else "Fac")
        table.add_column("Leader")
        if not compact:
            table.add_column("Dynasty")
        table.add_column("Pressure", justify="right")
        table.add_column("Agenda")
        if not compact:
            table.add_column("Need F/S/B/E")
        for index, row in enumerate(snapshot.faction_rows):
            selected = selected_actor is not None and selected_actor.section == "faction" and selected_actor.row_index == index
            style = self._faction_row_style(row, selected)
            cells = [
                self._faction_marker(row, selected),
                row.civilization,
                row.faction_name,
                row.leader_name,
            ]
            if not compact:
                cells.append(row.dynasty_name)
            cells.extend([f"{row.pressure:.1f}", row.agenda])
            if not compact:
                cells.append(self._needs_summary(row.needs))
            table.add_row(*cells, style=style)
        return table

    def _is_compact_width(self) -> bool:
        return self.console.size.width < 130

    def _detail_mode(self) -> str:
        height = self.console.size.height
        if height < 26:
            return "minimal"
        if height < 44:
            return "summary"
        if height < 60:
            return "court"
        return "full"

    def _event_lines(self, snapshot: DashboardSnapshot, *, detail_mode: str) -> list[EventRow]:
        if not snapshot.key_events:
            return []
        limits = {
            "minimal": 2,
            "summary": 3,
            "court": 4,
            "full": 6,
        }
        limit = limits.get(detail_mode, 3)
        if len(snapshot.key_events) <= limit:
            return snapshot.key_events
        hidden_count = len(snapshot.key_events) - limit
        return [*snapshot.key_events[:limit], EventRow(summary=f"... {hidden_count} more", context="", severity="normal")]

    def _render_routes(self, snapshot: DashboardSnapshot) -> None:
        self.console.print(self._routes_table(snapshot))

    def _render_status(self, snapshot: DashboardSnapshot, *, title: str) -> None:
        self.console.print(self._status_table(snapshot, title=title, compact=self._is_compact_width()))

    def _render_court(self, snapshot: DashboardSnapshot, *, title: str) -> None:
        self.console.print(self._court_table(snapshot, title=title, compact=self._is_compact_width(), selected_actor=self._selected_actor(snapshot, 0)))

    def _render_factions(self, snapshot: DashboardSnapshot, *, title: str) -> None:
        self.console.print(self._factions_table(snapshot, title=title, compact=self._is_compact_width(), selected_actor=self._selected_actor(snapshot, 0)))

    def _needs_summary(self, needs: NeedsView) -> str:
        return f"{needs.food:>2.0f}/{needs.safety:>2.0f}/{needs.belonging:>2.0f}/{needs.esteem:>2.0f}"

    def _route_style(self, state: str) -> str:
        if state == "severed":
            return "bold red"
        if state == "contested":
            return "bold yellow"
        return "green"

    def _event_panel_text(self, event_rows: list[EventRow], *, selected_event_index: int) -> Text:
        text = Text()
        selected_index = selected_event_index % len(event_rows) if event_rows else 0
        for index, event in enumerate(event_rows):
            if index:
                text.append("\n")
            selected = index == selected_index
            text.append("> " if selected else "- ", style=self._event_style(event.severity, selected=selected))
            text.append(event.summary, style=self._event_style(event.severity, selected=selected))
            if event.context:
                text.append("\n  ")
                text.append(event.context, style="dim")
            if selected and event.caused_by:
                text.append("\n  Caused by:")
                for line in event.caused_by:
                    text.append("\n    - ")
                    text.append(line, style="dim")
            if selected and event.led_to:
                text.append("\n  Led to:")
                for line in event.led_to:
                    text.append("\n    - ")
                    text.append(line, style="dim")
        return text

    def _biography_panel(self, actor: VisibleActorRow) -> Panel | None:
        bio = actor.biography
        if bio is None:
            return None
        lines = [
            f"{bio.name} · {bio.role} · {bio.relation_to_ruler or 'court figure'}",
            f"Civ: {bio.civilization} | Culture: {bio.culture_id} | Dynasty: {bio.dynasty_name}",
            f"Age: {bio.age} | Born ~ Year {bio.estimated_birth_year} | Health: {bio.health:.1f}",
            f"Needs F/S/B/E: {self._needs_summary(NeedsView(bio.needs.food, bio.needs.safety, bio.needs.belonging, bio.needs.esteem))}",
            f"Loyalty: {bio.loyalty:.1f} | Authority: {bio.authority:.1f} | Grievance: {bio.grievance:.1f} | Fatigue: {bio.fatigue:.1f}",
            f"Parents: {', '.join(bio.parent_names) if bio.parent_names else 'unknown'}",
            f"Grudges: {', '.join(bio.grudge_targets) if bio.grudge_targets else 'none'}",
        ]
        if bio.recent_events:
            lines.append("Recent events:")
            lines.extend(f"- {event}" for event in bio.recent_events)
        if bio.caused_by_events:
            lines.append("Caused by:")
            lines.extend(f"- {event}" for event in bio.caused_by_events)
        if bio.led_to_events:
            lines.append("Led to:")
            lines.extend(f"- {event}" for event in bio.led_to_events)
        return Panel(Text("\n".join(lines)), title=f"Biography · {bio.name} · {actor.relation_label}", border_style="cyan")

    def _court_marker(self, row: CourtRow, selected: bool, actor: VisibleActorRow | None) -> str:
        if selected and row.changed:
            return "*"
        if selected:
            if actor is not None and actor.relation_label == "heir":
                return "H"
            if actor is not None and actor.relation_label == "general":
                return "G"
            if actor is not None and actor.relation_label == "diplomat":
                return "D"
            return ">"
        if row.changed:
            return "+"
        return " "

    def _court_selection_label(self, selected: bool, actor: VisibleActorRow | None) -> str:
        if not selected or actor is None:
            return ""
        return actor.relation_label.title()

    def _court_row_style(self, row: CourtRow, selected: bool) -> str:
        if selected:
            return "bold bright_cyan"
        if row.changed:
            return "bold bright_yellow"
        return "default"

    def _faction_marker(self, row: FactionRow, selected: bool) -> str:
        if selected and row.changed:
            return "*"
        if selected:
            return ">"
        if row.changed:
            return "+"
        return " "

    def _event_style(self, severity: str, *, selected: bool = False) -> str:
        suffix = " underline" if selected else ""
        if severity == "catastrophic":
            return f"bold red{suffix}"
        if severity == "major":
            return f"bold yellow{suffix}"
        return f"default{suffix}".strip()

    def _status_value(self, value: str, style: str) -> Text:
        return Text(value, style=style)

    def _population_style(self, value: int) -> str:
        if value < 7000:
            return "bold red"
        if value < 11000:
            return "yellow"
        return "green"

    def _store_style(self, value: int) -> str:
        if value <= 0:
            return "bold red"
        if value < 25:
            return "yellow"
        return "green"

    def _stockpile_style(self, value: int) -> str:
        if value < 20:
            return "bold red"
        if value < 60:
            return "yellow"
        return "green"

    def _high_good_style(self, value: float) -> str:
        if value < 35.0:
            return "bold red"
        if value < 55.0:
            return "yellow"
        return "green"

    def _low_good_style(self, value: float) -> str:
        if value >= 60.0:
            return "bold red"
        if value >= 30.0:
            return "yellow"
        return "green"

    def _war_style(self, value: int) -> str:
        if value >= 2:
            return "bold red"
        if value == 1:
            return "yellow"
        return "green"

    def _route_pressure_style(self, contested: int, severed: int) -> str:
        if severed > 0:
            return "bold red"
        if contested > 0:
            return "yellow"
        return "green"

    def _selected_actor(self, snapshot: DashboardSnapshot, selected_actor_index: int) -> VisibleActorRow | None:
        if not snapshot.visible_actors:
            return None
        return snapshot.visible_actors[selected_actor_index % len(snapshot.visible_actors)]

    def _faction_row_style(self, row: FactionRow, selected: bool) -> str:
        if selected:
            return "bold bright_cyan"
        if row.changed:
            return "bold bright_yellow"
        return self._faction_style(row)

    def _faction_style(self, row: FactionRow) -> str:
        if row.pressure >= 78.0:
            return "red"
        if row.pressure >= 50.0:
            return "yellow"
        return "default"
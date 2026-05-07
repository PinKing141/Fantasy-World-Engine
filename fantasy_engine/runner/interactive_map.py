"""Interactive procedural-world map runtime.

This is a pygame-ce viewer layered on top of the static cartographer. It
adds:

    * Pan with right-mouse-drag (or middle-drag, or arrow keys)
    * Zoom with the mouse wheel, centered on the cursor
    * Hover highlighting of provinces
    * Click-to-select with a side panel showing the selected province
    * Continent navigation: press 1..9 to jump to that landmass
    * Keyboard reseed: press R to roll a new world
    * F1 to toggle the help overlay
    * F2 to toggle province borders

The runtime is intentionally read-only and isolated from the simulation core.
It pulls a `GeographyResult` and `ProvinceMap` and renders them; if you later
attach civilizations to provinces, you only have to surface the bindings in
the side panel - the picking, camera, and rendering pipeline don't need to
change.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

import numpy as np
import pygame

from fantasy_engine.world.geography import GeographyConfig, GeographyResult, generate_geography
from fantasy_engine.world.provinces import Province, ProvinceMap, build_province_map
from fantasy_engine.visual.cartographer import CartographyOptions, RenderInputs, render_world


SIDE_PANEL_WIDTH = 320
DEFAULT_WINDOW_SIZE = (1280, 800)
MIN_CELL_PIXELS = 2.0
MAX_CELL_PIXELS = 24.0
DEFAULT_CELL_PIXELS = 4.5
PAN_SPEED_KEY = 380.0
ZOOM_STEP = 1.18

BACKGROUND_COLOR = (18, 22, 28)
PANEL_BG_COLOR = (28, 32, 40)
PANEL_BORDER_COLOR = (60, 66, 78)
TEXT_COLOR = (228, 228, 220)
DIM_TEXT_COLOR = (160, 162, 158)
HIGHLIGHT_COLOR = (255, 220, 120)


@dataclass(slots=True)
class Camera:
    """Maps world cell coordinates to screen pixels."""

    world_width: int
    world_height: int
    viewport_size: tuple[int, int]
    center_x: float = 0.0
    center_y: float = 0.0
    cell_pixels: float = DEFAULT_CELL_PIXELS

    def __post_init__(self) -> None:
        self.center_x = self.world_width / 2.0
        self.center_y = self.world_height / 2.0

    def update_viewport(self, viewport_size: tuple[int, int]) -> None:
        self.viewport_size = viewport_size
        self._clamp_center()

    def screen_to_world(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        viewport_w, viewport_h = self.viewport_size
        world_x = self.center_x + (screen_x - viewport_w / 2.0) / self.cell_pixels
        world_y = self.center_y + (screen_y - viewport_h / 2.0) / self.cell_pixels
        return world_x, world_y

    def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        viewport_w, viewport_h = self.viewport_size
        screen_x = (world_x - self.center_x) * self.cell_pixels + viewport_w / 2.0
        screen_y = (world_y - self.center_y) * self.cell_pixels + viewport_h / 2.0
        return screen_x, screen_y

    def pan(self, delta_screen_x: float, delta_screen_y: float) -> None:
        self.center_x -= delta_screen_x / self.cell_pixels
        self.center_y -= delta_screen_y / self.cell_pixels
        self._clamp_center()

    def zoom_at(self, screen_x: float, screen_y: float, factor: float) -> None:
        before_world_x, before_world_y = self.screen_to_world(screen_x, screen_y)
        self.cell_pixels = float(np.clip(self.cell_pixels * factor, MIN_CELL_PIXELS, MAX_CELL_PIXELS))
        after_world_x, after_world_y = self.screen_to_world(screen_x, screen_y)
        self.center_x += before_world_x - after_world_x
        self.center_y += before_world_y - after_world_y
        self._clamp_center()

    def visible_world_rect(self) -> tuple[float, float, float, float]:
        viewport_w, viewport_h = self.viewport_size
        half_w = viewport_w / 2.0 / self.cell_pixels
        half_h = viewport_h / 2.0 / self.cell_pixels
        return (
            self.center_x - half_w,
            self.center_y - half_h,
            self.center_x + half_w,
            self.center_y + half_h,
        )

    def jump_to(self, world_x: float, world_y: float, *, cell_pixels: float | None = None) -> None:
        self.center_x = world_x
        self.center_y = world_y
        if cell_pixels is not None:
            self.cell_pixels = float(np.clip(cell_pixels, MIN_CELL_PIXELS, MAX_CELL_PIXELS))
        self._clamp_center()

    def _clamp_center(self) -> None:
        viewport_w, viewport_h = self.viewport_size
        half_w_world = viewport_w / 2.0 / self.cell_pixels
        half_h_world = viewport_h / 2.0 / self.cell_pixels
        self.center_x = float(np.clip(self.center_x, -half_w_world, self.world_width + half_w_world))
        self.center_y = float(np.clip(self.center_y, -half_h_world, self.world_height + half_h_world))


@dataclass(slots=True)
class RenderCache:
    """Caches the cartographer's RGB output as a pygame Surface."""

    options: CartographyOptions
    selected_province_id: int | None
    hovered_province_id: int | None
    surface: pygame.Surface

    @classmethod
    def build(cls, geography: GeographyResult, provinces: ProvinceMap, options: CartographyOptions, selected: int | None, hovered: int | None) -> "RenderCache":
        rgb = render_world(RenderInputs(
            geography=geography,
            provinces=provinces,
            selected_province_id=selected,
            hovered_province_id=hovered,
            options=options,
        ))
        surface = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
        return cls(options=options, selected_province_id=selected, hovered_province_id=hovered, surface=surface)


def _format_province_summary(province: Province, geography: GeographyResult) -> list[tuple[str, tuple[int, int, int]]]:
    title_color = HIGHLIGHT_COLOR
    label_color = DIM_TEXT_COLOR
    value_color = TEXT_COLOR

    lines: list[tuple[str, tuple[int, int, int]]] = []
    lines.append((f"Province #{province.province_id}", title_color))
    lines.append((province.name or "(unnamed)", value_color))
    lines.append(("", value_color))
    lines.append((f"Landmass:        #{province.landmass_id}", label_color))
    lines.append((f"Cells:           {province.cell_count}", label_color))
    lines.append((f"Coastal:         {'yes' if province.is_coastal else 'no'}", label_color))
    lines.append((f"River:           {'yes' if province.has_river else 'no'}", label_color))
    lines.append(("", value_color))
    lines.append(("Climate", title_color))
    lines.append((f"Elevation:       {province.mean_elevation:+.2f}", value_color))
    lines.append((f"Temperature:     {province.mean_temperature:.2f}", value_color))
    lines.append((f"Moisture:        {province.mean_moisture:.2f}", value_color))
    lines.append(("", value_color))
    lines.append(("Biome mix", title_color))
    lines.append((f"Dominant: {province.dominant_biome}", value_color))
    for biome_name, share in sorted(province.biome_mix.items(), key=lambda item: item[1], reverse=True)[:5]:
        lines.append((f"  {biome_name:<18} {share:>5.1%}", value_color))
    lines.append(("", value_color))
    if province.neighbor_ids:
        lines.append(("Neighbors", title_color))
        neighbor_text = ", ".join(f"#{neighbor_id}" for neighbor_id in province.neighbor_ids[:8])
        if len(province.neighbor_ids) > 8:
            neighbor_text += f"  (+{len(province.neighbor_ids) - 8} more)"
        lines.append((neighbor_text, value_color))
    return lines


def _format_world_summary(geography: GeographyResult, provinces: ProvinceMap) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    lines.append(("Procedural World", HIGHLIGHT_COLOR))
    lines.append((f"Seed:            {geography.config.seed}", DIM_TEXT_COLOR))
    lines.append((f"Size:            {geography.config.width} x {geography.config.height}", DIM_TEXT_COLOR))
    lines.append((f"Land fraction:   {geography.land_mask.mean():.0%}", DIM_TEXT_COLOR))
    lines.append((f"Sea level:       {geography.sea_level:+.3f}", DIM_TEXT_COLOR))
    lines.append((f"Landmasses:      {len(geography.landmasses)}", DIM_TEXT_COLOR))
    continent_count = sum(1 for landmass in geography.landmasses if landmass.is_continent)
    lines.append((f"  continents:    {continent_count}", DIM_TEXT_COLOR))
    lines.append((f"  islands:       {len(geography.landmasses) - continent_count}", DIM_TEXT_COLOR))
    lines.append((f"Provinces:       {len(provinces.provinces)}", DIM_TEXT_COLOR))
    lines.append((f"Rivers:          {int(geography.rivers.sum())} cells", DIM_TEXT_COLOR))
    lines.append(("", TEXT_COLOR))
    lines.append(("Click a province to inspect", DIM_TEXT_COLOR))
    return lines


def _help_overlay_lines() -> list[str]:
    return [
        "MAP CONTROLS",
        "",
        "  Right/Middle-drag    Pan",
        "  Mouse wheel          Zoom (toward cursor)",
        "  Arrow keys / WASD    Pan",
        "  Left-click           Select province",
        "  1-9                  Jump to landmass",
        "  R                    Reseed world",
        "  F1                   Toggle this help",
        "  F2                   Toggle province borders",
        "  F3                   Toggle hill shading",
        "  ESC                  Clear selection / quit help",
        "  Q                    Quit",
    ]


@dataclass(slots=True)
class InteractiveMapState:
    geography: GeographyResult
    provinces: ProvinceMap
    options: CartographyOptions = field(default_factory=CartographyOptions)
    selected_province_id: int | None = None
    hovered_province_id: int | None = None
    show_help: bool = False


def run_interactive_map(
    *,
    config: GeographyConfig | None = None,
    initial_state: InteractiveMapState | None = None,
    window_size: tuple[int, int] = DEFAULT_WINDOW_SIZE,
    on_close: Callable[[], None] | None = None,
) -> None:
    """Open a pygame window and run the interactive map until the user quits."""
    if initial_state is None:
        config = config or GeographyConfig()
        geography = generate_geography(config)
        provinces = build_province_map(geography)
        initial_state = InteractiveMapState(geography=geography, provinces=provinces)

    pygame.init()
    pygame.display.set_caption("Fantasy Engine - Procedural World Map")
    screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    fonts = _load_fonts()

    state = initial_state
    camera = Camera(
        world_width=state.geography.config.width,
        world_height=state.geography.config.height,
        viewport_size=_map_viewport_size(window_size),
    )
    cache = RenderCache.build(state.geography, state.provinces, state.options, state.selected_province_id, state.hovered_province_id)

    running = True
    panning = False
    pan_anchor: tuple[int, int] | None = None
    keys_held: set[int] = set()

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                camera.update_viewport(_map_viewport_size(event.size))
            elif event.type == pygame.KEYDOWN:
                keys_held.add(event.key)
                running, state, cache, camera = _handle_keydown(event, state, cache, camera)
            elif event.type == pygame.KEYUP:
                keys_held.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                state, cache, panning, pan_anchor = _handle_mouse_down(event, state, cache, camera, panning, pan_anchor)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (2, 3):
                    panning = False
                    pan_anchor = None
            elif event.type == pygame.MOUSEMOTION:
                state, cache, pan_anchor = _handle_mouse_motion(event, state, cache, camera, panning, pan_anchor)
            elif event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if mouse_x < camera.viewport_size[0]:
                    factor = ZOOM_STEP if event.y > 0 else 1.0 / ZOOM_STEP
                    camera.zoom_at(mouse_x, mouse_y, factor)

        _apply_keyboard_pan(camera, keys_held, dt)
        _draw_frame(screen, state, cache, camera, fonts)
        pygame.display.flip()

    pygame.quit()
    if on_close is not None:
        on_close()


def _load_fonts() -> dict[str, pygame.font.Font]:
    return {
        "title": pygame.font.SysFont("consolas,menlo,monospace", 18, bold=True),
        "body": pygame.font.SysFont("consolas,menlo,monospace", 14),
        "small": pygame.font.SysFont("consolas,menlo,monospace", 12),
    }


def _map_viewport_size(window_size: tuple[int, int]) -> tuple[int, int]:
    return (max(200, window_size[0] - SIDE_PANEL_WIDTH), window_size[1])


def _handle_keydown(event: pygame.event.Event, state: InteractiveMapState, cache: RenderCache, camera: Camera) -> tuple[bool, InteractiveMapState, RenderCache, Camera]:
    if event.key in (pygame.K_q,):
        return False, state, cache, camera
    if event.key == pygame.K_ESCAPE:
        if state.show_help:
            state = replace(state, show_help=False)
        elif state.selected_province_id is not None:
            state = replace(state, selected_province_id=None)
            cache = RenderCache.build(state.geography, state.provinces, state.options, state.selected_province_id, state.hovered_province_id)
        return True, state, cache, camera
    if event.key == pygame.K_F1:
        state = replace(state, show_help=not state.show_help)
        return True, state, cache, camera
    if event.key == pygame.K_F2:
        new_options = replace(state.options, show_province_borders=not state.options.show_province_borders)
        state = replace(state, options=new_options)
        cache = RenderCache.build(state.geography, state.provinces, new_options, state.selected_province_id, state.hovered_province_id)
        return True, state, cache, camera
    if event.key == pygame.K_F3:
        new_strength = 0.0 if state.options.hillshade_strength > 0.0 else 0.55
        new_options = replace(state.options, hillshade_strength=new_strength)
        state = replace(state, options=new_options)
        cache = RenderCache.build(state.geography, state.provinces, new_options, state.selected_province_id, state.hovered_province_id)
        return True, state, cache, camera
    if event.key == pygame.K_r:
        new_seed = (state.geography.config.seed * 1664525 + 1013904223) & 0x7FFFFFFF
        new_config = replace(state.geography.config, seed=new_seed)
        new_geography = generate_geography(new_config)
        new_provinces = build_province_map(new_geography)
        state = InteractiveMapState(geography=new_geography, provinces=new_provinces, options=state.options)
        camera = Camera(world_width=new_geography.config.width, world_height=new_geography.config.height, viewport_size=camera.viewport_size)
        cache = RenderCache.build(new_geography, new_provinces, state.options, None, None)
        return True, state, cache, camera
    if pygame.K_1 <= event.key <= pygame.K_9:
        index = event.key - pygame.K_1
        sorted_landmasses = sorted(state.geography.landmasses, key=lambda landmass: landmass.cell_count, reverse=True)
        if index < len(sorted_landmasses):
            target = sorted_landmasses[index]
            camera.jump_to(target.centroid_x, target.centroid_y, cell_pixels=max(camera.cell_pixels, 6.0))
    return True, state, cache, camera


def _handle_mouse_down(event: pygame.event.Event, state: InteractiveMapState, cache: RenderCache, camera: Camera, panning: bool, pan_anchor: tuple[int, int] | None) -> tuple[InteractiveMapState, RenderCache, bool, tuple[int, int] | None]:
    if event.button == 1:
        if event.pos[0] >= camera.viewport_size[0]:
            return state, cache, panning, pan_anchor
        province_id = _province_id_at_screen(event.pos, state, camera)
        if province_id != state.selected_province_id:
            state = replace(state, selected_province_id=province_id)
            cache = RenderCache.build(state.geography, state.provinces, state.options, province_id, state.hovered_province_id)
    elif event.button in (2, 3):
        panning = True
        pan_anchor = event.pos
    return state, cache, panning, pan_anchor


def _handle_mouse_motion(event: pygame.event.Event, state: InteractiveMapState, cache: RenderCache, camera: Camera, panning: bool, pan_anchor: tuple[int, int] | None) -> tuple[InteractiveMapState, RenderCache, tuple[int, int] | None]:
    if panning and pan_anchor is not None:
        delta_x = event.pos[0] - pan_anchor[0]
        delta_y = event.pos[1] - pan_anchor[1]
        camera.pan(delta_x, delta_y)
        pan_anchor = event.pos
        return state, cache, pan_anchor

    if event.pos[0] >= camera.viewport_size[0]:
        if state.hovered_province_id is not None:
            state = replace(state, hovered_province_id=None)
            cache = RenderCache.build(state.geography, state.provinces, state.options, state.selected_province_id, None)
        return state, cache, pan_anchor

    province_id = _province_id_at_screen(event.pos, state, camera)
    if province_id != state.hovered_province_id:
        state = replace(state, hovered_province_id=province_id)
        cache = RenderCache.build(state.geography, state.provinces, state.options, state.selected_province_id, province_id)
    return state, cache, pan_anchor


def _province_id_at_screen(screen_pos: tuple[int, int], state: InteractiveMapState, camera: Camera) -> int | None:
    world_x, world_y = camera.screen_to_world(*screen_pos)
    grid_x = int(round(world_x))
    grid_y = int(round(world_y))
    height, width = state.geography.elevation.shape
    if not (0 <= grid_x < width and 0 <= grid_y < height):
        return None
    province_id = int(state.provinces.province_id_grid[grid_y, grid_x])
    return province_id if province_id >= 0 else None


def _apply_keyboard_pan(camera: Camera, keys_held: set[int], dt: float) -> None:
    delta_x = 0.0
    delta_y = 0.0
    if pygame.K_LEFT in keys_held or pygame.K_a in keys_held:
        delta_x += PAN_SPEED_KEY * dt
    if pygame.K_RIGHT in keys_held or pygame.K_d in keys_held:
        delta_x -= PAN_SPEED_KEY * dt
    if pygame.K_UP in keys_held or pygame.K_w in keys_held:
        delta_y += PAN_SPEED_KEY * dt
    if pygame.K_DOWN in keys_held or pygame.K_s in keys_held:
        delta_y -= PAN_SPEED_KEY * dt
    if delta_x != 0.0 or delta_y != 0.0:
        camera.pan(delta_x, delta_y)


def _draw_frame(screen: pygame.Surface, state: InteractiveMapState, cache: RenderCache, camera: Camera, fonts: dict[str, pygame.font.Font]) -> None:
    screen.fill(BACKGROUND_COLOR)
    _draw_map(screen, cache, camera)
    _draw_side_panel(screen, state, fonts)
    _draw_top_bar(screen, state, camera, fonts)
    if state.show_help:
        _draw_help_overlay(screen, fonts)


def _draw_map(screen: pygame.Surface, cache: RenderCache, camera: Camera) -> None:
    viewport_w, viewport_h = camera.viewport_size
    target_width = int(round(cache.surface.get_width() * camera.cell_pixels))
    target_height = int(round(cache.surface.get_height() * camera.cell_pixels))
    if target_width <= 0 or target_height <= 0:
        return
    scaled = pygame.transform.scale(cache.surface, (target_width, target_height))

    top_left_world = (camera.center_x - viewport_w / 2.0 / camera.cell_pixels, camera.center_y - viewport_h / 2.0 / camera.cell_pixels)
    blit_x = int(round(-top_left_world[0] * camera.cell_pixels))
    blit_y = int(round(-top_left_world[1] * camera.cell_pixels))

    map_rect = pygame.Rect(0, 0, viewport_w, viewport_h)
    screen.set_clip(map_rect)
    screen.blit(scaled, (blit_x, blit_y))
    screen.set_clip(None)


def _draw_side_panel(screen: pygame.Surface, state: InteractiveMapState, fonts: dict[str, pygame.font.Font]) -> None:
    panel_x = screen.get_width() - SIDE_PANEL_WIDTH
    panel_rect = pygame.Rect(panel_x, 0, SIDE_PANEL_WIDTH, screen.get_height())
    pygame.draw.rect(screen, PANEL_BG_COLOR, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER_COLOR, (panel_x, 0), (panel_x, screen.get_height()), 2)

    if state.selected_province_id is not None and 0 <= state.selected_province_id < len(state.provinces.provinces):
        province = state.provinces.provinces[state.selected_province_id]
        lines = _format_province_summary(province, state.geography)
    else:
        lines = _format_world_summary(state.geography, state.provinces)

    y = 18
    for text, color in lines:
        if not text:
            y += 6
            continue
        font = fonts["title"] if color == HIGHLIGHT_COLOR else fonts["body"]
        rendered = font.render(text, True, color)
        screen.blit(rendered, (panel_x + 18, y))
        y += rendered.get_height() + 2


def _draw_top_bar(screen: pygame.Surface, state: InteractiveMapState, camera: Camera, fonts: dict[str, pygame.font.Font]) -> None:
    text = f"seed {state.geography.config.seed}   zoom {camera.cell_pixels:.1f}x   F1 help   R reseed   Q quit"
    rendered = fonts["small"].render(text, True, DIM_TEXT_COLOR)
    bar_rect = pygame.Rect(0, 0, camera.viewport_size[0], rendered.get_height() + 10)
    overlay = pygame.Surface(bar_rect.size, pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 130))
    screen.blit(overlay, bar_rect.topleft)
    screen.blit(rendered, (12, 5))


def _draw_help_overlay(screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
    lines = _help_overlay_lines()
    line_height = fonts["body"].get_linesize()
    panel_w = 380
    panel_h = line_height * (len(lines) + 1) + 30
    panel_x = (screen.get_width() - SIDE_PANEL_WIDTH - panel_w) // 2
    panel_y = (screen.get_height() - panel_h) // 2
    overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    overlay.fill((20, 22, 28, 220))
    pygame.draw.rect(overlay, PANEL_BORDER_COLOR, overlay.get_rect(), 2)
    screen.blit(overlay, (panel_x, panel_y))

    y = panel_y + 18
    for index, line in enumerate(lines):
        font = fonts["title"] if index == 0 else fonts["body"]
        color = HIGHLIGHT_COLOR if index == 0 else TEXT_COLOR
        rendered = font.render(line, True, color)
        screen.blit(rendered, (panel_x + 22, y))
        y += line_height

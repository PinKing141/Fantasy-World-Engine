"""High-quality cartographic rendering for the procedural world.

This is a deliberately layered renderer: each visual effect is its own pass
that reads the geography and writes RGB. The layering is what gives the map
its painted look - flat-color biome maps look like census choropleths, and
nobody wants their fantasy world to look like a census map.

Layer order (bottom to top):
    1. Biome base color           - flat per-cell biome palette
    2. Ocean depth gradient       - smooth blue-by-depth, replaces flat ocean
    3. Hillshading                - Lambertian shading from a low sun
    4. Painterly noise modulation - subtle low-frequency brightness variation
    5. Coastline halo             - soft light ring on water adjacent to land
    6. Rivers                     - single-pixel blue with wider halo
    7. Province borders           - thin, dark brown, semi-transparent
    8. Selection / hover tints    - UI overlays
    9. Vignette                   - gentle darkening at the corners

Each layer is opt-out via CartographyOptions; the web backend uses this to
serve a "raw biome map" debug view without forking the renderer.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from noise import snoise2

from fantasy_engine.world.geography import BIOME_COLORS, GeographyResult
from fantasy_engine.world.provinces import ProvinceMap


@dataclass(frozen=True, slots=True)
class CartographyOptions:
    show_rivers: bool = True
    show_coastline_halo: bool = True
    show_province_borders: bool = True
    show_landmass_borders: bool = False
    apply_ocean_gradient: bool = True
    apply_painterly_noise: bool = True
    apply_vignette: bool = True
    hillshade_strength: float = 0.85
    """0.0 = flat colors. 1.0 = aggressive relief lighting. The default 0.85
    gives the map physical depth without making valleys look bruised."""

    coast_halo_color: tuple[int, int, int] = (148, 196, 218)
    river_color: tuple[int, int, int] = (54, 110, 168)
    province_border_color: tuple[int, int, int] = (38, 30, 24)
    province_border_alpha: float = 0.55
    """Borders blend with the underlying terrain. Solid black borders fight
    the painted look - semi-transparent dark brown reads as ink."""

    landmass_border_color: tuple[int, int, int] = (24, 18, 14)
    selected_province_tint: tuple[int, int, int] = (255, 220, 110)
    hovered_province_tint: tuple[int, int, int] = (255, 248, 200)


@dataclass(frozen=True, slots=True)
class RenderInputs:
    geography: GeographyResult
    provinces: ProvinceMap | None = None
    selected_province_id: int | None = None
    hovered_province_id: int | None = None
    options: CartographyOptions = CartographyOptions()


def render_world(inputs: RenderInputs) -> np.ndarray:
    """Render the world to an (H, W, 3) uint8 RGB array."""
    geography = inputs.geography
    options = inputs.options
    rgb = _base_biome_layer(geography).astype(np.float32)

    if options.apply_ocean_gradient:
        rgb = _apply_ocean_depth_gradient(rgb, geography)

    if options.hillshade_strength > 0.0:
        rgb = _apply_hillshading(rgb, geography, options.hillshade_strength)

    if options.apply_painterly_noise:
        rgb = _apply_painterly_noise(rgb, geography)

    if options.show_coastline_halo:
        rgb = _apply_coastline_halo(rgb, geography, options.coast_halo_color)

    if options.show_rivers:
        rgb = _apply_river_layer(rgb, geography, options.river_color)

    if inputs.provinces is not None:
        if options.show_province_borders:
            rgb = _apply_province_borders(rgb, inputs.provinces, options.province_border_color, options.province_border_alpha)
        if inputs.selected_province_id is not None:
            rgb = _tint_province(rgb, inputs.provinces, inputs.selected_province_id, options.selected_province_tint, alpha=0.40)
        if inputs.hovered_province_id is not None and inputs.hovered_province_id != inputs.selected_province_id:
            rgb = _tint_province(rgb, inputs.provinces, inputs.hovered_province_id, options.hovered_province_tint, alpha=0.22)

    if options.show_landmass_borders:
        rgb = _apply_landmass_borders(rgb, geography, options.landmass_border_color)

    if options.apply_vignette:
        rgb = _apply_vignette(rgb)

    return np.clip(rgb, 0.0, 255.0).astype(np.uint8)


def _base_biome_layer(geography: GeographyResult) -> np.ndarray:
    height, width = geography.elevation.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for biome_idx, biome_name in enumerate(geography.biome_names):
        mask = geography.biome == biome_idx
        if mask.any():
            rgb[mask] = BIOME_COLORS[biome_name]
    return rgb


def _apply_ocean_depth_gradient(rgb: np.ndarray, geography: GeographyResult) -> np.ndarray:
    """Replace flat per-biome ocean colors with a smooth depth gradient.

    The depth field gets a heavy box blur before the gradient is computed,
    which is what stops the open ocean from looking cloudy with the
    underlying elevation noise. Without this blur, every minor fluctuation
    in the seafloor shows up as a light/dark patch on the surface."""
    water = ~geography.land_mask
    if not water.any():
        return rgb

    depth = np.clip(geography.sea_level - geography.elevation, 0.0, None)
    depth = _box_blur(depth, radius=10)
    max_depth = float(depth[water].max())
    if max_depth < 1e-3:
        return rgb
    normalized = depth / max_depth

    coast = np.array([108, 168, 196], dtype=np.float32)
    shallow = np.array([56, 116, 162], dtype=np.float32)
    deep = np.array([22, 46, 84], dtype=np.float32)

    near = _smoothstep(0.0, 0.18, normalized)
    far = _smoothstep(0.18, 0.85, normalized)

    water_color = (
        coast * (1.0 - near[..., None])
        + shallow * (near[..., None] * (1.0 - far[..., None]))
        + deep * far[..., None]
    )

    rgb[water] = water_color[water]
    return rgb


def _apply_hillshading(rgb: np.ndarray, geography: GeographyResult, strength: float) -> np.ndarray:
    """Lambertian hillshading from a fixed low sun (upper-left).

    Both the brighten and darken passes are capped: full Lambert lerps to
    pure white/black, which destroys the underlying biome color. Capping
    the lerps at ~45% keeps the hue while still giving the map dimensional
    depth."""
    elevation = _box_blur(geography.elevation, radius=1)

    light_dx, light_dy, light_dz = -1.0, -1.0, 1.4
    light_norm = float(np.sqrt(light_dx * light_dx + light_dy * light_dy + light_dz * light_dz))

    grad_y, grad_x = np.gradient(elevation)
    dot = (-grad_x * light_dx + -grad_y * light_dy + 1.0 * light_dz) / light_norm
    shading = np.clip(dot, -1.0, 1.0) * strength
    shading = np.where(geography.land_mask, shading, 0.0)

    rgb_float = rgb.astype(np.float32)
    bright_blend = np.clip(shading, 0.0, None)[..., None]
    dark_blend = np.clip(-shading, 0.0, None)[..., None]
    rgb_float = rgb_float + (255.0 - rgb_float) * bright_blend * 0.45
    rgb_float = rgb_float * (1.0 - dark_blend * 0.55)
    return rgb_float


def _apply_painterly_noise(rgb: np.ndarray, geography: GeographyResult) -> np.ndarray:
    """Modulate land brightness by a low-frequency noise field.

    This adds the subtle painterly variation that makes hand-drawn maps look
    like paper rather than vector art."""
    height, width = geography.elevation.shape
    seed = geography.config.seed
    noise_field = np.empty((height, width), dtype=np.float32)
    scale = 75.0
    for y in range(height):
        for x in range(width):
            noise_field[y, x] = snoise2(x / scale, y / scale, octaves=3, persistence=0.5, base=(seed + 31337) % 1024)

    multiplier = 1.0 + noise_field * 0.06
    multiplier = np.where(geography.land_mask, multiplier, 1.0)
    return rgb * multiplier[..., None]


def _apply_coastline_halo(rgb: np.ndarray, geography: GeographyResult, color: tuple[int, int, int]) -> np.ndarray:
    """Soft cyan halo on water cells adjacent to land - gives the coast a
    'lit shore' feel that's classic on cartographer-style maps."""
    water = ~geography.land_mask
    near_land = np.zeros_like(water)
    near_land[1:, :] |= geography.land_mask[:-1, :] & water[1:, :]
    near_land[:-1, :] |= geography.land_mask[1:, :] & water[:-1, :]
    near_land[:, 1:] |= geography.land_mask[:, :-1] & water[:, 1:]
    near_land[:, :-1] |= geography.land_mask[:, 1:] & water[:, :-1]

    halo_color = np.array(color, dtype=np.float32)
    rgb_float = rgb.astype(np.float32)
    rgb_float[near_land] = rgb_float[near_land] * 0.78 + halo_color * 0.22
    return rgb_float


def _apply_river_layer(rgb: np.ndarray, geography: GeographyResult, color: tuple[int, int, int]) -> np.ndarray:
    rivers = geography.rivers
    halo = np.zeros_like(rivers)
    halo[1:, :] |= rivers[:-1, :]
    halo[:-1, :] |= rivers[1:, :]
    halo[:, 1:] |= rivers[:, :-1]
    halo[:, :-1] |= rivers[:, 1:]
    halo &= ~rivers & geography.land_mask

    halo_color = np.array([color[0] + 30, color[1] + 30, color[2] + 30], dtype=np.float32)
    river_color = np.array(color, dtype=np.float32)
    rgb_float = rgb.astype(np.float32)
    rgb_float[halo] = rgb_float[halo] * 0.55 + halo_color * 0.45
    rgb_float[rivers] = river_color
    return rgb_float


def _apply_province_borders(rgb: np.ndarray, provinces: ProvinceMap, color: tuple[int, int, int], alpha: float) -> np.ndarray:
    ids = provinces.province_id_grid
    borders = np.zeros(ids.shape, dtype=bool)
    borders[1:, :] |= (ids[1:, :] != ids[:-1, :]) & (ids[1:, :] != -1) & (ids[:-1, :] != -1)
    borders[:, 1:] |= (ids[:, 1:] != ids[:, :-1]) & (ids[:, 1:] != -1) & (ids[:, :-1] != -1)

    border_color = np.array(color, dtype=np.float32)
    rgb_float = rgb.astype(np.float32)
    rgb_float[borders] = rgb_float[borders] * (1.0 - alpha) + border_color * alpha
    return rgb_float


def _apply_landmass_borders(rgb: np.ndarray, geography: GeographyResult, color: tuple[int, int, int]) -> np.ndarray:
    ids = geography.landmass_id
    borders = np.zeros(ids.shape, dtype=bool)
    borders[1:, :] |= (ids[1:, :] != ids[:-1, :]) & (ids[1:, :] != -1) & (ids[:-1, :] != -1)
    borders[:, 1:] |= (ids[:, 1:] != ids[:, :-1]) & (ids[:, 1:] != -1) & (ids[:, :-1] != -1)
    rgb[borders] = color
    return rgb


def _tint_province(rgb: np.ndarray, provinces: ProvinceMap, province_id: int, tint: tuple[int, int, int], alpha: float) -> np.ndarray:
    mask = provinces.province_id_grid == province_id
    if not mask.any():
        return rgb
    tint_array = np.array(tint, dtype=np.float32)
    rgb_float = rgb.astype(np.float32)
    rgb_float[mask] = rgb_float[mask] * (1.0 - alpha) + tint_array * alpha
    return rgb_float


def _apply_vignette(rgb: np.ndarray) -> np.ndarray:
    """Mild radial darkening at the corners. Helps the map read as a framed
    artifact rather than a screenshot."""
    height, width, _ = rgb.shape
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xs / max(width - 1, 1)) * 2.0 - 1.0
    ny = (ys / max(height - 1, 1)) * 2.0 - 1.0
    radius = np.sqrt(nx * nx + ny * ny)
    falloff = 1.0 - np.clip((radius - 0.85) * 0.45, 0.0, 0.18)
    return rgb * falloff[..., None]


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _box_blur(field: np.ndarray, radius: int = 1) -> np.ndarray:
    """Cheap separable box blur. Used to smooth elevation before hillshading
    so the shading reflects broad terrain rather than per-pixel noise."""
    if radius <= 0:
        return field
    blurred = field.astype(np.float32)
    for _ in range(radius):
        accum = blurred.copy()
        accum[1:, :] += blurred[:-1, :]
        accum[:-1, :] += blurred[1:, :]
        accum[:, 1:] += blurred[:, :-1]
        accum[:, :-1] += blurred[:, 1:]
        blurred = accum / 5.0
    return blurred


import math  # noqa: E402

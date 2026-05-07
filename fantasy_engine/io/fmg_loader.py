"""Loader for Azgaar's Fantasy Map Generator (FMG) ``.map`` files.

Format reference: ``public/modules/io/save.js`` and ``public/modules/io/load.js``
in the FMG repository. The format is 40 ``\\r\\n``-delimited lines, optionally
gzip-compressed. Each line is one of:

    * ``|``-delimited fields            (params, settings, biomes)
    * comma-separated integer array     (per-cell arrays: heights, biomes, ...)
    * JSON                              (provinces, cultures, states, rivers, ...)
    * raw SVG                           (line 5)

We don't try to round-trip the format. We extract the simulation-relevant
parts — cell geometry, provinces, cultures, religions, states, burgs, rivers
— into clean Python dataclasses. Everything else (notes, fonts, markers,
routes, zones, ice, the embedded SVG) is preserved on the World object as
``raw_lines`` so callers that need it can dig in, but the simulation layer
shouldn't have to think about any of that.

Two design choices worth flagging:

1. We tolerate FMG's "index 0 is null" convention. In FMG, ``provinces[0]``,
   ``cultures[0]``, ``states[0]`` are placeholder zero-objects representing
   "no province", "neutral land", etc. We keep them in the parsed data so
   indices stay aligned with FMG's per-cell arrays — the per-cell
   ``province_of_cell[i]`` value of ``0`` really means "this cell has no
   province" and matches ``provinces[0]``. Callers that want to iterate
   only "real" provinces should filter on ``province.id > 0``.

2. We do not load FMG's grid (the unpacked Voronoi grid). FMG keeps two
   parallel cell arrays — ``grid`` (raw Voronoi) and ``pack`` (re-indexed,
   with water cells deduplicated). The simulation only ever wants ``pack``,
   so that's all we expose.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Index of each section within the 40-line .map payload. Names match FMG's
# `pack.*` and `grid.cells.*` paths so the mapping back to the source is obvious.
class _Idx:
    PARAMS = 0
    SETTINGS = 1
    COORDS = 2
    BIOMES = 3
    NOTES = 4
    SVG = 5
    GRID_GENERAL = 6
    GRID_HEIGHTS = 7
    GRID_PRECIPITATION = 8
    GRID_FEATURES = 9
    GRID_TYPE = 10
    GRID_TEMPERATURE = 11
    PACK_FEATURES = 12
    CULTURES = 13
    STATES = 14
    BURGS = 15
    CELL_BIOME = 16
    CELL_BURG = 17
    CELL_CONFLUX = 18
    CELL_CULTURE = 19
    CELL_FLOW = 20
    CELL_POP = 21
    CELL_RIVER = 22
    # 23 deprecated (road)
    CELL_SCORE = 24
    CELL_STATE = 25
    CELL_RELIGION = 26
    CELL_PROVINCE = 27
    # 28 deprecated (crossroad)
    RELIGIONS = 29
    PROVINCES = 30
    NAMES_DATA = 31
    RIVERS = 32
    RULERS = 33
    FONTS = 34
    MARKERS = 35
    CELL_ROUTES = 36
    ROUTES = 37
    ZONES = 38
    ICE = 39


# --------------------------------------------------------------------------- #
#  Domain objects                                                             #
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Biome:
    """One row of FMG's biome table (17 biomes by default).

    The same biome list is shared across all FMG-generated maps unless the
    user customised it in the editor. Cells reference biomes by index via
    :attr:`World.cell_biome`."""
    id: int
    name: str
    color: str             # hex, e.g. "#9bbc8d"
    habitability: int      # 0..100
    cost: int              # movement cost — useful for any pathfinding the sim does


@dataclass(slots=True)
class Culture:
    id: int
    name: str
    color: str
    type: str = ""         # "Generic", "Highland", "Naval", "Nomadic", "Hunting", "Lake", "River"
    base: int = 0          # name base index — which name list this culture uses
    expansionism: float = 1.0
    center: int = 0        # capital cell index
    is_removed: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Religion:
    id: int
    name: str
    color: str = ""
    type: str = ""         # "Folk", "Organized", "Cult", "Heresy"
    form: str = ""         # "Polytheism", "Monotheism", "Animism", "Dualism", ...
    deity: str = ""
    culture: int = 0
    center: int = 0
    expansionism: float = 1.0
    is_removed: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class State:
    """A country / political entity. FMG state[0] is "neutral land"."""
    id: int
    name: str
    color: str = ""
    full_name: str = ""
    form: str = ""         # "Monarchy", "Republic", "Theocracy", ...
    capital: int = 0       # burg id
    culture: int = 0
    center: int = 0        # cell index of state's center
    type: str = ""
    expansionism: float = 1.0
    is_removed: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Burg:
    """A settlement — town, city, capital. FMG burgs[0] is the null sentinel."""
    id: int
    name: str
    cell: int = 0
    x: float = 0.0
    y: float = 0.0
    state: int = 0
    culture: int = 0
    feature: int = 0       # which packFeature (continent/lake) it sits on
    population: float = 0.0
    is_capital: bool = False
    is_port: bool = False
    is_removed: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Province:
    id: int
    name: str
    full_name: str = ""
    color: str = ""
    state: int = 0
    burg: int = 0          # capital burg id (0 if none)
    center: int = 0        # representative cell index
    form_name: str = ""    # "Duchy", "County", "March", ...
    is_removed: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class River:
    id: int
    name: str = ""
    type: str = ""
    parent: int = 0
    source: int = 0        # cell index
    mouth: int = 0         # cell index
    discharge: float = 0.0
    length: float = 0.0
    width: float = 0.0
    cells: list[int] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class World:
    """Parsed FMG world. The simulation should only need this.

    FMG keeps **two** cell graphs in every world:

    * ``pack`` — the simulation-facing cells. Deep ocean is dropped, coastal
      cells are subdivided. All sociopolitical data lives here: biome, state,
      culture, province, religion, burg, river. Pack arrays are prefixed
      ``cell_`` below.
    * ``grid`` — the raw Voronoi grid before reGraph(). Terrain data lives
      here: height, temperature, precipitation. Grid arrays are prefixed
      ``grid_`` below.

    The two arrays are NOT the same length and NOT cross-indexable without
    FMG's pack→grid mapping (``pack.cells.g``), which isn't saved in the
    .map file — FMG reconstructs it by re-running reGraph() at load time.
    For most simulation purposes, biome already encodes the climate
    information you'd otherwise read from grid temperature/precipitation, so
    this isn't usually a problem in practice.

    Index 0 in the lookup tables (provinces, states, cultures, religions,
    burgs) is FMG's "no/null" sentinel. Per-cell arrays use ``0`` to mean
    "this cell has no province/state/etc." — which lines up with the
    sentinel correctly. Filter on ``id > 0`` when iterating real entities.
    """
    fmg_version: str
    seed: str
    width: int
    height: int

    biomes: list[Biome]
    cultures: list[Culture]
    religions: list[Religion]
    states: list[State]
    burgs: list[Burg]
    provinces: list[Province]
    rivers: list[River]

    # Pack-level per-cell arrays. All same length (number of pack cells).
    # These are what the simulation should read.
    cell_biome: list[int]
    cell_burg: list[int]
    cell_culture: list[int]
    cell_state: list[int]
    cell_religion: list[int]
    cell_province: list[int]
    cell_river: list[int]
    cell_population: list[float]
    cell_flow: list[int]

    # Grid-level per-cell arrays. Same length as each other (number of grid
    # cells), but DIFFERENT length from the pack arrays above. Don't index
    # these with a pack cell ID — they won't line up.
    grid_height: list[int]          # 0..100, sea level is 20 by FMG convention
    grid_temperature: list[int]     # signed (°C)
    grid_precipitation: list[int]   # 0..255

    # Stash unparsed lines so callers that want SVG, notes, routes, etc.
    # can grab them without re-reading the file.
    raw_lines: list[str] = field(repr=False, default_factory=list)

    @property
    def n_pack_cells(self) -> int:
        return len(self.cell_biome)

    @property
    def n_grid_cells(self) -> int:
        return len(self.grid_height)


# --------------------------------------------------------------------------- #
#  Parsing                                                                    #
# --------------------------------------------------------------------------- #


def load_fmg_map(path: str | Path) -> World:
    """Load and parse an FMG ``.map`` file from disk.

    Handles both plain-text and gzip-compressed .map files (FMG started
    gzipping by default in v1.95+; older saves are plain text)."""
    raw_bytes = Path(path).read_bytes()
    text = _decode(raw_bytes)
    return parse_fmg_text(text)


def parse_fmg_text(text: str) -> World:
    """Parse a .map payload that's already been read into a string.

    Useful for tests, in-memory pipelines, and HTTP upload handlers that
    don't want to touch disk."""
    lines = text.split("\r\n")
    if len(lines) < 33:
        raise ValueError(
            f"FMG .map file truncated: expected at least 33 lines, found {len(lines)}. "
            "The file may be corrupt or not actually a .map file."
        )

    params = lines[_Idx.PARAMS].split("|")
    fmg_version = params[0] if len(params) > 0 else "?"
    seed = params[3] if len(params) > 3 else ""
    width = _safe_int(params[4]) if len(params) > 4 else 0
    height = _safe_int(params[5]) if len(params) > 5 else 0

    biomes = _parse_biomes(lines[_Idx.BIOMES])
    cultures = _parse_cultures(_safe_json(lines[_Idx.CULTURES], default=[]))
    religions = _parse_religions(_safe_json(lines[_Idx.RELIGIONS], default=[]))
    states = _parse_states(_safe_json(lines[_Idx.STATES], default=[]))
    burgs = _parse_burgs(_safe_json(lines[_Idx.BURGS], default=[]))
    provinces = _parse_provinces(_safe_json(lines[_Idx.PROVINCES], default=[]))
    rivers = _parse_rivers(_safe_json(lines[_Idx.RIVERS], default=[]))

    return World(
        fmg_version=fmg_version,
        seed=seed,
        width=width,
        height=height,
        biomes=biomes,
        cultures=cultures,
        religions=religions,
        states=states,
        burgs=burgs,
        provinces=provinces,
        rivers=rivers,
        cell_biome=_parse_int_array(lines[_Idx.CELL_BIOME]),
        cell_burg=_parse_int_array(lines[_Idx.CELL_BURG]),
        cell_culture=_parse_int_array(lines[_Idx.CELL_CULTURE]),
        cell_state=_parse_int_array(lines[_Idx.CELL_STATE]),
        cell_religion=_parse_int_array(lines[_Idx.CELL_RELIGION]),
        cell_province=_parse_int_array(lines[_Idx.CELL_PROVINCE]),
        cell_river=_parse_int_array(lines[_Idx.CELL_RIVER]),
        cell_population=_parse_float_array(lines[_Idx.CELL_POP]),
        cell_flow=_parse_int_array(lines[_Idx.CELL_FLOW]),
        grid_height=_parse_int_array(lines[_Idx.GRID_HEIGHTS]),
        grid_temperature=_parse_int_array(lines[_Idx.GRID_TEMPERATURE]),
        grid_precipitation=_parse_int_array(lines[_Idx.GRID_PRECIPITATION]),
        raw_lines=lines,
    )


# --------------------------------------------------------------------------- #
#  Section parsers                                                            #
# --------------------------------------------------------------------------- #


def _parse_biomes(line: str) -> list[Biome]:
    """FMG saves biomes as three pipe-separated CSV sections:
    ``colors_csv | habitability_csv | names_csv`` (see ``save.js``:
    ``[biomesData.color, biomesData.habitability, biomesData.name].join('|')``).

    Cost isn't saved — FMG looks it up from the in-code biome table at
    runtime — so we leave it at a default of 10. Callers that need the real
    cost values can ship FMG's ``biome.json`` alongside the .map file."""
    if not line:
        return []
    sections = line.split("|")
    if len(sections) < 3:
        # Older format or corrupted file — degrade gracefully.
        return []
    colors = sections[0].split(",")
    habitability = [_safe_int(v) for v in sections[1].split(",")]
    names = sections[2].split(",")
    n = min(len(colors), len(habitability), len(names))
    return [
        Biome(id=i, name=names[i], color=colors[i],
              habitability=habitability[i], cost=10)
        for i in range(n)
    ]


def _parse_cultures(items: list) -> list[Culture]:
    out: list[Culture] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            out.append(Culture(id=idx, name="", is_removed=True))
            continue
        out.append(Culture(
            id=int(item.get("i", idx)),
            name=str(item.get("name", f"Culture #{idx}")),
            color=str(item.get("color", "")),
            type=str(item.get("type", "")),
            base=int(item.get("base", 0)),
            expansionism=float(item.get("expansionism", 1.0)),
            center=int(item.get("center", 0)),
            is_removed=bool(item.get("removed", False)),
            extras=_extras(item, {"i", "name", "color", "type", "base", "expansionism", "center", "removed"}),
        ))
    return out


def _parse_religions(items: list) -> list[Religion]:
    out: list[Religion] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            out.append(Religion(id=idx, name="", is_removed=True))
            continue
        out.append(Religion(
            id=int(item.get("i", idx)),
            name=str(item.get("name", f"Religion #{idx}")),
            color=str(item.get("color", "")),
            type=str(item.get("type", "")),
            form=str(item.get("form", "")),
            deity=str(item.get("deity") or ""),
            culture=int(item.get("culture", 0)),
            center=int(item.get("center", 0)),
            expansionism=float(item.get("expansionism", 1.0)),
            is_removed=bool(item.get("removed", False)),
            extras=_extras(item, {"i", "name", "color", "type", "form", "deity", "culture", "center", "expansionism", "removed"}),
        ))
    return out


def _parse_states(items: list) -> list[State]:
    out: list[State] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            out.append(State(id=idx, name="", is_removed=True))
            continue
        out.append(State(
            id=int(item.get("i", idx)),
            name=str(item.get("name", f"State #{idx}")),
            color=str(item.get("color", "")),
            full_name=str(item.get("fullName", "")),
            form=str(item.get("form", "")),
            capital=int(item.get("capital", 0)),
            culture=int(item.get("culture", 0)),
            center=int(item.get("center", 0)),
            type=str(item.get("type", "")),
            expansionism=float(item.get("expansionism", 1.0)),
            is_removed=bool(item.get("removed", False)),
            extras=_extras(item, {"i", "name", "color", "fullName", "form", "capital", "culture", "center", "type", "expansionism", "removed"}),
        ))
    return out


def _parse_burgs(items: list) -> list[Burg]:
    out: list[Burg] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            out.append(Burg(id=idx, name="", is_removed=True))
            continue
        out.append(Burg(
            id=int(item.get("i", idx)),
            name=str(item.get("name", f"Burg #{idx}")),
            cell=int(item.get("cell", 0)),
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            state=int(item.get("state", 0)),
            culture=int(item.get("culture", 0)),
            feature=int(item.get("feature", 0)),
            population=float(item.get("population", 0.0)),
            is_capital=bool(item.get("capital", False)),
            is_port=bool(item.get("port", False)),
            is_removed=bool(item.get("removed", False)),
            extras=_extras(item, {"i", "name", "cell", "x", "y", "state", "culture", "feature", "population", "capital", "port", "removed"}),
        ))
    return out


def _parse_rivers(items: list) -> list[River]:
    out: list[River] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue  # rivers don't use a sentinel — skip stray non-dicts
        out.append(River(
            id=int(item.get("i", idx)),
            name=str(item.get("name", "")),
            type=str(item.get("type", "")),
            parent=int(item.get("parent", 0)),
            source=int(item.get("source", 0)),
            mouth=int(item.get("mouth", 0)),
            discharge=float(item.get("discharge", 0.0)),
            length=float(item.get("length", 0.0)),
            width=float(item.get("width", 0.0)),
            cells=list(item.get("cells", [])),
            extras=_extras(item, {"i", "name", "type", "parent", "source", "mouth", "discharge", "length", "width", "cells"}),
        ))
    return out


def _parse_provinces(items: list) -> list[Province]:
    """Provinces are sparse: index 0 is always 0 (sentinel). Other entries can
    be 0 too (deleted provinces). We still keep the slot so indices line up."""
    out: list[Province] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            # FMG uses 0 as a placeholder for "no province at this slot".
            out.append(Province(id=idx, name="", is_removed=True))
            continue
        out.append(Province(
            id=int(item.get("i", idx)),
            name=str(item.get("name", f"Province #{idx}")),
            full_name=str(item.get("fullName", "")),
            color=str(item.get("color", "")),
            state=int(item.get("state", 0)),
            burg=int(item.get("burg", 0)),
            center=int(item.get("center", 0)),
            form_name=str(item.get("formName", "")),
            is_removed=bool(item.get("removed", False)),
            extras=_extras(item, {"i", "name", "fullName", "color", "state", "burg", "center", "formName", "removed"}),
        ))
    return out


# --------------------------------------------------------------------------- #
#  Helpers                                                                    #
# --------------------------------------------------------------------------- #


def _decode(raw: bytes) -> str:
    """FMG saves are sometimes gzip-compressed. The magic bytes for gzip are
    0x1f 0x8b. We try gzip first; if it doesn't have the magic bytes we
    fall back to plain UTF-8."""
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        return gzip.decompress(raw).decode("utf-8")
    return raw.decode("utf-8")


def _safe_int(value: str | int | None) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_json(line: str, default):
    if not line:
        return default
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return default


def _parse_int_array(line: str) -> list[int]:
    if not line:
        return []
    return [_safe_int(v) for v in line.split(",")]


def _parse_float_array(line: str) -> list[float]:
    if not line:
        return []
    out: list[float] = []
    for v in line.split(","):
        try:
            out.append(float(v) if v else 0.0)
        except ValueError:
            out.append(0.0)
    return out


def _extras(item: dict, claimed_keys: set[str]) -> dict[str, Any]:
    """Pull any keys we didn't explicitly model into ``extras`` so callers
    that want FMG-specific fields can still get at them."""
    return {k: v for k, v in item.items() if k not in claimed_keys}

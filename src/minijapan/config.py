from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Tuple

import yaml

from .errors import ConfigurationError
from .models import (
    CompressionConfig,
    FacadeSpec,
    MaterialSlot,
    OutputConfig,
    ProjectConfig,
    StationNode,
    TransitRoute,
    WorldBounds,
    WorldOrigin,
    ensure_mapping,
    ensure_sequence,
)


def _required(mapping: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise ConfigurationError(f"{path}.{key}: missing required field")
    return mapping[key]


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{path}: expected a non-empty string")
    return value.strip()


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{path}: expected a number")
    return float(value)


def _integer(value: Any, path: str) -> int:
    number = _number(value, path)
    if number != int(number):
        raise ConfigurationError(f"{path}: expected an integer")
    return int(number)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    try:
        return ensure_mapping(value, path)
    except ValueError as error:
        raise ConfigurationError(str(error)) from error


def _list(value: Any, path: str) -> Tuple[Any, ...]:
    try:
        return tuple(ensure_sequence(value, path))
    except ValueError as error:
        raise ConfigurationError(str(error)) from error


def load_config(path: Path) -> ProjectConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(f"config: file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"config: invalid YAML: {error}") from error

    root = _mapping(raw, "config")
    schema_version = _string(_required(root, "schema_version", "config"), "config.schema_version")
    project = _string(_required(root, "project", "config"), "config.project")
    seed = _integer(_required(root, "seed", "config"), "config.seed")
    mode = _string(_required(root, "mode", "config"), "config.mode")

    world = _mapping(_required(root, "world", "config"), "config.world")
    world_name = _string(_required(world, "name", "config.world"), "config.world.name")
    origin_raw = _mapping(_required(world, "origin", "config.world"), "config.world.origin")
    origin = WorldOrigin(
        x=_integer(_required(origin_raw, "x", "config.world.origin"), "config.world.origin.x"),
        y=_integer(_required(origin_raw, "y", "config.world.origin"), "config.world.origin.y"),
        z=_integer(_required(origin_raw, "z", "config.world.origin"), "config.world.origin.z"),
    )
    bounds_raw = _mapping(_required(world, "bounds", "config.world"), "config.world.bounds")
    bounds = WorldBounds(
        min_x=_integer(
            _required(bounds_raw, "min_x", "config.world.bounds"), "config.world.bounds.min_x"
        ),
        max_x=_integer(
            _required(bounds_raw, "max_x", "config.world.bounds"), "config.world.bounds.max_x"
        ),
        min_z=_integer(
            _required(bounds_raw, "min_z", "config.world.bounds"), "config.world.bounds.min_z"
        ),
        max_z=_integer(
            _required(bounds_raw, "max_z", "config.world.bounds"), "config.world.bounds.max_z"
        ),
    )

    compression_raw = _mapping(_required(root, "compression", "config"), "config.compression")
    compression = CompressionConfig(
        minimum_station_spacing_blocks=_number(
            _required(compression_raw, "minimum_station_spacing_blocks", "config.compression"),
            "config.compression.minimum_station_spacing_blocks",
        ),
        preserve_cardinal_directions=bool(
            compression_raw.get("preserve_cardinal_directions", True)
        ),
        protect_landmark_envelopes=bool(compression_raw.get("protect_landmark_envelopes", True)),
        factor=_number(compression_raw.get("factor", 0.85), "config.compression.factor"),
    )

    station_values = _list(_required(root, "stations", "config"), "config.stations")
    stations = []
    for index, value in enumerate(station_values):
        station_path = f"config.stations[{index}]"
        station = _mapping(value, station_path)
        modes_value = station.get("modes", ["rail"])
        modes = tuple(
            _string(mode_value, f"{station_path}.modes[{mode_index}]")
            for mode_index, mode_value in enumerate(_list(modes_value, f"{station_path}.modes"))
        )
        stations.append(
            StationNode(
                id=_string(_required(station, "id", station_path), f"{station_path}.id"),
                name_ja=_string(
                    _required(station, "name_ja", station_path), f"{station_path}.name_ja"
                ),
                x_hint=_number(
                    _required(station, "x_hint", station_path), f"{station_path}.x_hint"
                ),
                z_hint=_number(
                    _required(station, "z_hint", station_path), f"{station_path}.z_hint"
                ),
                role=_string(_required(station, "role", station_path), f"{station_path}.role"),
                name_en=str(station.get("name_en", "")).strip(),
                modes=modes,
            )
        )

    route_values = _list(_required(root, "routes", "config"), "config.routes")
    routes = []
    for index, value in enumerate(route_values):
        route_path = f"config.routes[{index}]"
        route = _mapping(value, route_path)
        station_ids = tuple(
            _string(station_id, f"{route_path}.station_ids[{station_index}]")
            for station_index, station_id in enumerate(
                _list(_required(route, "station_ids", route_path), f"{route_path}.station_ids")
            )
        )
        routes.append(
            TransitRoute(
                id=_string(_required(route, "id", route_path), f"{route_path}.id"),
                name=_string(_required(route, "name", route_path), f"{route_path}.name"),
                station_ids=station_ids,
                demo_only=bool(route.get("demo_only", True)),
            )
        )

    materials_raw = _mapping(root.get("materials", {}), "config.materials")
    material_profile = _string(
        materials_raw.get("profile", "vanilla_safe"), "config.materials.profile"
    )
    material_slots_raw = _mapping(materials_raw.get("slots", {}), "config.materials.slots")
    material_slots = []
    for slot_id, value in material_slots_raw.items():
        slot_path = f"config.materials.slots.{slot_id}"
        slot = _mapping(value, slot_path)
        preferred = tuple(
            _string(block_id, f"{slot_path}.preferred[{index}]")
            for index, block_id in enumerate(
                _list(slot.get("preferred", []), f"{slot_path}.preferred")
            )
        )
        fallback = _string(_required(slot, "fallback", slot_path), f"{slot_path}.fallback")
        material_slots.append(
            MaterialSlot(id=_string(slot_id, slot_path), preferred=preferred, fallback=fallback)
        )

    facade_values = _list(root.get("facades", []), "config.facades")
    facades = []
    for index, value in enumerate(facade_values):
        facade_path = f"config.facades[{index}]"
        facade = _mapping(value, facade_path)
        offset = _mapping(facade.get("offset", {"x": 0, "z": 0}), f"{facade_path}.offset")
        facades.append(
            FacadeSpec(
                id=_string(_required(facade, "id", facade_path), f"{facade_path}.id"),
                anchor_station_id=_string(
                    _required(facade, "anchor_station_id", facade_path),
                    f"{facade_path}.anchor_station_id",
                ),
                offset_x=_integer(offset.get("x", 0), f"{facade_path}.offset.x"),
                offset_z=_integer(offset.get("z", 0), f"{facade_path}.offset.z"),
                width=_integer(_required(facade, "width", facade_path), f"{facade_path}.width"),
                depth=_integer(_required(facade, "depth", facade_path), f"{facade_path}.depth"),
                floors=_integer(_required(facade, "floors", facade_path), f"{facade_path}.floors"),
                style_id=_string(
                    _required(facade, "style_id", facade_path), f"{facade_path}.style_id"
                ),
                storefront_count=_integer(
                    facade.get("storefront_count", 1), f"{facade_path}.storefront_count"
                ),
                windows_per_floor=_integer(
                    facade.get("windows_per_floor", 2), f"{facade_path}.windows_per_floor"
                ),
            )
        )

    output_raw = _mapping(root.get("output", {}), "config.output")
    output = OutputConfig(
        preview_format=str(output_raw.get("preview_format", "svg")),
        json_indent=_integer(output_raw.get("json_indent", 2), "config.output.json_indent"),
    )

    config = ProjectConfig(
        schema_version=schema_version,
        project=project,
        seed=seed,
        mode=mode,
        world_name=world_name,
        origin=origin,
        bounds=bounds,
        compression=compression,
        stations=tuple(stations),
        routes=tuple(routes),
        material_profile=material_profile,
        material_slots=tuple(material_slots),
        facades=tuple(facades),
        output=output,
    )
    issues = validate_config(config)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        details = "; ".join(f"{issue.path}: {issue.message}" for issue in errors)
        raise ConfigurationError(details)
    return config


def validate_config(config: ProjectConfig):
    from .validation import validate_config_model

    return validate_config_model(config)

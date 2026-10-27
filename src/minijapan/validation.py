from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import combinations
from typing import List

from .materials import is_block_id
from .models import (
    ProjectConfig,
    ValidationIssue,
    WorldBounds,
    WorldPlacement,
)


def validate_config_model(config: ProjectConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if config.schema_version != "1.0.0":
        issues.append(
            ValidationIssue(
                "unsupported_schema", "/schema_version", "only schema_version 1.0.0 is supported"
            )
        )
    bounds = config.bounds
    if bounds.min_x >= bounds.max_x or bounds.min_z >= bounds.max_z:
        issues.append(
            ValidationIssue(
                "invalid_world_bounds",
                "/world/bounds",
                "minimum bounds must be less than maximum bounds",
            )
        )
    if config.compression.minimum_station_spacing_blocks <= 0:
        issues.append(
            ValidationIssue(
                "invalid_spacing",
                "/compression/minimum_station_spacing_blocks",
                "must be greater than zero",
            )
        )
    if config.compression.factor <= 0:
        issues.append(
            ValidationIssue(
                "invalid_compression_factor", "/compression/factor", "must be greater than zero"
            )
        )
    if not config.stations:
        issues.append(
            ValidationIssue("empty_stations", "/stations", "at least one station is required")
        )
    if not config.routes:
        issues.append(ValidationIssue("empty_routes", "/routes", "at least one route is required"))

    material_slot_ids = set()
    for slot_index, slot in enumerate(config.material_slots):
        path = f"/materials/slots/{slot_index}"
        if slot.id in material_slot_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_material_slot", f"{path}/id", f"duplicate material slot: {slot.id}"
                )
            )
        material_slot_ids.add(slot.id)
        for block_id in (*slot.preferred, slot.fallback):
            if not is_block_id(block_id):
                issues.append(
                    ValidationIssue(
                        "invalid_block_id", path, f"invalid namespaced block id: {block_id}"
                    )
                )
        if not slot.preferred and not slot.fallback:
            issues.append(
                ValidationIssue(
                    "empty_material_slot",
                    path,
                    "a material slot needs a preferred block or fallback",
                )
            )

    station_ids = set()
    for index, station in enumerate(config.stations):
        path = f"/stations/{index}"
        if station.id in station_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_station_id", f"{path}/id", f"duplicate station id: {station.id}"
                )
            )
        station_ids.add(station.id)
        if not math.isfinite(station.x_hint) or not math.isfinite(station.z_hint):
            issues.append(
                ValidationIssue(
                    "invalid_coordinate", path, "x_hint and z_hint must be finite numbers"
                )
            )
        if not station.modes:
            issues.append(
                ValidationIssue("empty_modes", f"{path}/modes", "at least one mode is required")
            )

    route_ids = set()
    for index, route in enumerate(config.routes):
        path = f"/routes/{index}"
        if route.id in route_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_route_id", f"{path}/id", f"duplicate route id: {route.id}"
                )
            )
        route_ids.add(route.id)
        if len(route.station_ids) < 2:
            issues.append(
                ValidationIssue(
                    "route_too_short", f"{path}/station_ids", "a route needs at least two stations"
                )
            )
        if len(set(route.station_ids)) != len(route.station_ids):
            issues.append(
                ValidationIssue(
                    "route_repeated_station",
                    f"{path}/station_ids",
                    "a route cannot repeat a station",
                )
            )
        for station_index, station_id in enumerate(route.station_ids):
            if station_id not in station_ids:
                issues.append(
                    ValidationIssue(
                        "missing_station_reference",
                        f"{path}/station_ids/{station_index}",
                        f"unknown station id: {station_id}",
                    )
                )

    if config.output.preview_format.lower() != "svg":
        issues.append(
            ValidationIssue(
                "unsupported_preview_format",
                "/output/preview_format",
                "MVP currently supports only svg",
            )
        )
    if config.output.json_indent < 0 or config.output.json_indent > 8:
        issues.append(
            ValidationIssue("invalid_json_indent", "/output/json_indent", "must be between 0 and 8")
        )

    facade_ids = set()
    for index, facade in enumerate(config.facades):
        path = f"/facades/{index}"
        if facade.id in facade_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_facade_id", f"{path}/id", f"duplicate facade id: {facade.id}"
                )
            )
        facade_ids.add(facade.id)
        if facade.anchor_station_id not in station_ids:
            issues.append(
                ValidationIssue(
                    "missing_facade_anchor",
                    f"{path}/anchor_station_id",
                    f"unknown station id: {facade.anchor_station_id}",
                )
            )
        if facade.width <= 0 or facade.depth <= 0 or facade.floors <= 0:
            issues.append(
                ValidationIssue(
                    "invalid_facade_size",
                    path,
                    "facade width, depth and floors must be greater than zero",
                )
            )
        if facade.storefront_count <= 0 or facade.storefront_count > facade.width:
            issues.append(
                ValidationIssue(
                    "invalid_storefront_count",
                    f"{path}/storefront_count",
                    "storefront_count must be between 1 and facade width",
                )
            )
        if facade.windows_per_floor < 0:
            issues.append(
                ValidationIssue(
                    "invalid_window_count",
                    f"{path}/windows_per_floor",
                    "windows_per_floor cannot be negative",
                )
            )
    return issues


def validate_placements(
    placements: Mapping[str, WorldPlacement],
    bounds: WorldBounds,
    minimum_spacing: float,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for station_id, placement in placements.items():
        if not bounds.contains(placement.x, placement.z):
            issues.append(
                ValidationIssue(
                    "layout_out_of_bounds",
                    f"/stations/{station_id}",
                    "station placement is outside world bounds",
                )
            )
    for left, right in combinations(sorted(placements), 2):
        first = placements[left]
        second = placements[right]
        distance = math.hypot(first.x - second.x, first.z - second.z)
        if distance < minimum_spacing:
            issues.append(
                ValidationIssue(
                    "station_spacing",
                    f"/stations/{left}",
                    f"distance to {right} is {distance:.2f}, below minimum {minimum_spacing:.2f}",
                )
            )
    return issues


def validate_facade_placements(
    config: ProjectConfig, placements: Mapping[str, WorldPlacement]
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    bounds = WorldBounds(
        min_x=config.bounds.min_x + config.origin.x,
        max_x=config.bounds.max_x + config.origin.x,
        min_z=config.bounds.min_z + config.origin.z,
        max_z=config.bounds.max_z + config.origin.z,
    )
    for facade in config.facades:
        anchor = placements.get(facade.anchor_station_id)
        if anchor is None:
            continue
        x = anchor.x + facade.offset_x
        z = anchor.z + facade.offset_z
        if not bounds.contains(x, z) or not bounds.contains(
            x + facade.width - 1, z + facade.depth - 1
        ):
            issues.append(
                ValidationIssue(
                    "facade_out_of_bounds",
                    f"/facades/{facade.id}",
                    "facade footprint is outside world bounds",
                )
            )
    return issues


def validate_plan_shape(plan: Mapping[str, object]) -> List[ValidationIssue]:
    required = (
        "schema_version",
        "plan_id",
        "source",
        "target",
        "regions",
        "materials",
        "stations",
        "rails",
        "routes",
        "execution",
    )
    issues: List[ValidationIssue] = []
    for key in required:
        if key not in plan:
            issues.append(
                ValidationIssue(
                    "missing_plan_field", f"/{key}", f"required plan field is missing: {key}"
                )
            )
    if plan.get("schema_version") != "1.0.0":
        issues.append(
            ValidationIssue("invalid_plan_schema", "/schema_version", "plan schema must be 1.0.0")
        )
    if not isinstance(plan.get("stations"), list):
        issues.append(
            ValidationIssue("invalid_plan_stations", "/stations", "stations must be an array")
        )
    if not isinstance(plan.get("routes"), list):
        issues.append(ValidationIssue("invalid_plan_routes", "/routes", "routes must be an array"))
    station_ids = [item.get("id") for item in plan.get("stations", []) if isinstance(item, dict)]
    if len(station_ids) != len(set(station_ids)):
        issues.append(
            ValidationIssue(
                "duplicate_plan_station_id", "/stations", "plan station ids must be unique"
            )
        )
    return issues

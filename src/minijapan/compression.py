from __future__ import annotations

import math
from typing import Dict, List

from .models import LayoutResult, ProjectConfig, WorldPlacement
from .validation import validate_placements


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _scaled_hints(config: ProjectConfig) -> Dict[str, List[float]]:
    factor = config.compression.factor
    positions = {
        station.id: [station.x_hint * factor, station.z_hint * factor]
        for station in config.stations
    }
    margin = max(1.0, config.compression.minimum_station_spacing_blocks / 2.0)
    max_abs_x = max((abs(position[0]) for position in positions.values()), default=0.0)
    max_abs_z = max((abs(position[1]) for position in positions.values()), default=0.0)
    available_x = max(abs(config.bounds.min_x), abs(config.bounds.max_x)) - margin
    available_z = max(abs(config.bounds.min_z), abs(config.bounds.max_z)) - margin
    if max_abs_x > available_x or max_abs_z > available_z:
        scale_x = available_x / max_abs_x if max_abs_x else 1.0
        scale_z = available_z / max_abs_z if max_abs_z else 1.0
        scale = min(scale_x, scale_z)
        for position in positions.values():
            position[0] *= scale
            position[1] *= scale
    return positions


def compress_layout(config: ProjectConfig) -> LayoutResult:
    """Create a deterministic, hint-preserving layout with hard spacing and bounds checks."""
    positions = _scaled_hints(config)
    ordered_ids = [station.id for station in config.stations]
    minimum = config.compression.minimum_station_spacing_blocks
    min_x, max_x = config.bounds.min_x, config.bounds.max_x
    min_z, max_z = config.bounds.min_z, config.bounds.max_z

    for _ in range(256):
        changed = False
        for left_index, left_id in enumerate(ordered_ids):
            for right_id in ordered_ids[left_index + 1 :]:
                left = positions[left_id]
                right = positions[right_id]
                dx = right[0] - left[0]
                dz = right[1] - left[1]
                distance = math.hypot(dx, dz)
                if distance >= minimum:
                    continue
                if distance == 0:
                    angle = ((left_index + 1) * 0.61803398875) % (2 * math.pi)
                    dx, dz = math.cos(angle), math.sin(angle)
                    distance = 1.0
                correction = (minimum - distance) / 2.0
                ux, uz = dx / distance, dz / distance
                left[0] -= ux * correction
                left[1] -= uz * correction
                right[0] += ux * correction
                right[1] += uz * correction
                changed = True
        for position in positions.values():
            position[0] = _clamp(position[0], min_x, max_x)
            position[1] = _clamp(position[1], min_z, max_z)
        if not changed:
            break

    placements = {
        station.id: WorldPlacement(
            station_id=station.id,
            x=int(round(positions[station.id][0])) + config.origin.x,
            y=config.origin.y - 10,
            z=int(round(positions[station.id][1])) + config.origin.z,
        )
        for station in config.stations
    }
    # Bounds are expressed in world coordinates relative to the configured origin.
    world_placements = {station_id: placement for station_id, placement in placements.items()}
    shifted_bounds = type(config.bounds)(
        min_x=config.bounds.min_x + config.origin.x,
        max_x=config.bounds.max_x + config.origin.x,
        min_z=config.bounds.min_z + config.origin.z,
        max_z=config.bounds.max_z + config.origin.z,
    )
    issues = validate_placements(world_placements, shifted_bounds, minimum)
    return LayoutResult(placements=placements, issues=issues)

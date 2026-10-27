from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class WorldBounds:
    min_x: int
    max_x: int
    min_z: int
    max_z: int

    def contains(self, x: float, z: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_z <= z <= self.max_z

    def as_dict(self) -> Dict[str, int]:
        return {
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_z": self.min_z,
            "max_z": self.max_z,
        }


@dataclass(frozen=True)
class WorldOrigin:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class StationNode:
    id: str
    name_ja: str
    x_hint: float
    z_hint: float
    role: str
    name_en: str = ""
    modes: Tuple[str, ...] = ("rail",)


@dataclass(frozen=True)
class TransitRoute:
    id: str
    name: str
    station_ids: Tuple[str, ...]
    demo_only: bool = True


@dataclass(frozen=True)
class MaterialSlot:
    id: str
    preferred: Tuple[str, ...]
    fallback: str


@dataclass(frozen=True)
class FacadeSpec:
    id: str
    anchor_station_id: str
    offset_x: int
    offset_z: int
    width: int
    depth: int
    floors: int
    style_id: str
    storefront_count: int = 1
    windows_per_floor: int = 2


@dataclass(frozen=True)
class CompressionConfig:
    minimum_station_spacing_blocks: float
    preserve_cardinal_directions: bool
    protect_landmark_envelopes: bool
    factor: float = 0.85


@dataclass(frozen=True)
class OutputConfig:
    preview_format: str = "svg"
    json_indent: int = 2


@dataclass(frozen=True)
class ProjectConfig:
    schema_version: str
    project: str
    seed: int
    mode: str
    world_name: str
    origin: WorldOrigin
    bounds: WorldBounds
    compression: CompressionConfig
    stations: Tuple[StationNode, ...]
    routes: Tuple[TransitRoute, ...]
    material_profile: str
    material_slots: Tuple[MaterialSlot, ...]
    facades: Tuple[FacadeSpec, ...]
    output: OutputConfig


@dataclass(frozen=True)
class WorldPlacement:
    station_id: str
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"

    def as_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class LayoutResult:
    placements: Dict[str, WorldPlacement]
    issues: List[ValidationIssue] = field(default_factory=list)


def station_to_dict(station: StationNode, placement: WorldPlacement) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": station.id,
        "label_ja": station.name_ja,
        "x": placement.x,
        "y": placement.y,
        "z": placement.z,
        "role": station.role,
        "modes": list(station.modes),
    }
    if station.name_en:
        result["label_en"] = station.name_en
    return result


def route_to_dict(route: TransitRoute) -> Dict[str, Any]:
    return {
        "id": route.id,
        "name": route.name,
        "station_ids": list(route.station_ids),
        "demo_only": route.demo_only,
        "status": "demo_topology" if route.demo_only else "unverified",
        "requires_verified_mtr_adapter": True,
    }


def ensure_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a mapping")
    return value


def ensure_sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{path} must be a list")
    return value

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .compression import compress_layout
from .models import ProjectConfig, TransitRoute, route_to_dict, station_to_dict
from .validation import validate_plan_shape


def _edge_id(route: TransitRoute, index: int) -> str:
    return f"{route.id}__{index:02d}"


def build_plan(config: ProjectConfig) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    layout = compress_layout(config)
    issues = [issue.as_dict() for issue in layout.issues]
    if issues:
        return {}, issues

    stations = [
        station_to_dict(station, layout.placements[station.id]) for station in config.stations
    ]
    routes = [route_to_dict(route) for route in config.routes]
    rails: List[Dict[str, Any]] = []
    for route in config.routes:
        for index, (source_id, target_id) in enumerate(
            zip(route.station_ids, route.station_ids[1:])
        ):
            source = layout.placements[source_id]
            target = layout.placements[target_id]
            rails.append(
                {
                    "id": _edge_id(route, index),
                    "route_id": route.id,
                    "source": source_id,
                    "target": target_id,
                    "geometry": {
                        "points": [
                            {"x": source.x, "y": source.y, "z": source.z},
                            {"x": target.x, "y": target.y, "z": target.z},
                        ]
                    },
                    "length_blocks": round(math.hypot(source.x - target.x, source.z - target.z), 2),
                    "status": "geometry_only_demo",
                }
            )

    plan: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "plan_id": f"{config.project}-{config.seed}",
        "source": {
            "profile": config.project,
            "seed": config.seed,
            "real_data": False,
            "notes": "Synthetic prototype positions; routes are demonstration topology, not a railway timetable or MTR network.",
        },
        "target": {
            "edition": "java",
            "minecraft_version": "1.20.1",
            "loader": "fabric",
            "dimension": "minecraft:overworld",
        },
        "regions": [
            {
                "id": "tokyo_center",
                "origin": {"x": config.origin.x, "y": config.origin.y, "z": config.origin.z},
                "style_id": "tokyo_modern",
                "bounds": {
                    "min_x": config.bounds.min_x + config.origin.x,
                    "max_x": config.bounds.max_x + config.origin.x,
                    "min_z": config.bounds.min_z + config.origin.z,
                    "max_z": config.bounds.max_z + config.origin.z,
                },
            }
        ],
        "stations": stations,
        "rails": rails,
        "routes": routes,
        "structures": [],
        "execution": {
            "mode": "dry_run",
            "overwrite_policy": "air_only",
            "max_changed_blocks_per_job": 100000,
            "requires_player_confirmation": True,
            "mtr_adapter": "unverified_manual_or_mock_only",
        },
    }
    shape_issues = [issue.as_dict() for issue in validate_plan_shape(plan)]
    return plan, shape_issues


def write_plan_outputs(config: ProjectConfig, output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan, issues = build_plan(config)
    if issues:
        validation = {"status": "invalid", "errors": issues, "warnings": []}
        validation_path = output_dir / "validation.json"
        validation_path.write_text(
            json.dumps(validation, ensure_ascii=False, indent=config.output.json_indent) + "\n",
            encoding="utf-8",
        )
        return {"validation": validation_path}

    validation = {
        "status": "valid",
        "errors": [],
        "warnings": [
            {
                "code": "demo_topology",
                "path": "/routes",
                "message": "Routes are synthetic demonstration topology and are not verified MTR routes.",
                "severity": "warning",
            },
            {
                "code": "no_game_write",
                "path": "/execution",
                "message": "This command only writes offline planning artefacts; it does not modify a Minecraft world.",
                "severity": "warning",
            },
        ],
    }
    plan_path = output_dir / "plan.json"
    validation_path = output_dir / "validation.json"
    preview_path = output_dir / "preview.svg"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=config.output.json_indent) + "\n",
        encoding="utf-8",
    )
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=config.output.json_indent) + "\n",
        encoding="utf-8",
    )
    from .preview import render_svg

    preview_path.write_text(render_svg(config, plan), encoding="utf-8")
    return {"plan": plan_path, "validation": validation_path, "preview": preview_path}

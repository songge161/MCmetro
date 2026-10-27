from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any, List, Tuple

from .models import ProjectConfig

WIDTH = 1200
HEIGHT = 820
PADDING = 80


def _project(x: float, z: float, config: ProjectConfig) -> Tuple[float, float]:
    min_x = config.bounds.min_x + config.origin.x
    max_x = config.bounds.max_x + config.origin.x
    min_z = config.bounds.min_z + config.origin.z
    max_z = config.bounds.max_z + config.origin.z
    span_x = max(1, max_x - min_x)
    span_z = max(1, max_z - min_z)
    px = PADDING + (x - min_x) / span_x * (WIDTH - 2 * PADDING)
    py = HEIGHT - PADDING - (z - min_z) / span_z * (HEIGHT - 2 * PADDING)
    return px, py


def render_svg(config: ProjectConfig, plan: Mapping[str, Any]) -> str:
    stations = {station["id"]: station for station in plan["stations"]}
    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<title>MiniJapan AI offline demo plan</title>",
        '<rect width="100%" height="100%" fill="#101827"/>',
        f'<rect x="{PADDING}" y="{PADDING}" width="{WIDTH - 2 * PADDING}" height="{HEIGHT - 2 * PADDING}" fill="#162235" stroke="#60738c" stroke-width="2"/>',
        '<text x="80" y="42" fill="#f7f1df" font-family="sans-serif" font-size="24" font-weight="700">MiniJapan AI · Tokyo demo</text>',
        '<text x="80" y="68" fill="#aebdd0" font-family="sans-serif" font-size="14">Synthetic offline layout · demonstration topology only · not an MTR route</text>',
    ]
    colors = ["#f2b84b", "#62c7bd", "#e9838f", "#a98cf3"]
    for route_index, route in enumerate(plan["routes"]):
        color = colors[route_index % len(colors)]
        points = []
        for station_id in route["station_ids"]:
            station = stations[station_id]
            px, py = _project(station["x"], station["z"], config)
            points.append(f"{px:.1f},{py:.1f}")
        lines.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>'
        )
        lines.append(
            f'<text x="{WIDTH - 300}" y="{110 + route_index * 24}" fill="{color}" font-family="sans-serif" font-size="14">{escape(route["name"])} · demo</text>'
        )

    for structure in plan.get("structures", []):
        placement = structure["placement"]
        size = structure["size"]
        start_x, start_y = _project(placement["x"], placement["z"], config)
        end_x, end_y = _project(placement["x"] + size["x"], placement["z"] + size["z"], config)
        rect_x = min(start_x, end_x)
        rect_y = min(start_y, end_y)
        rect_width = max(5, abs(end_x - start_x))
        rect_height = max(5, abs(end_y - start_y))
        lines.extend(
            [
                f'<rect x="{rect_x:.1f}" y="{rect_y:.1f}" width="{rect_width:.1f}" height="{rect_height:.1f}" fill="#d27b61" fill-opacity="0.24" stroke="#e9a07d" stroke-width="2" stroke-dasharray="5 4"/>',
                f'<text x="{rect_x + 4:.1f}" y="{rect_y + 15:.1f}" fill="#f5c2a7" font-family="monospace" font-size="11">{escape(structure["id"])} · facade</text>',
            ]
        )

    for station in plan["stations"]:
        px, py = _project(station["x"], station["z"], config)
        label = escape(station["label_ja"])
        station_id = escape(station["id"])
        lines.extend(
            [
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="12" fill="#f7f1df" stroke="#101827" stroke-width="4"/>',
                f'<text x="{px + 18:.1f}" y="{py - 5:.1f}" fill="#f7f1df" font-family="sans-serif" font-size="16" font-weight="700">{label}</text>',
                f'<text x="{px + 18:.1f}" y="{py + 14:.1f}" fill="#9eafc4" font-family="monospace" font-size="12">{station_id} · ({station["x"]}, {station["z"]})</text>',
            ]
        )
    lines.extend(
        [
            f'<text x="{PADDING}" y="{HEIGHT - 28}" fill="#9eafc4" font-family="sans-serif" font-size="13">World X → · World Z ↑ · seed {config.seed} · no Minecraft world writes</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"

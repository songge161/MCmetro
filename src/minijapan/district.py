"""Small, flat, uncompressed district with reproducible exploratory interiors."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, deque
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .geodata import load_area
from .schematic import Blocks, write_schematic

AIR = "minecraft:air"
STAIRS = (
    "minecraft:stone_brick_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]"
)
ROAD_WIDTHS = {
    "primary": 10,
    "secondary": 8,
    "tertiary": 7,
    "unclassified": 6,
    "residential": 6,
    "service": 4,
    "pedestrian": 6,
    "footway": 3,
    "living_street": 5,
}


def neighbors(cell):
    x, z = cell
    return ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1))


class Projection:
    def __init__(self, bbox):
        self.south, self.west, self.north, self.east = bbox
        self.longitude_scale = 111_320 * math.cos(math.radians((self.south + self.north) / 2))
        self.width = math.ceil((self.east - self.west) * self.longitude_scale)
        self.length = math.ceil((self.north - self.south) * 111_320)

    def point(self, coordinate):
        lon, lat = coordinate[:2]
        return ((lon - self.west) * self.longitude_scale, (self.north - lat) * 111_320)


def inside_ring(x, z, ring):
    inside = False
    for first, second in zip(ring, ring[1:] + ring[:1]):
        if (first[1] > z) != (second[1] > z):
            crossing = first[0] + (z - first[1]) * (second[0] - first[0]) / (second[1] - first[1])
            if x < crossing:
                inside = not inside
    return inside


def raster_polygon(rings, projection):
    outer = rings[0]
    result = set()
    for z in range(
        max(0, math.floor(min(p[1] for p in outer))),
        min(projection.length, math.ceil(max(p[1] for p in outer))),
    ):
        for x in range(
            max(0, math.floor(min(p[0] for p in outer))),
            min(projection.width, math.ceil(max(p[0] for p in outer))),
        ):
            if inside_ring(x + 0.5, z + 0.5, outer) and not any(
                inside_ring(x + 0.5, z + 0.5, hole) for hole in rings[1:]
            ):
                result.add((x, z))
    return result


def raster_line(points, width, projection):
    result = set()
    radius = width / 2
    for first, second in zip(points, points[1:]):
        dx, dz = second[0] - first[0], second[1] - first[1]
        squared = dx * dx + dz * dz
        for z in range(
            max(0, math.floor(min(first[1], second[1]) - radius)),
            min(projection.length, math.ceil(max(first[1], second[1]) + radius)),
        ):
            for x in range(
                max(0, math.floor(min(first[0], second[0]) - radius)),
                min(projection.width, math.ceil(max(first[0], second[0]) + radius)),
            ):
                portion = (
                    max(
                        0, min(1, ((x + 0.5 - first[0]) * dx + (z + 0.5 - first[1]) * dz) / squared)
                    )
                    if squared
                    else 0
                )
                if (x + 0.5 - first[0] - portion * dx) ** 2 + (
                    z + 0.5 - first[1] - portion * dz
                ) ** 2 <= radius**2:
                    result.add((x, z))
    return result


def component(cells, start):
    reached = {start}
    queue = deque([start])
    while queue:
        for adjacent in neighbors(queue.popleft()):
            if adjacent in cells and adjacent not in reached:
                reached.add(adjacent)
                queue.append(adjacent)
    return reached


def positive_number(value):
    try:
        number = float(str(value).removesuffix(" m").strip())
        return number if math.isfinite(number) and number > 0 else None
    except ValueError:
        return None


def floors_for(tags):
    levels = positive_number(tags.get("building:levels"))
    height = positive_number(tags.get("height"))
    if levels:
        return min(8, max(1, round(levels))), "building:levels"
    if height:
        return min(8, max(1, round(height / 4))), "height_divided_by_4_estimate"
    return 3, "default_3_floors"


def access_paths(roads, occupied, projection):
    parent = {cell: None for cell in sorted(roads - occupied)}
    distance = {cell: 0 for cell in parent}
    queue = deque(parent)
    while queue:
        current = queue.popleft()
        for adjacent in neighbors(current):
            x, z = adjacent
            if (
                0 <= x < projection.width
                and 0 <= z < projection.length
                and adjacent not in occupied
                and adjacent not in parent
            ):
                parent[adjacent] = current
                distance[adjacent] = distance[current] + 1
                queue.append(adjacent)
    return parent, distance


def stair_candidates(interior):
    # Prefer the roomy template. Compact candidates still need voxel connectivity
    # validation: an irregular footprint can leave pockets behind the railings.
    for run, across, stair_width, offset, template in (
        (8, 6, 2, 2, "straight_double"),
        (7, 5, 1, 2, "straight_single"),
        (7, 4, 1, 1, "straight_single_compact"),
    ):
        for x, z in sorted(interior):
            for axis, width, length in (("x", run, across), ("z", across, run)):
                if all((x + dx, z + dz) in interior for dx in range(width) for dz in range(length)):
                    core = (x + 1, z + offset, axis) if axis == "x" else (x + offset, z + 1, axis)
                    yield core, stair_width, template


def stair_core(interior):
    return next((core for core, _, _ in stair_candidates(interior)), None)


def build_building(blocks, cells, boundary, entrance, core, floors, identity, stair_width=2):
    materials = [
        "minecraft:smooth_sandstone",
        "minecraft:light_gray_concrete",
        "minecraft:white_concrete",
        "minecraft:bricks",
    ]
    material = materials[
        int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % len(materials)
    ]
    roof = 1 + floors * 5
    for x, z in sorted(cells):
        for y in range(2, blocks.height):
            state = AIR
            if y >= roof:
                pass  # Clear previous candidate geometry before a retry or downgrade.
            elif (x, z) in boundary:
                state = material
                if y % 5 in (3, 4) and (x + z) % 4 in (1, 2):
                    state = "minecraft:glass"
            elif (y - 1) % 5 == 0:
                state = "minecraft:oak_planks"
            blocks.set(x, y, z, state)
        blocks.set(x, 1, z, "minecraft:stone_bricks")
        blocks.set(x, roof, z, "minecraft:stone_bricks")
        if (x, z) not in boundary and x % 6 == 0 and z % 6 == 0:
            for floor in range(floors):
                blocks.set(x, 5 + floor * 5, z, "minecraft:sea_lantern")
    for y in (2, 3, 4):
        blocks.set(entrance[0], y, entrance[1], AIR)
    if core:
        core_x, core_z, axis = core

        def stair_position(step, side):
            return (core_x + step, core_z + side) if axis == "x" else (core_x + side, core_z + step)

        state = STAIRS.format(facing="east" if axis == "x" else "south")
        for floor in range(floors - 1):
            base = 1 + floor * 5
            for step in range(5):
                for width in range(stair_width):
                    x, z = stair_position(step, width)
                    for y in range(base + step + 2, base + step + 5):
                        blocks.set(x, y, z, AIR)
                    blocks.set(x, base + step + 1, z, state)
            for step in range(4):
                for side in (-1, stair_width):
                    x, z = stair_position(step, side)
                    blocks.set(
                        x,
                        base + 6,
                        z,
                        "minecraft:oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]",
                    )
    return material


def build_frontage(blocks, cells, boundary, entrance, outside, occupied, tags, identity):
    """In-footprint generated decoration, never a claim of real shop identity."""
    if tags.get("building") in {"house", "residential", "apartments", "detached", "dormitory"}:
        return {"style": "residential_windows", "source": "procedural", "cells": []}
    dx, dz = outside[0] - entrance[0], outside[1] - entrance[1]
    accents = ["minecraft:cyan_terracotta", "minecraft:red_terracotta", "minecraft:blue_terracotta"]
    accent = accents[int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % len(accents)]
    frontage = []
    # A small, straight bay near the doorway; no projecting blocks or invented signage.
    for offset in range(-3, 4):
        x, z = entrance[0] - dz * offset, entrance[1] + dx * offset
        if (x, z) not in boundary or (x + dx, z + dz) in occupied:
            continue
        if (x - dx, z - dz) not in cells:
            continue
        frontage.append((x, z))
        blocks.set(x, 5, z, accent)
        if offset and abs(offset) < 3:
            for y in (2, 3, 4):
                blocks.set(x, y, z, "minecraft:glass")
    return {
        "style": "shopfront_bay",
        "source": "procedural_not_real_shop",
        "accent": accent,
        "cells": frontage,
    }


def check_floors(blocks, cells, interior, entrance, floors):
    reached = walkable_reach(blocks, cells, (entrance[0], 2, entrance[1]))
    checks = []
    for floor in range(floors):
        y = 2 + floor * 5
        supported = {
            (x, z)
            for x, z in interior
            if blocks.get(x, y - 1, z) and blocks.get(x, y, z) == 0 and blocks.get(x, y + 1, z) == 0
        }
        reachable = {(x, z) for x, z in supported if (x, y, z) in reached}
        checks.append(
            {
                "floor": floor + 1,
                "walkable_cells": len(supported),
                "reachable_cells": len(reachable),
                "passed": bool(supported) and supported == reachable,
            }
        )
    return checks


def walkable_reach(blocks, cells, start):
    fences = {index for name, index in blocks.palette.items() if "_fence[" in name}

    def clear(x, y, z):
        return (
            1 <= y < blocks.height - 1 and blocks.get(x, y, z) == 0 and blocks.get(x, y + 1, z) == 0
        )

    seen = {start}
    queue = deque([start])
    while queue:
        x, y, z = queue.popleft()
        for nx, nz in neighbors((x, z)):
            if (nx, nz) not in cells:
                continue
            for ny in (y, y + 1, y - 1):
                candidate = (nx, ny, nz)
                if (
                    candidate not in seen
                    and clear(nx, ny, nz)
                    and blocks.get(nx, ny - 1, nz)
                    and blocks.get(nx, ny - 1, nz) not in fences
                    and (ny <= y or blocks.get(x, y + 2, z) == 0)
                    and (ny >= y or blocks.get(nx, y + 1, nz) == 0)
                ):
                    seen.add(candidate)
                    queue.append(candidate)
    return seen


def generate(collection, area):
    projection = Projection(area["bbox"])
    blocks = Blocks(projection.width, 44, projection.length)
    features = sorted(collection["features"], key=lambda feature: str(feature["id"]))
    roads, sidewalks, occupied = set(), set(), set()
    candidates, omitted, road_records = [], [], []
    for feature in features:
        tags = feature["properties"]["tags"]
        geometry = feature["geometry"]
        kind = feature["properties"]["kind"]
        if kind == "road" and geometry["type"] == "LineString":
            highway = tags.get("highway")
            if (
                highway not in ROAD_WIDTHS
                or tags.get("tunnel", "no") != "no"
                or tags.get("bridge", "no") != "no"
                or tags.get("indoor") == "yes"
                or str(tags.get("layer", "0")) != "0"
                or str(tags.get("level", "0")) != "0"
            ):
                omitted.append({"id": feature["id"], "reason": "非首版地面道路类型或高程"})
                continue
            measured = positive_number(tags.get("width"))
            width = min(14, max(3, measured or ROAD_WIDTHS[highway]))
            points = [projection.point(p) for p in geometry["coordinates"]]
            road_cells = raster_line(points, width, projection)
            if road_cells:
                roads.update(road_cells)
                sidewalks.update(raster_line(points, width + 4, projection))
                road_records.append(
                    {
                        "id": feature["id"],
                        "name": tags.get("name"),
                        "width_blocks": width,
                        "width_source": "width_tag" if measured else "highway_default",
                        "tags": tags,
                    }
                )
        elif kind == "building" and geometry["type"] == "Polygon":
            rings = [[projection.point(p) for p in ring] for ring in geometry["coordinates"]]
            cells = raster_polygon(rings, projection)
            if not cells:
                continue
            occupied.update(cells)
            if any(
                not (1 <= x < projection.width - 1 and 1 <= z < projection.length - 1)
                for x, z in rings[0]
            ):
                omitted.append({"id": feature["id"], "reason": "跨样板边界，暂不生成截断建筑"})
            elif len(cells) < 30:
                omitted.append({"id": feature["id"], "reason": "轮廓太小"})
            elif tags.get("building") in ("roof", "construction"):
                omitted.append({"id": feature["id"], "reason": "非完整建筑"})
            else:
                candidates.append((feature, cells))
    if not roads:
        raise ValueError("区域内没有可生成的地面道路")
    road_overlap = len(roads & occupied)
    roads -= occupied
    parent, distance = access_paths(roads, occupied, projection)
    for z in range(projection.length):
        for x in range(projection.width):
            blocks.set(x, 0, z, "minecraft:stone")
            blocks.set(x, 1, z, "minecraft:grass_block[snowy=false]")
    for x, z in sorted(sidewalks - occupied):
        blocks.set(x, 1, z, "minecraft:smooth_stone")
    for x, z in sorted(roads):
        blocks.set(x, 1, z, "minecraft:gray_concrete")
    buildings, built, paths = [], set(), set()
    for feature, cells in candidates:
        identity = feature["id"]
        if cells & built:
            omitted.append({"id": identity, "reason": "建筑轮廓重叠"})
            continue
        interior = {cell for cell in cells if all(adj in cells for adj in neighbors(cell))}
        boundary = cells - interior
        entrances = []
        for wall in sorted(boundary):
            for outside in neighbors(wall):
                opposite = (wall[0] * 2 - outside[0], wall[1] * 2 - outside[1])
                if outside in parent and opposite in interior:
                    entrances.append((distance[outside], wall, outside, opposite))
        if not entrances:
            omitted.append({"id": identity, "reason": "无法连接地面道路"})
            continue
        _, entrance, outside, inside = min(entrances)
        interior_component = component(interior, inside)
        if len(interior_component) != len(interior):
            omitted.append({"id": identity, "reason": "体素化后室内分裂，需要修复轮廓"})
            continue
        tags = feature["properties"]["tags"]
        floors, floor_source = floors_for(tags)
        planned_floors = floors
        attempts = 0
        downgrade_reason = None
        options = stair_candidates(interior_component) if floors > 1 else iter(())
        for core, stair_width, stair_template in options:
            attempts += 1
            material = build_building(
                blocks, cells, boundary, entrance, core, floors, identity, stair_width
            )
            floor_checks = check_floors(blocks, cells, interior, entrance, floors)
            if all(check["passed"] for check in floor_checks):
                break
        else:
            core, stair_width, stair_template = None, 0, None
            if planned_floors > 1:
                downgrade_reason = (
                    "no_connected_stair_candidate" if attempts else "no_stair_template_fits"
                )
            floors = 1
            material = build_building(blocks, cells, boundary, entrance, core, floors, identity)
        frontage = build_frontage(
            blocks, cells, boundary, entrance, outside, occupied, tags, identity
        )
        cursor = outside
        while cursor is not None:
            paths.add(cursor)
            if cursor not in roads:
                blocks.set(cursor[0], 1, cursor[1], "minecraft:smooth_stone")
            cursor = parent[cursor]
        floor_checks = check_floors(blocks, cells, interior, entrance, floors)
        if not all(check["passed"] for check in floor_checks):
            raise ValueError(f"建筑 {identity} 未通过楼层连通性检查")
        buildings.append(
            {
                "id": identity,
                "name": tags.get("name"),
                "tags": tags,
                "footprint": sorted(cells),
                "entrance": entrance,
                "stair_core": core,
                "stair_width": stair_width,
                "stair_template": stair_template,
                "stair_candidates_tested": attempts,
                "floor_downgrade_reason": downgrade_reason,
                "floors": floors,
                "requested_floors": planned_floors,
                "floor_source": floor_source,
                "material": material,
                "frontage": frontage,
                "floor_checks": floor_checks,
                "interior_source": "procedural_open_plan",
            }
        )
        built.update(cells)
    if not buildings:
        raise ValueError("没有可生成并连接道路的建筑")
    report = {
        "schema_version": 1,
        "area": area,
        "minecraft": "1.20.1",
        "data_version": 3465,
        "dimensions": [blocks.width, blocks.height, blocks.length],
        "projection": {
            "origin_lon": projection.west,
            "origin_lat": projection.north,
            "x": "east",
            "z": "south",
            "blocks_per_metre": 1,
            "method": "local_equirectangular",
            "compression": False,
        },
        "buildings": buildings,
        "roads": road_records,
        "omitted": omitted,
        "road_cells_removed_at_buildings": road_overlap,
        "validation": {
            "floor_connectivity": True,
            "game_import_verified": False,
            "method": "two_air_blocks_headroom_step_height_1_grid_bfs",
            "limitation": "楼梯按满格支撑近似，需游戏确认碰撞、护栏与实际行走",
        },
        "limitations": [
            "平坦地形，无地下和高架",
            "关系型建筑依赖上游，尚未拼接",
            "building_part 尚未生成",
            "楼层最多 8 层，每层 5 格",
            "无可连通楼梯核心的建筑简化为单层，逐栋记录原因",
            "门洞无门扇，内部为开放楼层",
            "门面、入口和室内为程序设计，不是现实还原",
            "道路宽度受可玩范围约束，和建筑冲突的铺装不生成",
            "未接入 Yuushya、MTR 或选择性压缩",
        ],
    }
    return blocks, report, roads, paths


def district_preview(report, roads, paths):
    width, _, length = report["dimensions"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {length + 18}">',
        '<rect width="100%" height="100%" fill="#f4f0e6"/>',
    ]
    for cells, color in ((roads, "#71808a"), (paths - roads, "#e5ba69")):
        path = " ".join(f"M{x},{z}h1v1h-1z" for x, z in sorted(cells))
        parts.append(f'<path d="{path}" fill="{color}"/>')
    for building in report["buildings"]:
        path = " ".join(f"M{x},{z}h1v1h-1z" for x, z in building["footprint"])
        parts.append(
            f'<path d="{path}" fill="#bbcdb6"><title>'
            f"{escape(building['id'])} / {escape(building['name'] or '未命名')} / "
            f"{building['floors']} 层</title></path>"
        )
        x, z = building["entrance"]
        parts.append(f'<circle cx="{x + 0.5}" cy="{z + 0.5}" r="1" fill="#d55b40"/>')
        if building["stair_core"]:
            x, z, axis = building["stair_core"]
            span = building["stair_width"]
            stair_width, stair_length = (5, span) if axis == "x" else (span, 5)
            parts.append(
                f'<rect x="{x}" y="{z}" width="{stair_width}" '
                f'height="{stair_length}" fill="#4e7899"/>'
            )
    parts.append(f'<text x="2" y="{length + 5}" font-size="3">北 ↑ / 东 → · 1 格≈1米</text>')
    parts.append(f'<text x="2" y="{length + 10}" font-size="3">灰：道路 红：入口 蓝：楼梯</text>')
    parts.append(
        f'<text x="2" y="{length + 15}" font-size="3">© OpenStreetMap contributors</text></svg>'
    )
    return "\n".join(parts)


def voxel_preview(blocks):
    colors = {
        "minecraft:stone": "#7d8186",
        "minecraft:gray_concrete": "#616e7a",
        "minecraft:grass_block[snowy=false]": "#a4b88a",
        "minecraft:smooth_stone": "#d2d2cc",
        "minecraft:stone_bricks": "#91979c",
        "minecraft:smooth_sandstone": "#e3d7b3",
        "minecraft:light_gray_concrete": "#c3c0b8",
        "minecraft:white_concrete": "#e4e4dc",
        "minecraft:bricks": "#b57f6a",
        "minecraft:glass": "#82b8cf",
        "minecraft:cyan_terracotta": "#617777",
        "minecraft:red_terracotta": "#a04f3b",
        "minecraft:blue_terracotta": "#555575",
    }
    palette_colors = {index: colors.get(name, "#b7a27e") for name, index in blocks.palette.items()}
    tops = {}
    for z in range(blocks.length):
        for x in range(blocks.width):
            tops[x, z] = next(y for y in range(blocks.height - 1, -1, -1) if blocks.get(x, y, z))

    def projected(x, y, z):
        return f"{(x - z + blocks.length) * 3:.1f},{(x + z) * 1.5 + (blocks.height - y) * 3:.1f}"

    def polygon(points, color, opacity=1):
        coords = " ".join(projected(*point) for point in points)
        return f'<polygon points="{coords}" fill="{color}" opacity="{opacity}"/>'

    width = (blocks.width + blocks.length) * 3
    height = (blocks.width + blocks.length) * 1.5 + blocks.height * 3 + 22
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f2efe7"/>',
    ]
    for x, z in sorted(tops, key=lambda cell: (sum(cell), cell)):
        top = tops[x, z]
        for direction in (0, 1):
            neighbor = (x + 1, z) if direction == 0 else (x, z + 1)
            bottom = tops.get(neighbor, -1) + 1
            while bottom <= top:
                state = blocks.get(x, bottom, z)
                upper = bottom + 1
                while upper <= top and blocks.get(x, upper, z) == state:
                    upper += 1
                if state:
                    if direction == 0:
                        points = [
                            (x + 1, bottom, z),
                            (x + 1, bottom, z + 1),
                            (x + 1, upper, z + 1),
                            (x + 1, upper, z),
                        ]
                    else:
                        points = [
                            (x, bottom, z + 1),
                            (x + 1, bottom, z + 1),
                            (x + 1, upper, z + 1),
                            (x, upper, z + 1),
                        ]
                    parts.append(polygon(points, palette_colors[state]))
                    parts.append(polygon(points, "#000000", 0.12 if direction == 0 else 0.24))
                bottom = upper
        parts.append(
            polygon(
                [
                    (x, top + 1, z),
                    (x + 1, top + 1, z),
                    (x + 1, top + 1, z + 1),
                    (x, top + 1, z + 1),
                ],
                palette_colors[blocks.get(x, top, z)],
            )
        )
    parts.append(
        f'<text x="12" y="{height - 7}" font-size="12">'
        "方块体量预览（非游戏截图） · © OpenStreetMap contributors</text></svg>"
    )
    return "\n".join(parts)


def generate_district(snapshot, config, out):
    snapshot, out = Path(snapshot), Path(out)
    if out.exists():
        raise ValueError("输出目录已存在，请使用新目录")
    area = load_area(config)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    coverage = manifest["area"]["bbox"]
    south, west, north, east = area["bbox"]
    if not (
        coverage[0] <= south < north <= coverage[2] and coverage[1] <= west < east <= coverage[3]
    ):
        raise ValueError("生成范围超出快照覆盖范围")
    raw = (snapshot / "features.geojson").read_bytes()
    blocks, report, roads, paths = generate(json.loads(raw), area)
    report["source"] = {
        "snapshot": str(snapshot),
        "manifest": manifest,
        "features_sha256": hashlib.sha256(raw).hexdigest(),
        "quality": json.loads((snapshot / "quality.json").read_text(encoding="utf-8")),
    }
    report["palette"] = blocks.palette
    counts = Counter(blocks.data)
    report["block_counts"] = {name: counts[index] for name, index in blocks.palette.items()}
    out.mkdir(parents=True)
    write_schematic(blocks, out / "district.schem")
    report["schematic_sha256"] = hashlib.sha256((out / "district.schem").read_bytes()).hexdigest()
    (out / "district.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "preview.svg").write_text(district_preview(report, roads, paths), encoding="utf-8")
    (out / "preview-3d.svg").write_text(voxel_preview(blocks), encoding="utf-8")
    instructions = f"""# MC Metro 街区测试包

尺寸：{blocks.width} × {blocks.height} × {blocks.length}（X、Y、Z）。
包含 {len(report["buildings"])} 栋建筑，地面位于本地 Y=1，入口脚底位置为 Y=2。
X 向东，Z 向南；局部近似 1 米 = 1 格，未压缩，地形平坦。

## Windows 导入

1. 使用独立的 Minecraft Java 1.20.1 Fabric 测试实例，安装支持该版本的 WorldEdit。
2. 新建开启作弊的创造模式超平坦测试世界。此包仅使用原版方块。
3. 将 district.schem 复制到该实例的 config/worldedit/schematics/ 目录。
4. 在游戏中执行 /gamemode creative，飞到空旷位置。
5. 执行 //schem load district，然后用 //paste -n 预览范围，确认后执行 //paste。
   使用完整粘贴（不要加 -a），确保楼层和门洞内的空气也正确写入。
6. 粘贴点是样板西北角底座；建筑向 +X、+Z 延伸。粘贴点建议 Y=64。
   此时街面方块 Y=65，玩家脚底 Y=66；可飞到样板外再进入街道。
7. 如需撤销，使用 //undo。

## 验收

- 沿街步行，检查入口是否连通道路；按 preview.svg 的红点找到入口。
- 蓝色标记是楼梯。挑选多层建筑，逐层检查楼梯净空和楼梯口护栏。
- 保存退出并重进，检查建筑和楼梯仍然存在。
- 此文件通过离线几何和格式检查，尚未完成游戏内导入或行走验收。
  连通性算法以整格支撑近似楼梯，不能替代 Minecraft 的碰撞检查。

## 内容范围

道路与建筑轮廓来自真实 OSM 数据；宽度、入口、外观、室内存在程序推定。
缺失楼层默认 3 层，最多 8 层，每层 5 格；无可连通楼梯核心的建筑降为单层。
优先双宽楼梯，窄楼尝试单宽模板；橱窗和入口饰带是程序设计，不代表真实店铺。
跨样板边界、过小或无法安全生成的轮廓不会强行生成，详见 district.json。
未实现复合建筑关系、地下通道、高架、精细店面、Yuushya 和 MTR。
preview-3d.svg 是实际导出方块的体量预览，不是 Minecraft 截图。

数据：© OpenStreetMap contributors，ODbL-1.0。
https://www.openstreetmap.org/copyright
来源、估算、简化、每栋楼连通性结果及文件摘要均记录于 district.json。
WorldEdit 操作参考：https://worldedit.enginehub.org/en/latest/usage/clipboard/
"""
    (out / "导入说明.md").write_text(instructions, encoding="utf-8")
    checklist = [
        "# Windows 游戏内验收清单",
        "",
        "状态：尚未游戏内验收。下表的离线检查通过不代表实际碰撞与行走已通过。",
        "坐标是相对粘贴点的入口脚底偏移（X, Y, Z）；实际坐标需加上粘贴点坐标。",
        "每栋多层楼请从入口沿楼梯步行至最高层，再返回街道；不要用飞行代替楼梯验收。",
        "另检查入口饰带/橱窗是否突兀、道路是否畅通，以及保存退出重进后的结果。",
        "如有问题，请记录建筑 ID、楼层和截图；单宽楼梯是本轮优先检查项。",
        "",
        "| 建筑 ID | 入口偏移 | 生成/计划层数 | 楼梯宽度 | 简化原因 | 游戏内结果 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    reasons = {
        None: "无",
        "no_stair_template_fits": "模板放不下",
        "no_connected_stair_candidate": "候选未通过连通检查",
    }
    for building in report["buildings"]:
        x, z = building["entrance"]
        checklist.append(
            f"| {building['id']} | ({x}, 2, {z}) | {building['floors']}/{building['requested_floors']} "
            f"| {building['stair_width']} | {reasons[building['floor_downgrade_reason']]} | 待测 |"
        )
    (out / "验收清单.md").write_text("\n".join(checklist) + "\n", encoding="utf-8")
    with ZipFile(out / "district-package.zip", "w", compression=ZIP_DEFLATED) as package:
        for name in (
            "district.schem",
            "district.json",
            "preview.svg",
            "preview-3d.svg",
            "导入说明.md",
            "验收清单.md",
        ):
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            package.writestr(info, (out / name).read_bytes())
    return {
        "output": str(out),
        "dimensions": report["dimensions"],
        "buildings": len(report["buildings"]),
        "roads": len(report["roads"]),
        "multi_storey_buildings": sum(b["floors"] > 1 for b in report["buildings"]),
        "floor_connectivity": True,
        "game_import_verified": False,
    }

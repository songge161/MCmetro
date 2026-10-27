"""Traceable OSM snapshots. Coordinates remain WGS84; no inferred geometry."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml


def load_area(path):
    area = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    bbox = area.get("bbox") if isinstance(area, dict) else None
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox 必须包含南、西、北、东四个数值")
    if any(
        isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in bbox
    ):
        raise ValueError("bbox 必须是有限数值")
    south, west, north, east = bbox
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("bbox 范围或顺序无效")
    if north - south > 0.02 or east - west > 0.02:
        raise ValueError("试验阶段采集范围每边不能超过 0.02 度")
    if not area.get("id"):
        raise ValueError("缺少区域 id")
    return area


def query_for(area):
    bbox = ",".join(str(value) for value in area["bbox"])
    selectors = [
        'way["highway"]',
        'nwr["building"]',
        'nwr["building:part"]',
        'nwr["shop"]',
        'nwr["tourism"]',
        'nwr["historic"]',
        'node["entrance"]',
        'nwr["amenity"]',
        'nwr["railway"="station"]',
    ]
    return (
        "[out:json][timeout:40];("
        + "".join(f"{selector}({bbox});" for selector in selectors)
        + ");out meta geom;"
    )


def normalize(payload):
    if payload.get("remark"):
        raise ValueError(f"Overpass 返回不完整结果：{payload['remark']}")
    if not isinstance(payload.get("elements"), list) or not payload["elements"]:
        raise ValueError("数据不包含地图对象")
    features, skipped = [], []
    for element in payload["elements"]:
        identity = f"{element['type']}/{element['id']}"
        tags = element.get("tags", {})
        kind = (
            "building"
            if tags.get("building", "no") != "no"
            else "building_part"
            if tags.get("building:part", "no") != "no"
            else "road"
            if "highway" in tags
            else "poi"
        )
        geometry = None
        reason = "缺失或不完整几何"
        if element["type"] == "node" and "lon" in element and "lat" in element:
            geometry = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        elif element["type"] == "way":
            points = element.get("geometry", [])
            if points and all(p and "lon" in p and "lat" in p for p in points):
                coords = [[p["lon"], p["lat"]] for p in points]
                closed = len(coords) >= 4 and coords[0] == coords[-1]
                if closed and (kind != "road" or tags.get("area") == "yes"):
                    geometry = {"type": "Polygon", "coordinates": [coords]}
                elif kind not in ("building", "building_part") and len(coords) >= 2:
                    geometry = {"type": "LineString", "coordinates": coords}
                else:
                    reason = "建筑轮廓未闭合"
        elif element["type"] == "relation":
            reason = "关系几何尚未拼接；完整成员保留于原始快照"
        if geometry is None:
            skipped.append({"id": identity, "kind": kind, "reason": reason})
            continue
        features.append(
            {
                "type": "Feature",
                "id": identity,
                "geometry": geometry,
                "properties": {
                    "kind": kind,
                    "tags": tags,
                    "osm_version": element.get("version"),
                    "osm_timestamp": element.get("timestamp"),
                },
            }
        )
    buildings = [
        f
        for f in features
        if f["properties"]["kind"] == "building" and f["geometry"]["type"] == "Polygon"
    ]
    report = {
        "raw_elements": len(payload["elements"]),
        "features": len(features),
        "counts": dict(Counter(f["properties"]["kind"] for f in features)),
        "building_footprints": len(buildings),
        "buildings_without_height_or_levels": sum(
            not any(f["properties"]["tags"].get(key) for key in ("height", "building:levels"))
            for f in buildings
        ),
        "skipped": skipped,
        "limitations": [
            "未裁切跨边界对象",
            "高度标签未解释或补全",
            "关系几何未拼接",
            "地图未标注的店铺与建筑不代表现实中不存在",
        ],
    }
    return {"type": "FeatureCollection", "features": features}, report


def preview(collection, bbox):
    south, west, north, east = bbox
    ratio = math.cos(math.radians((south + north) / 2))
    width, height = 1000, 1000 * (north - south) / ((east - west) * ratio)

    def point(coord):
        return (
            f"{(coord[0] - west) / (east - west) * width:.2f},"
            f"{(north - coord[1]) / (north - south) * height:.2f}"
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height + 35}">',
        '<rect width="100%" height="100%" fill="#f6f3ec"/>',
        f'<svg width="{width}" height="{height}" overflow="hidden">',
    ]
    for feature in sorted(collection["features"], key=lambda f: f["properties"]["kind"] == "road"):
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            coords = " ".join(point(p) for p in geometry["coordinates"][0])
            parts.append(
                f'<polygon points="{coords}" fill="#c4cbd0" stroke="#687985" stroke-width="0.8"/>'
            )
        elif geometry["type"] == "LineString" and feature["properties"]["kind"] == "road":
            coords = " ".join(point(p) for p in geometry["coordinates"])
            parts.append(
                f'<polyline points="{coords}" fill="none" stroke="#d18a42" stroke-width="2"/>'
            )
    parts.extend(
        [
            "</svg>",
            f'<text x="10" y="{height + 22}" font-size="13">'
            "North up | OSM geometry preview | © OpenStreetMap contributors</text>",
            "</svg>",
        ]
    )
    return "\n".join(parts)


def fetch_area(
    config,
    out,
    input_path=None,
    endpoint="https://overpass-api.de/api/interpreter",
    transport="urllib",
):
    area = load_area(config)
    query = query_for(area)
    out = Path(out)
    if out.exists():
        raise ValueError("输出目录已存在，请使用新目录保留历史快照")
    if input_path:
        raw = Path(input_path).read_bytes()
    elif transport == "curl":
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "55",
                "--data-urlencode",
                "data@-",
                endpoint,
            ],
            input=query.encode(),
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise ValueError(result.stderr.decode(errors="replace"))
        raw = result.stdout
    else:
        request = Request(
            endpoint,
            data=urlencode({"data": query}).encode(),
            headers={"User-Agent": "MCMetro/0.1 (github.com/songge161/MCmetro)"},
        )
        with urlopen(request, timeout=55) as response:
            raw = response.read()
    payload = json.loads(raw)
    collection, report = normalize(payload)
    manifest = {
        "schema_version": 1,
        "area": area,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "source": str(input_path) if input_path else endpoint,
        "mode": "offline_reprocess" if input_path else "download",
        "transport": transport if not input_path else None,
        "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "query": None if input_path else query,
        "attribution": "© OpenStreetMap contributors",
        "license": "ODbL-1.0",
        "license_url": "https://www.openstreetmap.org/copyright",
    }
    out.mkdir(parents=True)
    (out / "osm.json").write_bytes(raw)
    for name, data in (
        ("features.geojson", collection),
        ("quality.json", report),
        ("manifest.json", manifest),
    ):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "preview.svg").write_text(preview(collection, area["bbox"]), encoding="utf-8")
    return {"output": str(out), "quality": report}

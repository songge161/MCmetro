"""Local OSM PBF extraction.

The pipeline is deliberately split in two layers:

* clipping is delegated to ``osmium-tool`` (streaming, constant memory);
* semantic parsing stays in Python so it needs no extra runtime dependency.

Nothing here infers geometry or downloads data implicitly.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import yaml

from .geodata import classify, load_area, preview

OSMIUM_HINT = "未找到 osmium 命令，请先安装 osmium-tool（brew install osmium-tool）"


def osmium_binary():
    path = shutil.which("osmium")
    if not path:
        raise ValueError(OSMIUM_HINT)
    return path


def osmium_version():
    path = shutil.which("osmium")
    if not path:
        return None
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = result.stdout.strip().splitlines()
    return lines[0].strip() if lines else None


def load_source(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("id") or not data.get("url"):
        raise ValueError("数据源需要 id 与 url")
    return data


def bbox_argument(area):
    """osmium expects ``left,bottom,right,top`` = west,south,east,north."""
    south, west, north, east = area["bbox"]
    return f"{west},{south},{east},{north}"


def cut(pbf, area, target):
    result = subprocess.run(
        [
            osmium_binary(),
            "extract",
            "-b",
            bbox_argument(area),
            "--overwrite",
            str(pbf),
            "-o",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode:
        raise ValueError(f"osmium extract 失败：{result.stderr.strip()}")
    return Path(target)


def to_xml(pbf, target):
    result = subprocess.run(
        [osmium_binary(), "cat", str(pbf), "-f", "osm", "--overwrite", "-o", str(target)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode:
        raise ValueError(f"osmium cat 失败：{result.stderr.strip()}")
    return Path(target)


def _version(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _tags(element):
    return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}


def parse_osm_xml(path):
    """Turn an OSM XML export into the same FeatureCollection the Overpass path emits."""
    nodes = {}
    features = []
    skipped = []
    raw_count = 0

    for _, element in ElementTree.iterparse(str(path), events=("end",)):
        if element.tag == "node":
            raw_count += 1
            node_id = element.get("id")
            lat, lon = element.get("lat"), element.get("lon")
            tags = _tags(element)
            if node_id and lat is not None and lon is not None:
                coordinate = [float(lon), float(lat)]
                nodes[node_id] = coordinate
                if tags:
                    features.append(
                        {
                            "type": "Feature",
                            "id": f"node/{node_id}",
                            "geometry": {"type": "Point", "coordinates": coordinate},
                            "properties": {
                                "kind": classify(tags),
                                "tags": tags,
                                "osm_version": _version(element.get("version")),
                                "osm_timestamp": element.get("timestamp"),
                            },
                        }
                    )
            element.clear()
        elif element.tag == "way":
            raw_count += 1
            way_id = element.get("id")
            tags = _tags(element)
            kind = classify(tags)
            refs = [nd.get("ref") for nd in element.findall("nd")]
            coords = [nodes[ref] for ref in refs if ref in nodes]
            geometry = None
            reason = "缺失节点坐标"
            if len(coords) == len(refs) and len(coords) >= 2:
                closed = len(coords) >= 4 and coords[0] == coords[-1]
                if closed and (kind != "road" or tags.get("area") == "yes"):
                    geometry = {"type": "Polygon", "coordinates": [coords]}
                elif kind not in ("building", "building_part"):
                    geometry = {"type": "LineString", "coordinates": coords}
                else:
                    reason = "建筑轮廓未闭合"
            if geometry is None:
                skipped.append({"id": f"way/{way_id}", "kind": kind, "reason": reason})
            else:
                features.append(
                    {
                        "type": "Feature",
                        "id": f"way/{way_id}",
                        "geometry": geometry,
                        "properties": {
                            "kind": kind,
                            "tags": tags,
                            "osm_version": _version(element.get("version")),
                            "osm_timestamp": element.get("timestamp"),
                        },
                    }
                )
            element.clear()
        elif element.tag == "relation":
            raw_count += 1
            tags = _tags(element)
            if tags:
                skipped.append(
                    {
                        "id": f"relation/{element.get('id')}",
                        "kind": classify(tags),
                        "reason": "关系几何尚未拼接；完整成员保留于裁切后的原始数据",
                    }
                )
            element.clear()

    buildings = [
        feature
        for feature in features
        if feature["properties"]["kind"] == "building" and feature["geometry"]["type"] == "Polygon"
    ]
    report = {
        "raw_elements": raw_count,
        "features": len(features),
        "counts": dict(Counter(feature["properties"]["kind"] for feature in features)),
        "building_footprints": len(buildings),
        "buildings_without_height_or_levels": sum(
            not any(feature["properties"]["tags"].get(key) for key in ("height", "building:levels"))
            for feature in buildings
        ),
        "skipped": skipped,
        "limitations": [
            "按 bbox 裁切并保留跨越边界的完整 way（complete_ways），区域外几何不额外裁断",
            "高度标签未解释或补全",
            "关系几何未拼接",
            "地图未标注的店铺与建筑不代表现实中不存在",
        ],
    }
    return {"type": "FeatureCollection", "features": features}, report


def sha256_of(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_area(config, out, pbf=None, source=None, keep_intermediate=False):
    area = load_area(config)
    out = Path(out)
    if out.exists():
        raise ValueError("输出目录已存在，请使用新目录保留历史快照")
    osmium_binary()
    if pbf is None:
        raise ValueError("需要 --pbf 指定本地 .osm.pbf 文件")
    pbf = Path(pbf)
    if not pbf.is_file():
        raise ValueError(f"找不到 PBF 文件：{pbf}")
    source_info = load_source(source) if source else None

    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = out.parent / f".{out.name}.work"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    clipped = workdir / "area.osm.pbf"
    xml = workdir / "area.osm"
    try:
        cut(pbf, area, clipped)
        to_xml(clipped, xml)
        collection, report = parse_osm_xml(xml)
    finally:
        if not keep_intermediate:
            shutil.rmtree(workdir, ignore_errors=True)

    manifest = {
        "schema_version": 1,
        "area": area,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "source": source_info,
        "pbf": {
            "path": str(pbf),
            "size_bytes": pbf.stat().st_size,
            "sha256": sha256_of(pbf),
        },
        "clip_bbox": area["bbox"],
        "osmium": osmium_version(),
        "attribution": "© OpenStreetMap contributors",
        "license": "ODbL-1.0",
        "license_url": "https://www.openstreetmap.org/copyright",
    }
    out.mkdir(parents=True)
    for name, data in (
        ("features.geojson", collection),
        ("quality.json", report),
        ("manifest.json", manifest),
    ):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "preview.svg").write_text(preview(collection, area["bbox"]), encoding="utf-8")
    return {"output": str(out), "quality": report}

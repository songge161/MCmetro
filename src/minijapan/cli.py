from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .config import load_config
from .district import generate_district
from .errors import ConfigurationError
from .geodata import fetch_area
from .material_probe import generate_material_probe
from .mod_catalog import inspect_mod
from .pbf import extract_area
from .planner import write_plan_outputs
from .validation import validate_config_model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minijapan", description="MC Metro 本地城市规划与街区生成工具"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="report local tool versions and MVP capabilities")
    catalog = subparsers.add_parser(
        "inspect-mod", help="只读检查 Fabric 模组资源，不执行代码或证明运行时兼容"
    )
    catalog.add_argument("--jar", required=True, type=Path)
    catalog.add_argument("--out", required=True, type=Path)
    catalog.add_argument("--sha512", help="可选发布摘要，用于下载完整性核对")
    probe = subparsers.add_parser(
        "material-probe", help="生成版本锁定的 Yuushya 独立材料测试区，非已验证街区适配"
    )
    probe.add_argument("--jar", required=True, type=Path)
    probe.add_argument("--out", required=True, type=Path)
    fetch = subparsers.add_parser("fetch-area", help="采集真实地图并输出来源与质量报告")
    fetch.add_argument("--config", required=True, type=Path)
    fetch.add_argument("--out", required=True, type=Path)
    fetch.add_argument("--input", type=Path, help="离线重处理 Overpass JSON")
    fetch.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter")
    fetch.add_argument("--transport", choices=("urllib", "curl"), default="urllib")
    extract = subparsers.add_parser(
        "extract-area", help="从本地 OSM PBF 裁切区域快照（本地优先，不做在线查询）"
    )
    extract.add_argument("--config", required=True, type=Path)
    extract.add_argument("--pbf", type=Path, help="本地 .osm.pbf 文件")
    extract.add_argument("--source", type=Path, help="数据源 YAML，用于记录来源与许可")
    extract.add_argument("--out", required=True, type=Path)
    extract.add_argument("--keep-intermediate", action="store_true", help="保留裁切后的中间文件")
    district = subparsers.add_parser(
        "generate-district", help="从真实快照生成可探索街区 schem 样板"
    )
    district.add_argument("--snapshot", required=True, type=Path)
    district.add_argument("--config", required=True, type=Path)
    district.add_argument("--out", required=True, type=Path)
    for command in ("validate", "plan"):
        command_parser = subparsers.add_parser(
            command, help=f"{command} a YAML project configuration"
        )
        command_parser.add_argument("--config", required=True, type=Path)
        if command == "plan":
            command_parser.add_argument("--out", required=True, type=Path)
    return parser


def _doctor() -> int:
    result: Dict[str, Any] = {
        "minijapan_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "java": shutil.which("java") or "not found",
        "gradle": shutil.which("gradle") or "not found",
        "osmium": shutil.which("osmium") or "not found",
        "capabilities": {
            "offline_yaml_planning": True,
            "svg_preview": True,
            "local_pbf_extract": bool(shutil.which("osmium")),
            "district_schematic_export": "Sponge v2 / Java 1.20.1 / game import unverified",
            "mtr_write_adapter": "unverified / not implemented",
            "minecraft_world_access": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> None:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            raise SystemExit(_doctor())
        if args.command == "inspect-mod":
            print(
                json.dumps(
                    inspect_mod(args.jar, args.out, args.sha512), ensure_ascii=False, indent=2
                )
            )
            return
        if args.command == "material-probe":
            print(
                json.dumps(
                    generate_material_probe(args.jar, args.out), ensure_ascii=False, indent=2
                )
            )
            return
        if args.command == "generate-district":
            result = generate_district(args.snapshot, args.config, args.out)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.command == "fetch-area":
            result = fetch_area(args.config, args.out, args.input, args.endpoint, args.transport)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.command == "extract-area":
            result = extract_area(
                args.config,
                args.out,
                args.pbf,
                args.source,
                args.keep_intermediate,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        config = load_config(args.config)
        if args.command == "validate":
            issues = [issue.as_dict() for issue in validate_config_model(config)]
            result = {"status": "valid" if not issues else "invalid", "errors": issues}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            raise SystemExit(0 if not issues else 1)
        outputs = write_plan_outputs(config, args.out)
        print(
            json.dumps(
                {key: str(path) for key, path in outputs.items()}, ensure_ascii=False, indent=2
            )
        )
        raise SystemExit(0 if "plan" in outputs else 1)
    except (ConfigurationError, ValueError, OSError) as error:
        print(
            json.dumps(
                {"status": "invalid", "errors": [{"message": str(error)}]},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)

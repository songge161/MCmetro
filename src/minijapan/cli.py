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
from .errors import ConfigurationError
from .geodata import fetch_area
from .planner import write_plan_outputs
from .validation import validate_config_model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minijapan", description="MiniJapan AI offline planning tools"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="report local tool versions and MVP capabilities")
    fetch = subparsers.add_parser("fetch-area", help="采集真实地图并输出来源与质量报告")
    fetch.add_argument("--config", required=True, type=Path)
    fetch.add_argument("--out", required=True, type=Path)
    fetch.add_argument("--input", type=Path, help="离线重处理 Overpass JSON")
    fetch.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter")
    fetch.add_argument("--transport", choices=("urllib", "curl"), default="urllib")
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
        "capabilities": {
            "offline_yaml_planning": True,
            "svg_preview": True,
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
        if args.command == "fetch-area":
            result = fetch_area(args.config, args.out, args.input, args.endpoint, args.transport)
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

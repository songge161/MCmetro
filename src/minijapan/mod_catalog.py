"""Read-only Fabric JAR resource inventory; never a runtime registry probe."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

BLOCKSTATE = re.compile(r"^assets/([a-z0-9_.-]+)/blockstates/([a-z0-9_./-]+)\.json$")
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_TOTAL_JSON_BYTES = 128 * 1024 * 1024


def inspect_mod(jar, out, expected_sha512=None):
    jar, out = Path(jar), Path(out)
    if out.exists():
        raise ValueError("输出文件已存在，请使用新路径")
    sha256, sha512 = hashlib.sha256(), hashlib.sha512()
    with jar.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha256.update(chunk)
            sha512.update(chunk)
    if expected_sha512 and sha512.hexdigest() != expected_sha512.lower():
        raise ValueError("模组包 SHA512 与发布摘要不一致")
    try:
        with ZipFile(jar) as archive:
            names = archive.namelist()
            if len(names) > 100_000 or len(names) != len(set(names)):
                raise ValueError("模组包条目过多或存在重名条目")
            total = 0

            def read_json(name):
                nonlocal total
                size = archive.getinfo(name).file_size
                total += size
                if size > MAX_JSON_BYTES or total > MAX_TOTAL_JSON_BYTES:
                    raise ValueError("模组 JSON 资源超过读取限制")
                value = json.loads(archive.read(name).decode("utf-8-sig"))
                if not isinstance(value, dict):
                    raise ValueError(f"JSON 资源必须为对象：{name}")
                return value

            if "fabric.mod.json" not in names:
                raise ValueError("当前检查命令仅支持含 fabric.mod.json 的 Fabric JAR")
            metadata = read_json("fabric.mod.json")
            language = {}
            candidates = []
            for name in sorted(names):
                match = BLOCKSTATE.fullmatch(name)
                if not match:
                    continue
                namespace, path = match.groups()
                if ".." in path.split("/"):
                    raise ValueError("不合法的资源路径")
                if namespace not in language:
                    lang_path = f"assets/{namespace}/lang/zh_cn.json"
                    language[namespace] = read_json(lang_path) if lang_path in names else {}
                state = read_json(name)
                variants = state.get("variants", {})
                if not isinstance(variants, dict):
                    raise ValueError(f"variants 必须为对象：{name}")
                models = set()

                def collect_models(value):
                    if isinstance(value, dict):
                        if isinstance(value.get("model"), str):
                            models.add(value["model"])
                        for child in value.values():
                            collect_models(child)
                    elif isinstance(value, list):
                        for child in value:
                            collect_models(child)

                collect_models(state)
                candidates.append(
                    {
                        "candidate_block_id": f"{namespace}:{path}",
                        "name_zh_cn": language[namespace].get(
                            f"block.{namespace}.{path.replace('/', '.')}"
                        ),
                        "evidence_path": name,
                        "variant_selectors": sorted(variants),
                        "has_multipart": "multipart" in state,
                        "model_references": sorted(models),
                        "runtime_verified": False,
                    }
                )
    except (BadZipFile, UnicodeError, RecursionError) as error:
        raise ValueError(f"无法读取模组资源：{error}") from error
    report = {
        "schema_version": 1,
        "kind": "static_resource_inventory_not_runtime_registry",
        "source": {
            "file": jar.name,
            "sha256": sha256.hexdigest(),
            "sha512": sha512.hexdigest(),
            "publisher_hash_verified": bool(expected_sha512),
        },
        "mod": {key: metadata.get(key) for key in ("id", "version", "name", "license", "depends")},
        "candidate_count": len(candidates),
        "named_candidate_count": sum(isinstance(c["name_zh_cn"], str) for c in candidates),
        "runtime_verified": False,
        "limitations": [
            "资源文件可能未实际注册；缺失资源也不代表方块不存在",
            "variants 是渲染选择条件，不是完整合法状态集或默认状态",
            "不解析碰撞、行为、方块实体、模型继承、附加资源包或嵌套 JAR",
            "未推断材料用途，未写入世界，也未启动游戏",
        ],
        "candidates": candidates,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {
        key: report[key] for key in ("candidate_count", "named_candidate_count", "runtime_verified")
    }

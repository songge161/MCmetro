"""A version-pinned Yuushya test yard, not a production material adapter."""

from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from .schematic import Blocks, write_schematic

REVIEWED_SHA256 = "ab1c39d0763d8209aaf5bd6cc193724439dc3ad0738ffcb82af32042981f6518"
WALL = "yuushya:gray_wall"
WINDOW = "yuushya:black_windows_0"
FACINGS = ("north", "east", "south", "west")
REVIEWED_CLASSES = (
    "com/yuushya/utils/AddonLoader.class",
    "com/yuushya/registries/YuushyaRegistryConfig.class",
    "com/yuushya/block/YuushyaBlockFactory.class",
    "com/yuushya/block/YuushyaBlockFactory$BlockWithClassTypeNormal.class",
    "com/yuushya/block/PoleLineBlock.class",
    "com/yuushya/block/LineBlock.class",
    "com/yuushya/block/PoleBlock.class",
)


def load_contract(jar):
    """Only this reviewed JAR is accepted; no guessing across mod versions."""
    digest = hashlib.sha256()
    with Path(jar).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != REVIEWED_SHA256:
        raise ValueError("JAR 与已核对的 Yuushya 1.20.1 Fabric 2.3.0 摘要不一致，不跨版本猜测状态")
    evidence = {}
    try:
        with ZipFile(jar) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError("JAR 存在重名条目")

            def read(name):
                if archive.getinfo(name).file_size > 4 * 1024 * 1024:
                    raise ValueError("资源超过读取限制")
                raw = archive.read(name)
                evidence[name] = hashlib.sha256(raw).hexdigest()
                return json.loads(raw)

            metadata = read("fabric.mod.json")
            if (metadata["id"], metadata["version"]) != ("yuushya", "2.3.0"):
                raise ValueError("模组元数据不匹配")
            defaults = {b["name"]: b for b in read("data/yuushya/register/_class.json")["block"]}
            result = {}
            for block_id, filename, class_type, kit in (
                (WALL, "texture.json", "block", "block"),
                (WINDOW, "block_window.json", "WindowsBlock", "pole_line"),
            ):
                name = block_id.split(":")[1]
                definitions = read(f"data/yuushya/register/{filename}")["block"]
                matches = [b for b in definitions if b.get("name") == name]
                if len(matches) != 1 or matches[0].get("class_type") != class_type:
                    raise ValueError(f"注册定义不匹配：{block_id}")
                entry, base = matches[0], defaults[class_type]
                # Only the scalar sections needed for these two reviewed entries.
                # This is not a generic reimplementation of Yuushya inheritance.
                properties = {**base.get("properties", {}), **entry.get("properties", {})}
                blockstate = {**base.get("blockstate", {}), **entry.get("blockstate", {})}
                if blockstate.get("kit") != kit or properties.get("has_collision") is not True:
                    raise ValueError(f"方块模板或碰撞声明变化：{block_id}")
                if properties.get("is_solid") is not (block_id == WALL):
                    raise ValueError(f"含水状态推断前提变化：{block_id}")
                variants = read(f"assets/yuushya/blockstates/{name}.json")["variants"]
                collision = read(f"data/yuushya/collision/{name}.json")["blockstates"]
                collision_map = {c["variant"]: c["collision"] for c in collision}
                for selector, variant in variants.items():
                    if selector not in collision_map or not collision_map[selector]:
                        raise ValueError(f"缺少碰撞定义：{block_id} {selector}")
                    for model in variant if isinstance(variant, list) else [variant]:
                        namespace, model_path = model["model"].split(":", 1)
                        read(f"assets/{namespace}/models/{model_path}.json")
                result[block_id] = {
                    "class_type": class_type,
                    "kit": kit,
                    "properties": properties,
                    "variant_selectors": sorted(variants),
                    "collision_definition_count": len(collision_map),
                    "collision_extends_outside_cell": any(
                        value < 0 or value > 16
                        for boxes in collision_map.values()
                        for box in boxes
                        for corner in ("from", "to")
                        for value in box[corner]
                    ),
                    "runtime_verified": False,
                }
            for path in REVIEWED_CLASSES:
                evidence[path] = hashlib.sha256(archive.read(path)).hexdigest()
    except (BadZipFile, KeyError, TypeError, UnicodeError) as error:
        raise ValueError(f"Yuushya 证据资源不完整或无效：{error}") from error
    return {
        "jar_sha256": digest.hexdigest(),
        "mod": {key: metadata.get(key) for key in ("id", "version", "depends")},
        "release_type": "beta",
        "resource_sha256": evidence,
        "materials": result,
        "runtime_verified": False,
    }


def window_state(facing, column=0, row=0, width=1, height=1):
    if facing not in FACINGS or not (0 <= column < width and 0 <= row < height):
        raise ValueError("窗框朝向或面板索引无效")
    # Column increases along +X (north/south) or +Z (east/west).
    # Matches the reviewed LineBlock neighbor-to-pos mapping.
    first = "left" if facing in ("north", "east") else "right"
    last = "right" if first == "left" else "left"
    pos = (
        "none"
        if width == 1
        else first
        if column == 0
        else last
        if column == width - 1
        else "middle"
    )
    ypos = (
        "none"
        if height == 1
        else "bottom"
        if row == 0
        else "top"
        if row == height - 1
        else "middle"
    )
    return f"{WINDOW}[facing={facing},pos={pos},waterlogged=false,ypos={ypos}]"


def build_probe(contract):
    blocks = Blocks(36, 8, 26)
    for x in range(blocks.width):
        for z in range(blocks.length):
            blocks.set(x, 0, z, "minecraft:smooth_stone")
    cases, occupied = [], set()

    def add_case(identity, label, placements):
        positions = []
        states = []
        for x, y, z, state in placements:
            if (x, y, z) in occupied:
                raise ValueError("测试单元重叠")
            block_id = state.split("[")[0]
            if block_id.startswith("yuushya:"):
                selector = (
                    state.partition("[")[2].removesuffix("]").replace(",waterlogged=false", "")
                )
                if selector not in contract["materials"][block_id]["variant_selectors"]:
                    raise ValueError(f"状态缺少资源证据：{state}")
            blocks.set(x, y, z, state)
            occupied.add((x, y, z))
            positions.append([x, y, z])
            states.append(state)
        cases.append(
            {
                "id": identity,
                "label": label,
                "positions": positions,
                "placement_states": states,
                "game_result": "待测",
            }
        )

    for identity, label, start, state in (
        ("wall", "灰墙", 2, WALL),
        ("glass_control", "原版玻璃对照", 12, "minecraft:glass"),
    ):
        add_case(
            identity,
            label,
            [(x, y, 4, state) for x in range(start, start + 5) for y in range(1, 5)],
        )
    for i, facing in enumerate(FACINGS):
        add_case(f"single_{facing}", f"单窗 {facing}", [(23 + i * 3, 1, 4, window_state(facing))])
        center = 5 + i * 8
        panel = []
        for column in range(3):
            for row in range(3):
                x, z = (
                    (center - 1 + column, 14)
                    if facing in ("north", "south")
                    else (center, 13 + column)
                )
                panel.append((x, 1 + row, z, window_state(facing, column, row, 3, 3)))
        add_case(f"panel_{facing}", f"成组窗 {facing}", panel)
    facade = []
    for column in range(5):
        for row in range(5):
            state = (
                window_state("north", column - 1, row - 1, 3, 3)
                if 1 <= column <= 3 and 1 <= row <= 3
                else WALL
            )
            facade.append((3 + column, 1 + row, 22, state))
    add_case("facade", "灰墙嵌窗", facade)
    return blocks, cases


def probe_preview(cases):
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 600">',
        '<rect width="720" height="600" fill="#f4f0e6"/>',
        '<text x="16" y="24" font-size="16">Yuushya 测试区平面索引（非材质渲染、非游戏截图）</text>',
    ]
    for case in cases:
        cells = sorted({(x, z) for x, _, z in case["positions"]})
        for x, z in cells:
            parts.append(
                f'<rect x="{x * 20}" y="{z * 20 + 40}" width="19" height="19" fill="#568d9c"/>'
            )
        x, z = cells[0]
        parts.append(
            f'<text x="{x * 20}" y="{z * 20 + 34}" font-size="10">{escape(case["label"])}</text>'
        )
    parts.append(
        '<text x="16" y="585" font-size="14">北 ↑ / X 向东 / Z 向南；坐标相对粘贴点，绕行观察正反面</text></svg>'
    )
    return "\n".join(parts)


def generate_material_probe(jar, out):
    out = Path(out)
    if out.exists():
        raise ValueError("输出目录已存在，请使用新目录")
    contract = load_contract(jar)
    blocks, cases = build_probe(contract)
    report = {
        "schema_version": 1,
        "purpose": "isolated_material_probe_not_district_replacement",
        "dimensions": [blocks.width, blocks.height, blocks.length],
        "source": contract,
        "cases": cases,
        "palette": blocks.palette,
        "validation": {
            "resource_selectors_checked": True,
            "game_import_verified": False,
            "collision_runtime_verified": False,
        },
    }
    out.mkdir(parents=True)
    write_schematic(blocks, out / "yuushya-probe.schem")
    report["schematic_sha256"] = hashlib.sha256(
        (out / "yuushya-probe.schem").read_bytes()
    ).hexdigest()
    (out / "probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "preview.svg").write_text(probe_preview(cases), encoding="utf-8")
    instructions = """# Yuushya 独立材料测试区

状态：尚未游戏内验收。36×8×26 格，仅测试两种 Yuushya 材料与原版玻璃对照。
不包含模组、贴图、模型或材质渲染；不会替换已有街区。玻璃对照不是 Yuushya 材料。

## 准备与导入

使用独立的 Java 1.20.1 Fabric 测试实例，安装 Yuushya 2.3.0 Fabric（本轮检查版本，发布标记 beta）、
相应依赖与支持该版本的 WorldEdit。JAR 声明需要 Fabric Loader >=0.16.0、Java >=17、
Architectury >=9.2.14 和 Fabric API。该组合尚未实际启动验证，不要覆盖正在玩的整合包。
配套资源包与连接纹理要求以 https://yuushya.com/townscape/download-list/townscape.html 为准。

1. 新建创造模式超平坦测试世界，开启作弊。
2. 把 yuushya-probe.schem 放入实例的 config/worldedit/schematics/。
3. 飞到空旷位置，执行 //schem load yuushya-probe，再用 //paste -n 选择范围。
4. 确认不会覆盖已有建筑后执行 //paste（不加 -a）；需要撤销时使用 //undo。
5. 未安装匹配模组或出现未知方块/状态错误时停止，不把导入成功提示等同于材料完整。

粘贴点为西北角底座；地板本地 Y=0，站立脚底 Y=1，向 +X/+Z 展开。
下表是样本方块的相对坐标，不是玩家传送点。实际坐标需加上粘贴点。

## 验收

- 核对数量、朝向、透明度、贴图是否缺失；从正反两面观察窗框。
- 行走接近灰墙和窗框，检查碰撞；窗框碰撞定义部分超过单格边界，不能当成完整立方体。
- 对比单窗与 3×3 窗组，检查边缘、中心连接；本轮显式写出连接状态，不依赖导入器替我们计算。
- 在测试副本中拆掉窗组中心再放回，记录邻接更新后的变化，不把静态外观正确等同于连接逻辑正确。
- 保存退出并重进，再检查状态和效果；所有项目通过前不得作为正式街区材料。
- probe.json 记录具体方块状态、来源与未验证项。需要反馈时附样本 ID、版本和截图。

| 样本 ID | 内容 | 首个样本方块相对坐标 | 渲染 / 碰撞 / 连接 / 保存 |
| --- | --- | --- | --- |
"""
    for case in cases:
        instructions += f"| {case['id']} | {case['label']} | {case['positions'][0]} | 待测 |\n"
    (out / "导入与验收.md").write_text(instructions, encoding="utf-8")
    with ZipFile(out / "yuushya-probe-package.zip", "w", compression=ZIP_DEFLATED) as package:
        for name in ("yuushya-probe.schem", "probe.json", "preview.svg", "导入与验收.md"):
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            package.writestr(info, (out / name).read_bytes())
    return {
        "output": str(out),
        "cases": len(cases),
        "dimensions": report["dimensions"],
        "game_import_verified": False,
    }

import hashlib
import json
from itertools import product
from xml.etree import ElementTree
from zipfile import ZipFile

import nbtlib
import pytest

from minijapan import material_probe as probe


def fixture_jar(tmp_path, monkeypatch, missing_selector=None, window_solid=False):
    """Synthetic resources only; real package evidence is checked separately."""
    selectors = [
        f"facing={facing},pos={pos},ypos={ypos}"
        for facing, pos, ypos in product(
            probe.FACINGS, ("left", "right", "middle", "none"), ("bottom", "top", "middle", "none")
        )
    ]
    if missing_selector:
        selectors.remove(missing_selector)
    definitions = {
        "fabric.mod.json": {"id": "yuushya", "version": "2.3.0"},
        "data/yuushya/register/_class.json": {
            "block": [
                {
                    "name": "block",
                    "properties": {"has_collision": True, "is_solid": True},
                    "blockstate": {"kit": "block"},
                },
                {
                    "name": "WindowsBlock",
                    "properties": {"has_collision": False, "is_solid": window_solid},
                    "blockstate": {"kit": "normal"},
                },
            ]
        },
        "data/yuushya/register/texture.json": {
            "block": [{"name": "gray_wall", "class_type": "block"}]
        },
        "data/yuushya/register/block_window.json": {
            "block": [
                {
                    "name": "black_windows_0",
                    "class_type": "WindowsBlock",
                    "properties": {"has_collision": True},
                    "blockstate": {"kit": "pole_line"},
                }
            ]
        },
        "assets/yuushya/models/block/test.json": {},
    }
    for name, keys in (("gray_wall", [""]), ("black_windows_0", selectors)):
        definitions[f"assets/yuushya/blockstates/{name}.json"] = {
            "variants": {key: {"model": "yuushya:block/test"} for key in keys}
        }
        definitions[f"data/yuushya/collision/{name}.json"] = {
            "blockstates": [
                {"variant": key, "collision": [{"from": [0, 0, 0], "to": [16, 16, 16.5]}]}
                for key in keys
            ]
        }
    jar = tmp_path / "synthetic.jar"
    with ZipFile(jar, "w") as archive:
        for name, value in definitions.items():
            archive.writestr(name, json.dumps(value))
        for path in probe.REVIEWED_CLASSES:
            archive.writestr(path, b"synthetic class placeholder -- never executed")
    monkeypatch.setattr(probe, "REVIEWED_SHA256", hashlib.sha256(jar.read_bytes()).hexdigest())
    return jar


@pytest.mark.parametrize(
    "facing,first,last",
    [
        ("north", "left", "right"),
        ("east", "left", "right"),
        ("south", "right", "left"),
        ("west", "right", "left"),
    ],
)
def test_window_connection_states_follow_reviewed_direction_mapping(facing, first, last):
    assert f"pos={first},waterlogged=false,ypos=bottom" in probe.window_state(facing, 0, 0, 3, 3)
    assert f"pos={last},waterlogged=false,ypos=top" in probe.window_state(facing, 2, 2, 3, 3)
    assert "pos=middle,waterlogged=false,ypos=middle" in probe.window_state(facing, 1, 1, 3, 3)
    assert "pos=none,waterlogged=false,ypos=none" in probe.window_state(facing)


def test_invalid_direction_is_not_silently_defaulted():
    with pytest.raises(ValueError):
        probe.window_state("up")
    with pytest.raises(ValueError):
        probe.window_state("north", 3, 0, 3, 3)


def test_probe_exports_expected_blocks_and_is_deterministic(tmp_path, monkeypatch):
    jar = fixture_jar(tmp_path, monkeypatch)
    contract = probe.load_contract(jar)
    assert contract["materials"][probe.WINDOW]["properties"]["has_collision"]
    assert not contract["materials"][probe.WINDOW]["properties"]["is_solid"]
    assert contract["materials"][probe.WINDOW]["collision_extends_outside_cell"]
    blocks, cases = probe.build_probe(contract)
    assert len(cases) == 11
    for case in cases:
        assert len(case["positions"]) == len(case["placement_states"])
        for (x, y, z), state in zip(case["positions"], case["placement_states"]):
            assert blocks.get(x, y, z) == blocks.palette[state]
    cells = [tuple(cell) for case in cases for cell in case["positions"]]
    assert len(cells) == len(set(cells)) == 105
    indices = {index for state, index in blocks.palette.items() if state.startswith(probe.WINDOW)}
    assert sum(value in indices for value in blocks.data) == 49
    assert blocks.data.count(blocks.palette[probe.WALL]) == 36
    assert blocks.data.count(blocks.palette["minecraft:glass"]) == 20
    out = tmp_path / "probe"
    assert not probe.generate_material_probe(jar, out)["game_import_verified"]
    root = nbtlib.load(out / "yuushya-probe.schem")
    assert [int(root[key]) for key in ("Width", "Height", "Length")] == [36, 8, 26]
    assert len(root["BlockData"]) == 36 * 8 * 26
    assert set(root["Palette"]) == set(blocks.palette)
    assert not root["BlockEntities"]
    assert bytes(int(v) & 255 for v in root["BlockData"]) == blocks.data
    ElementTree.parse(out / "preview.svg")
    with ZipFile(out / "yuushya-probe-package.zip") as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 4
        assert archive.read("yuushya-probe.schem") == (out / "yuushya-probe.schem").read_bytes()
        assert "待测" in archive.read("导入与验收.md").decode()
    other = tmp_path / "again"
    probe.generate_material_probe(jar, other)
    assert (out / "yuushya-probe-package.zip").read_bytes() == (
        other / "yuushya-probe-package.zip"
    ).read_bytes()


def test_source_hash_mismatch_and_existing_output_are_rejected(tmp_path, monkeypatch):
    jar = fixture_jar(tmp_path, monkeypatch)
    monkeypatch.setattr(probe, "REVIEWED_SHA256", "0" * 64)
    out = tmp_path / "probe"
    with pytest.raises(ValueError, match="摘要"):
        probe.generate_material_probe(jar, out)
    assert not out.exists()
    out.mkdir()
    marker = out / "preserve.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="已存在"):
        probe.generate_material_probe(jar, out)
    assert marker.read_text() == "keep"


def test_missing_selector_and_changed_property_stop_export(tmp_path, monkeypatch):
    jar = fixture_jar(tmp_path, monkeypatch, missing_selector="facing=north,pos=middle,ypos=middle")
    with pytest.raises(ValueError, match="缺少资源证据"):
        probe.generate_material_probe(jar, tmp_path / "missing")
    assert not (tmp_path / "missing").exists()
    jar = fixture_jar(tmp_path, monkeypatch, window_solid=True)
    with pytest.raises(ValueError, match="含水状态"):
        probe.generate_material_probe(jar, tmp_path / "changed")


def test_cli_probe_path(tmp_path, monkeypatch, capsys):
    from minijapan.cli import main

    jar = fixture_jar(tmp_path, monkeypatch)
    main(["material-probe", "--jar", str(jar), "--out", str(tmp_path / "probe")])
    assert json.loads(capsys.readouterr().out)["cases"] == 11

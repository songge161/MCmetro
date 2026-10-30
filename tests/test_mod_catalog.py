import hashlib
import json
from zipfile import ZipFile

import pytest

from minijapan.mod_catalog import inspect_mod


def fixture_jar(path, extra=None):
    entries = {
        "fabric.mod.json": {"id": "sample", "version": "1.0", "depends": {"minecraft": "1.20.1"}},
        "assets/sample/lang/zh_cn.json": {"block.sample.window": "测试窗"},
        "assets/sample/blockstates/window.json": {
            "variants": {"facing=north": {"model": "sample:block/window"}}
        },
        "assets/sample/blockstates/unknown.json": {
            "multipart": [{"apply": {"model": "sample:block/unknown"}}]
        },
    }
    entries.update(extra or {})
    with ZipFile(path, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, json.dumps(value))


def test_static_catalog_is_deterministic_and_not_a_registry(tmp_path):
    jar = tmp_path / "mod.jar"
    fixture_jar(jar)
    expected = hashlib.sha512(jar.read_bytes()).hexdigest()
    out = tmp_path / "catalog.json"
    summary = inspect_mod(jar, out, expected)
    assert summary == {"candidate_count": 2, "named_candidate_count": 1, "runtime_verified": False}
    data = json.loads(out.read_text())
    assert data["source"]["publisher_hash_verified"]
    assert data["candidates"][1]["name_zh_cn"] == "测试窗"
    assert data["candidates"][1]["variant_selectors"] == ["facing=north"]
    assert data["candidates"][0]["has_multipart"]
    other = tmp_path / "again.json"
    inspect_mod(jar, other, expected)
    assert out.read_bytes() == other.read_bytes()


def test_wrong_hash_and_existing_output_do_not_write(tmp_path):
    jar = tmp_path / "mod.jar"
    fixture_jar(jar)
    out = tmp_path / "catalog.json"
    with pytest.raises(ValueError, match="SHA512"):
        inspect_mod(jar, out, "0" * 128)
    assert not out.exists()
    out.write_text("preserve")
    with pytest.raises(ValueError, match="已存在"):
        inspect_mod(jar, out)
    assert out.read_text() == "preserve"


def test_invalid_jar_and_oversized_resources_are_rejected(tmp_path, monkeypatch):
    jar = tmp_path / "mod.jar"
    jar.write_bytes(b"not a jar")
    out = tmp_path / "catalog.json"
    with pytest.raises(ValueError, match="无法读取"):
        inspect_mod(jar, out)
    fixture_jar(jar)
    monkeypatch.setattr("minijapan.mod_catalog.MAX_JSON_BYTES", 10)
    with pytest.raises(ValueError, match="读取限制"):
        inspect_mod(jar, out)
    assert not out.exists()


def test_non_fabric_jar_is_explicitly_unsupported(tmp_path):
    jar = tmp_path / "mod.jar"
    with ZipFile(jar, "w") as archive:
        archive.writestr("readme.txt", "fixture")
    with pytest.raises(ValueError, match="Fabric"):
        inspect_mod(jar, tmp_path / "catalog.json")


def test_cli_dispatch_and_hash_error_are_structured(tmp_path, capsys):
    from minijapan.cli import main

    jar, out = tmp_path / "mod.jar", tmp_path / "catalog.json"
    fixture_jar(jar)
    main(["inspect-mod", "--jar", str(jar), "--out", str(out)])
    assert json.loads(capsys.readouterr().out)["candidate_count"] == 2
    with pytest.raises(SystemExit) as error:
        main(
            [
                "inspect-mod",
                "--jar",
                str(jar),
                "--out",
                str(tmp_path / "bad.json"),
                "--sha512",
                "bad",
            ]
        )
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().err)["status"] == "invalid"


def test_duplicate_paths_and_invalid_variants_are_rejected(tmp_path):
    jar, out = tmp_path / "mod.jar", tmp_path / "catalog.json"
    fixture_jar(jar)
    with ZipFile(jar, "a") as archive:
        with pytest.warns(UserWarning, match="Duplicate"):
            archive.writestr("fabric.mod.json", "{}")
    with pytest.raises(ValueError, match="重名"):
        inspect_mod(jar, out)
    fixture_jar(jar, {"assets/sample/blockstates/bad.json": {"variants": []}})
    with pytest.raises(ValueError, match="variants"):
        inspect_mod(jar, out)
    assert not out.exists()

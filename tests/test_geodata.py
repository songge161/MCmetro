import json

import pytest

from minijapan.geodata import fetch_area, load_area, normalize


def test_geometry_and_missing_data_are_not_invented():
    points = [
        {"lon": 139.71, "lat": 35.73},
        {"lon": 139.72, "lat": 35.73},
        {"lon": 139.72, "lat": 35.74},
        {"lon": 139.71, "lat": 35.73},
    ]
    payload = {
        "elements": [
            {"type": "way", "id": 1, "tags": {"building": "yes"}, "geometry": points},
            {"type": "way", "id": 2, "tags": {"building": "yes"}, "geometry": points[:3]},
            {"type": "relation", "id": 3, "tags": {"building": "yes"}},
            {"type": "way", "id": 4, "tags": {"highway": "footway"}, "geometry": points[:2]},
        ]
    }
    collection, report = normalize(payload)
    assert [f["id"] for f in collection["features"]] == ["way/1", "way/4"]
    assert collection["features"][0]["geometry"]["coordinates"][0][0] == [139.71, 35.73]
    assert report["buildings_without_height_or_levels"] == 1
    assert len(report["skipped"]) == 2


@pytest.mark.parametrize(
    "payload", [{"elements": []}, {"elements": [], "remark": "runtime error: timeout"}]
)
def test_incomplete_download_is_rejected(payload):
    with pytest.raises(ValueError):
        normalize(payload)


def test_offline_snapshot_preserves_source_and_prevents_overwrite(tmp_path):
    config = tmp_path / "area.yaml"
    config.write_text("id: test\nbbox: [35.72, 139.71, 35.73, 139.72]\n")
    source = tmp_path / "source.json"
    raw = json.dumps(
        {
            "elements": [
                {"type": "node", "id": 1, "lat": 35.72, "lon": 139.71, "tags": {"shop": "yes"}}
            ]
        }
    ).encode()
    source.write_bytes(raw)
    out = tmp_path / "result"
    fetch_area(config, out, source)
    assert (out / "osm.json").read_bytes() == raw
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["mode"] == "offline_reprocess"
    assert manifest["query"] is None
    with pytest.raises(ValueError, match="已存在"):
        fetch_area(config, out, source)


def test_area_rejects_unbounded_query(tmp_path):
    config = tmp_path / "area.yaml"
    config.write_text("id: test\nbbox: [-90, -180, 90, 180]\n")
    with pytest.raises(ValueError):
        load_area(config)

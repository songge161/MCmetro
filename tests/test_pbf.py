import pytest

from minijapan import pbf

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="35.7300" lon="139.7100" version="3" timestamp="2026-01-01T00:00:00Z">
    <tag k="shop" v="convenience"/>
  </node>
  <node id="2" lat="35.7300" lon="139.7100"/>
  <node id="3" lat="35.7300" lon="139.7110"/>
  <node id="4" lat="35.7310" lon="139.7110"/>
  <node id="5" lat="35.7310" lon="139.7100"/>
  <node id="6" lat="35.7300" lon="139.7100"/>
  <way id="10" version="7" timestamp="2026-01-02T00:00:00Z">
    <nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="5"/><nd ref="6"/>
    <tag k="building" v="yes"/>
    <tag k="height" v="12"/>
  </way>
  <way id="11">
    <nd ref="2"/><nd ref="3"/><nd ref="4"/>
    <tag k="building" v="yes"/>
  </way>
  <way id="12">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="footway"/>
  </way>
  <relation id="20">
    <tag k="building" v="yes"/>
  </relation>
</osm>
"""


def test_bbox_argument_uses_osmium_order(tmp_path):
    area = {"bbox": [35.7278, 139.7110, 35.7320, 139.7195]}
    assert pbf.bbox_argument(area) == "139.711,35.7278,139.7195,35.732"


def test_parse_keeps_geometry_and_reports_gaps(tmp_path):
    path = tmp_path / "area.osm"
    path.write_text(SAMPLE_XML, encoding="utf-8")
    collection, report = pbf.parse_osm_xml(path)

    assert [f["id"] for f in collection["features"]] == ["node/1", "way/10", "way/12"]
    assert collection["features"][1]["geometry"]["type"] == "Polygon"
    assert collection["features"][1]["properties"]["osm_version"] == 7
    assert report["building_footprints"] == 1
    assert report["buildings_without_height_or_levels"] == 0
    assert report["counts"] == {"poi": 1, "building": 1, "road": 1}
    skipped = {item["id"]: item["reason"] for item in report["skipped"]}
    assert skipped["way/11"] == "建筑轮廓未闭合"
    assert "关系几何" in skipped["relation/20"]


def test_missing_osmium_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(pbf.shutil, "which", lambda name: None)
    config = tmp_path / "area.yaml"
    config.write_text("id: test\nbbox: [35.72, 139.71, 35.73, 139.72]\n")
    with pytest.raises(ValueError, match="osmium"):
        pbf.extract_area(config, tmp_path / "out", tmp_path / "missing.osm.pbf")


def test_existing_output_directory_is_never_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(pbf.shutil, "which", lambda name: "/usr/bin/osmium")
    config = tmp_path / "area.yaml"
    config.write_text("id: test\nbbox: [35.72, 139.71, 35.73, 139.72]\n")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="已存在"):
        pbf.extract_area(config, out, tmp_path / "any.osm.pbf")

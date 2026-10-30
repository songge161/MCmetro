import json
from zipfile import ZipFile

import nbtlib
import pytest

import minijapan.district as district
from minijapan.district import (
    Projection,
    floors_for,
    generate,
    generate_district,
    raster_polygon,
    stair_core,
    walkable_reach,
)
from minijapan.schematic import Blocks, write_schematic


def fixture_area():
    return {"id": "fixture", "bbox": [35, 139, 35.0004, 139.0006]}


def fixture_collection():
    projection = Projection(fixture_area()["bbox"])

    def coordinate(x, z):
        return [projection.west + x / projection.longitude_scale, projection.north - z / 111_320]

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "way/road",
                "properties": {"kind": "road", "tags": {"highway": "residential"}},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [coordinate(0, 8), coordinate(54, 8)],
                },
            },
            {
                "type": "Feature",
                "id": "way/building",
                "properties": {
                    "kind": "building",
                    "tags": {"building": "yes", "building:levels": "3"},
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            coordinate(x, z)
                            for x, z in [(10, 16), (32, 16), (32, 36), (10, 36), (10, 16)]
                        ]
                    ],
                },
            },
        ],
    }


def test_projection_north_is_negative_z_and_east_is_positive_x():
    projection = Projection(fixture_area()["bbox"])
    assert projection.point([139, 35.0004]) == (0, 0)
    assert projection.point([139.0001, 35.0003])[0] > 0
    assert projection.point([139.0001, 35.0003])[1] > 0


def test_polygon_hole_is_not_filled():
    projection = Projection(fixture_area()["bbox"])
    rings = [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], [(3, 3), (7, 3), (7, 7), (3, 7), (3, 3)]]
    cells = raster_polygon(rings, projection)
    assert len(cells) == 84
    assert (4, 4) not in cells


def test_real_block_output_has_stairs_entrance_and_all_floors_reachable():
    blocks, report, roads, paths = generate(fixture_collection(), fixture_area())
    building = report["buildings"][0]
    assert len(report["buildings"]) == 1
    assert building["floors"] == 3
    assert building["stair_core"]
    assert all(check["passed"] for check in building["floor_checks"])
    assert all(check["reachable_cells"] > 100 for check in building["floor_checks"])
    x, z = building["entrance"]
    assert blocks.get(x, 2, z) == blocks.get(x, 3, z) == 0
    assert paths & roads
    repeated, repeated_report, _, _ = generate(fixture_collection(), fixture_area())
    assert blocks.data == repeated.data
    assert report == repeated_report


def test_underground_roads_are_not_flattened_to_surface():
    collection = fixture_collection()
    collection["features"][0]["properties"]["tags"]["tunnel"] = "yes"
    with pytest.raises(ValueError, match="地面道路"):
        generate(collection, fixture_area())


def test_stairs_rotate_to_fit_narrow_long_interiors():
    assert stair_core({(x, z) for x in range(6) for z in range(8)}) == (2, 1, "z")


def narrow_collection(width, length):
    collection = fixture_collection()
    projection = Projection(fixture_area()["bbox"])
    points = [(10, 16), (10 + width, 16), (10 + width, 16 + length), (10, 16 + length), (10, 16)]
    collection["features"][1]["geometry"]["coordinates"] = [
        [
            [projection.west + x / projection.longitude_scale, projection.north - z / 111_320]
            for x, z in points
        ]
    ]
    return collection


@pytest.mark.parametrize("width,length,axis", [(9, 6, "x"), (6, 9, "z"), (9, 7, "x"), (7, 9, "z")])
def test_single_width_stairs_keep_narrow_buildings_multistorey(width, length, axis):
    blocks, report, _, _ = generate(narrow_collection(width, length), fixture_area())
    building = report["buildings"][0]
    assert building["floors"] == 3
    assert building["stair_width"] == 1
    assert building["stair_core"][2] == axis
    assert building["floor_downgrade_reason"] is None
    assert all(check["passed"] for check in building["floor_checks"])
    stairs = {index for name, index in blocks.palette.items() if "_stairs[" in name}
    assert sum(value in stairs for value in blocks.data) == 10


def test_stair_candidate_retry_checks_actual_geometry(monkeypatch):
    original = district.check_floors
    calls = 0

    def fail_first(*args):
        nonlocal calls
        calls += 1
        checks = original(*args)
        if calls == 1:
            checks[0]["passed"] = False
        return checks

    monkeypatch.setattr(district, "check_floors", fail_first)
    _, report, _, _ = generate(fixture_collection(), fixture_area())
    building = report["buildings"][0]
    assert building["stair_candidates_tested"] == 2
    assert building["floors"] == 3
    assert all(check["passed"] for check in building["floor_checks"])


def test_failed_stairs_downgrade_with_reason_and_clear_old_upper_floors(monkeypatch):
    original = district.check_floors

    def reject_upper_floors(blocks, cells, interior, entrance, floors):
        checks = original(blocks, cells, interior, entrance, floors)
        if floors > 1:
            checks[-1]["passed"] = False
        return checks

    monkeypatch.setattr(district, "check_floors", reject_upper_floors)
    blocks, report, _, _ = generate(narrow_collection(9, 6), fixture_area())
    building = report["buildings"][0]
    assert building["floors"] == 1
    assert building["requested_floors"] == 3
    assert building["floor_downgrade_reason"] == "no_connected_stair_candidate"
    assert all(
        blocks.get(x, y, z) == 0 for x, z in building["footprint"] for y in range(7, blocks.height)
    )


def test_no_fitting_stairs_are_reported_without_inventing_upper_access():
    _, report, _, _ = generate(narrow_collection(6, 6), fixture_area())
    building = report["buildings"][0]
    assert building["floors"] == 1
    assert building["stair_candidates_tested"] == 0
    assert building["floor_downgrade_reason"] == "no_stair_template_fits"


def test_frontage_preserves_entrance_stays_in_footprint_and_respects_residential_use():
    collection = fixture_collection()
    blocks, report, roads, paths = generate(collection, fixture_area())
    building = report["buildings"][0]
    frontage = building["frontage"]
    assert frontage["source"] == "procedural_not_real_shop"
    assert set(frontage["cells"]) <= set(building["footprint"])
    assert len(frontage["cells"]) > 1
    x, z = building["entrance"]
    assert all(blocks.get(x, y, z) == 0 for y in (2, 3, 4))
    assert all(blocks.get(x, 2, z) == blocks.get(x, 3, z) == 0 for x, z in roads | paths)
    assert all(
        blocks.get(x, 5, z) == blocks.palette[frontage["accent"]] for x, z in frontage["cells"]
    )
    collection["features"][1]["properties"]["tags"]["building"] = "apartments"
    _, residential, _, _ = generate(collection, fixture_area())
    assert residential["buildings"][0]["frontage"]["style"] == "residential_windows"


def test_removing_stairs_makes_upper_floors_unreachable():
    blocks, report, _, _ = generate(fixture_collection(), fixture_area())
    building = report["buildings"][0]
    stair_indices = {index for name, index in blocks.palette.items() if "_stairs[" in name}
    for index, value in enumerate(blocks.data):
        if value in stair_indices:
            blocks.data[index] = 0
    entrance_x, entrance_z = building["entrance"]
    reached = walkable_reach(
        blocks, set(map(tuple, building["footprint"])), (entrance_x, 2, entrance_z)
    )
    assert not any(y >= 7 for _, y, _ in reached)


def test_schematic_can_be_decoded_by_independent_nbt_library(tmp_path):
    blocks = Blocks(3, 4, 5)
    blocks.set(2, 3, 4, "minecraft:stone")
    path = tmp_path / "sample.schem"
    write_schematic(blocks, path)
    decoded = nbtlib.load(path)
    assert decoded.root_name == "Schematic"
    assert int(decoded["Version"]) == 2
    assert int(decoded["DataVersion"]) == 3465
    assert [int(decoded[key]) for key in ("Width", "Height", "Length")] == [3, 4, 5]
    data = bytes(int(value) & 255 for value in decoded["BlockData"])
    assert len(data) == 60
    assert data[2 + 4 * 3 + 3 * 3 * 5] == int(decoded["Palette"]["minecraft:stone"])
    assert sum(data) == 1
    repeated = tmp_path / "repeated.schem"
    write_schematic(blocks, repeated)
    assert path.read_bytes() == repeated.read_bytes()


def test_height_inferences_are_explicit():
    assert floors_for({}) == (3, "default_3_floors")
    assert floors_for({"height": "20 m"}) == (5, "height_divided_by_4_estimate")
    assert floors_for({"building:levels": "60"}) == (8, "building:levels")


def test_existing_output_is_preserved_and_outside_coverage_rejected(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(ValueError, match="已存在"):
        generate_district(tmp_path, tmp_path / "unused.yaml", out)
    config = tmp_path / "area.yaml"
    config.write_text("id: fixture\nbbox: [35, 139, 35.0004, 139.0006]\n")
    (tmp_path / "manifest.json").write_text(json.dumps({"area": {"bbox": [36, 140, 37, 141]}}))
    with pytest.raises(ValueError, match="覆盖范围"):
        generate_district(tmp_path, config, tmp_path / "new")


def test_offline_snapshot_to_delivery_package(tmp_path):
    config = tmp_path / "area.yaml"
    config.write_text("id: fixture\nbbox: [35, 139, 35.0004, 139.0006]\n")
    for name, data in (
        ("manifest.json", {"area": fixture_area(), "source": "synthetic_fixture"}),
        ("features.geojson", fixture_collection()),
        ("quality.json", {"skipped": []}),
    ):
        (tmp_path / name).write_text(json.dumps(data))
    out = tmp_path / "generated"
    summary = generate_district(tmp_path, config, out)
    assert summary["buildings"] == summary["multi_storey_buildings"] == 1
    assert not summary["game_import_verified"]
    report = json.loads((out / "district.json").read_text())
    assert report["source"]["manifest"]["source"] == "synthetic_fixture"
    decoded = nbtlib.load(out / "district.schem")
    volume = int(decoded["Width"]) * int(decoded["Height"]) * int(decoded["Length"])
    assert len(decoded["BlockData"]) == volume == sum(report["block_counts"].values())
    assert set(decoded["Palette"]) == set(report["palette"])
    with ZipFile(out / "district-package.zip") as package:
        assert package.testzip() is None
        assert package.read("district.schem") == (out / "district.schem").read_bytes()
        assert "导入说明.md" in package.namelist()
        checklist = package.read("验收清单.md").decode("utf-8")
        assert "way/building" in checklist
        assert "待测" in checklist

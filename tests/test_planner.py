import json
from pathlib import Path

import pytest
import yaml

from minijapan.compression import compress_layout
from minijapan.config import load_config
from minijapan.errors import ConfigurationError
from minijapan.planner import build_plan, write_plan_outputs
from minijapan.validation import validate_plan_shape


def _write_config(tmp_path: Path, sample_path: Path, mutate):
    data = yaml.safe_load(sample_path.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_sample_has_five_stations_and_two_routes(sample_config):
    assert len(sample_config.stations) == 5
    assert len(sample_config.routes) == 2


def test_invalid_coordinate_is_rejected(tmp_path, sample_path):
    path = _write_config(
        tmp_path, sample_path, lambda data: data["stations"][0].update({"x_hint": "nope"})
    )
    with pytest.raises(ConfigurationError, match="x_hint"):
        load_config(path)


def test_duplicate_station_id_is_rejected(tmp_path, sample_path):
    path = _write_config(
        tmp_path, sample_path, lambda data: data["stations"][1].update({"id": "tokyo"})
    )
    with pytest.raises(ConfigurationError, match="duplicate station id"):
        load_config(path)


def test_missing_route_endpoint_is_rejected(tmp_path, sample_path):
    path = _write_config(
        tmp_path, sample_path, lambda data: data["routes"][0]["station_ids"].append("missing")
    )
    with pytest.raises(ConfigurationError, match="unknown station id"):
        load_config(path)


def test_repeated_station_in_route_is_rejected(tmp_path, sample_path):
    path = _write_config(
        tmp_path,
        sample_path,
        lambda data: data["routes"][0].update({"station_ids": ["tokyo", "akihabara", "tokyo"]}),
    )
    with pytest.raises(ConfigurationError, match="cannot repeat"):
        load_config(path)


def test_layout_is_deterministic(sample_config):
    first = compress_layout(sample_config)
    second = compress_layout(sample_config)
    assert first.placements == second.placements
    assert first.issues == second.issues == []


def test_layout_respects_minimum_spacing(sample_config):
    layout = compress_layout(sample_config)
    points = list(layout.placements.values())
    for left_index, left in enumerate(points):
        for right in points[left_index + 1 :]:
            assert ((left.x - right.x) ** 2 + (left.z - right.z) ** 2) ** 0.5 >= 100


def test_layout_respects_world_bounds(sample_config):
    layout = compress_layout(sample_config)
    for placement in layout.placements.values():
        assert sample_config.bounds.contains(placement.x, placement.z)


def test_plan_has_schema_shape(sample_config):
    plan, issues = build_plan(sample_config)
    assert issues == []
    assert validate_plan_shape(plan) == []
    assert plan["source"]["real_data"] is False


def test_plan_contains_geometry_only_rails(sample_config):
    plan, issues = build_plan(sample_config)
    assert issues == []
    assert len(plan["rails"]) == 4
    assert {rail["status"] for rail in plan["rails"]} == {"geometry_only_demo"}


def test_plan_outputs_are_written(tmp_path, sample_config):
    outputs = write_plan_outputs(sample_config, tmp_path / "demo")
    assert set(outputs) == {"plan", "validation", "preview"}
    assert outputs["preview"].read_text(encoding="utf-8").startswith("<svg")
    assert json.loads(outputs["validation"].read_text(encoding="utf-8"))["status"] == "valid"


def test_route_references_are_preserved_in_plan(sample_config):
    plan, issues = build_plan(sample_config)
    assert issues == []
    assert plan["routes"][0]["station_ids"] == ["tokyo", "akihabara", "ueno"]
    assert all(route["requires_verified_mtr_adapter"] for route in plan["routes"])

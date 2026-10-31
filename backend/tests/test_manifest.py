"""sample 抽样规则测试：可重复、数量约束、FNDDS 缺口如实报告。"""
from __future__ import annotations

from backend.app.core.config import load_settings
from backend.app.etl.sample_manifest import (
    build_manifest,
    load_manifest,
    select_foundation,
    select_sr_legacy,
    select_survey,
    write_manifest,
)


def test_foundation_selects_all_real_foods(synthetic_env):
    entry = select_foundation(load_settings())
    assert entry["selected_count"] == 2
    assert entry["ids"] == [1001, 1002]


def test_sr_legacy_caps_per_category_and_is_deterministic(synthetic_env):
    first = select_sr_legacy(load_settings())
    second = select_sr_legacy(load_settings())
    assert first["ids"] == second["ids"]
    assert first["category_breakdown"]["11"] == 12
    assert first["category_breakdown"]["1"] == 1
    assert first["ids"] == sorted(first["ids"])


def test_survey_reports_honest_category_coverage(synthetic_env):
    entry = select_survey(load_settings())
    # 合成数据只有 5 个 ≥5 条的 WWEIA 分类，必须如实报告 5，而不是伪造 100
    assert entry["eligible_categories"] == 5
    assert entry["covered_categories"] == 5
    assert entry["target_categories"] == 100
    assert entry["selected_count"] == 26
    assert 2705383 in entry["ids"]
    assert 2705383 in entry["forced_ids"]
    assert sum(count for code, count in entry["category_breakdown"].items()
               if code != "9602") == 25


def _boundary_ids(items) -> set[int]:
    """边界条目可能是纯 ID 或带证据的字典。"""
    ids: set[int] = set()
    for item in items:
        ids.add(item["fdc_id"] if isinstance(item, dict) else item)
    return ids


def test_branded_boundary_selection(synthetic_env):
    manifest = build_manifest(load_settings(), include_branded=True)
    branded = manifest["sources"]["branded"]
    boundaries = branded["boundaries"]

    gtin_ids = {fid for group in boundaries["gtin_multi_version"] for fid in group["ids"]}
    assert {5001, 5002} <= gtin_ids
    assert {5003, 5006} <= _boundary_ids(boundaries["no_nutrient_records"])
    assert 5004 in _boundary_ids(boundaries["discontinued"])
    assert {5003, 5004} <= _boundary_ids(boundaries["ml_mlt_unit"])
    assert 5005 in _boundary_ids(boundaries["non_mass_unit"])
    assert {5003, 5006} <= _boundary_ids(boundaries["no_brand_category"])
    assert all(item["has_nutrient_records"] is False for item in boundaries["no_nutrient_records"])


def test_manifest_roundtrip_is_stable(synthetic_env):
    settings = load_settings()
    manifest = build_manifest(settings, include_branded=False)
    path = write_manifest(manifest, settings.sample_dir / "manifest.json")
    loaded = load_manifest(path)
    assert loaded["sha256"] == manifest["sha256"]
    assert loaded["sources"]["foundation"]["ids"] == manifest["sources"]["foundation"]["ids"]

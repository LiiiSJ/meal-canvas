"""端到端构建测试：sample 双库、缺失值、能量、中文化、路径隔离。"""
from __future__ import annotations

import sqlite3

import pytest
from backend.app.core.config import load_settings
from backend.app.etl.build import run
from backend.app.etl.sample_manifest import build_manifest, write_manifest


def _manifest(synthetic_env):
    settings = load_settings()
    manifest = build_manifest(settings, include_branded=True)
    return write_manifest(manifest, settings.sample_dir / "manifest.json")


def _query(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_default_library_build(synthetic_env):
    path = _manifest(synthetic_env)
    counts = run(load_settings(), "sample", "default", path, confirm_full=False)
    db_path = load_settings().sample_dir / "meal_canvas.sqlite"
    assert db_path.exists()
    assert counts["sources"]["foundation"]["foods"] == 2

    foods = _query(db_path, "SELECT fdc_id, data_type, name_zh, zh_status, category_zh FROM food")
    ids = {row["fdc_id"] for row in foods}
    assert 1001 in ids and 1002 in ids
    assert 9001 not in ids  # sub_sample_food 不得导入
    assert all(row["data_type"] != "branded_food" for row in foods)

    energy = {row["fdc_id"]: row for row in _query(
        db_path, "SELECT fdc_id, amount, origin_nutrient_id, quality_flag FROM food_nutrient WHERE nutrient_id=1008"
    )}
    assert energy[1001]["amount"] == 34
    assert energy[1001]["origin_nutrient_id"] == 1008
    assert energy[1002]["amount"] == 61
    assert energy[1002]["origin_nutrient_id"] == 2047  # 2048 为空时回退

    carb = _query(
        db_path, "SELECT amount, raw_amount, quality_flag FROM food_nutrient"
        " WHERE fdc_id=1002 AND nutrient_id=1005"
    )[0]
    assert carb["amount"] is None
    assert carb["raw_amount"] == -1.0
    assert carb["quality_flag"] == "negative"

    kj = _query(db_path, "SELECT amount FROM food_nutrient WHERE fdc_id=1002 AND nutrient_id=1062")
    assert kj and kj[0]["amount"] == 255

    summary = _query(db_path, "SELECT energy_kcal FROM food_summary WHERE fdc_id=1002")[0]
    assert summary["energy_kcal"] == 61  # 不是 61 + kJ

    events = {row["event_type"]: row["count"] for row in _query(
        db_path, "SELECT event_type, COUNT(*) count FROM quality_event GROUP BY 1"
    )}
    assert events.get("energy_conflict", 0) >= 1
    assert events.get("duplicate", 0) >= 1
    assert events.get("unmapped_nutrient", 0) >= 1  # 2066 不在白名单

    broccoli = _query(db_path, "SELECT name_zh, zh_status FROM food WHERE fdc_id=1001")[0]
    assert broccoli["name_zh"] == "西兰花"
    assert broccoli["zh_status"] == "glossary"

    assert not synthetic_env["formal_db"].exists()
    assert not synthetic_env["formal_branded"].exists()


def test_branded_library_build(synthetic_env):
    path = _manifest(synthetic_env)
    run(load_settings(), "sample", "default", path, confirm_full=False)
    counts = run(load_settings(), "sample", "branded", path, confirm_full=False)
    settings = load_settings()
    db_path = settings.sample_dir / "meal_canvas_branded.sqlite"
    assert db_path.exists()
    assert counts["sources"]["branded"]["foods"] == 6

    rows = _query(db_path, "SELECT data_type, library_scope, is_default_library, gtin_upc, serving_unit, zh_status FROM food")
    assert {row["data_type"] for row in rows} == {"branded_food"}
    assert all(row["library_scope"] == "branded" and row["is_default_library"] == 0 for row in rows)
    assert all(row["zh_status"] == "none" for row in rows)
    by_id = {row["gtin_upc"]: row for row in rows}
    assert by_id["GTIN-A"]["serving_unit"] == "g"
    assert _query(db_path, "SELECT COUNT(*) c FROM food_portion")[0]["c"] == 0

    no_nutrient = _query(
        db_path, "SELECT COUNT(*) c FROM food_nutrient WHERE fdc_id IN (5003, 5006)"
    )[0]["c"]
    assert no_nutrient == 0

    pending = (settings.sample_dir / "zh_pending_branded.csv")
    assert pending.exists()
    lines = pending.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 7  # 表头 + 6 条品牌商品待核验


def test_full_mode_requires_confirm(synthetic_env):
    path = _manifest(synthetic_env)
    with pytest.raises(RuntimeError):
        run(load_settings(), "full", "default", path, confirm_full=False)

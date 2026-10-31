"""独立补全存储层测试：去重、状态筛选、负缓存、与 USDA 库的独立性。"""
from __future__ import annotations

import sqlite3

import pytest
from backend.app.enrichment.storage import (
    CANDIDATE,
    VERIFIED,
    EnrichStorage,
)


@pytest.fixture()
def storage(tmp_path) -> EnrichStorage:
    return EnrichStorage(tmp_path / "enrich" / "meal_canvas_enrichment.sqlite")


def _add_source(storage: EnrichStorage, external_id: str = "9001", provider: str = "usda_fdc") -> int:
    return storage.upsert_source(
        provider=provider,
        external_id=external_id,
        external_name_en="Egg, white, raw",
        source_url=f"https://example.org/{external_id}",
        match_level="exact",
        match_score=1.0,
        match_evidence={"method": "description"},
        license_note="test",
    )


def test_schema_created_and_independent_file(storage, tmp_path):
    """补全库建立在指定路径，物理上独立于 USDA 库。"""
    assert storage.path.exists()
    assert storage.path.parent == tmp_path / "enrich"
    with sqlite3.connect(storage.path) as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"enrich_source", "enrich_value", "enrich_attempt"} <= tables


def test_source_upsert_dedup(storage):
    """同一 (provider, external_id) 只保留一行。"""
    first = _add_source(storage)
    second = _add_source(storage, "9001")
    assert first == second
    with sqlite3.connect(storage.path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM enrich_source").fetchone()[0]
    assert count == 1


def test_value_upsert_dedup_and_update(storage):
    """同一 (fdc_id, nutrient_key, source_id) 重复写入是更新，不是新增。"""
    source_id = _add_source(storage)
    storage.upsert_value(
        fdc_id=1001, nutrient_key="fiber_g", source_id=source_id,
        original_amount=0.5, original_unit="G", original_basis="per_100g",
        value_per_100g=0.5, conversion_method=None, status=VERIFIED, conflict_note=None,
    )
    storage.upsert_value(
        fdc_id=1001, nutrient_key="fiber_g", source_id=source_id,
        original_amount=0.6, original_unit="G", original_basis="per_100g",
        value_per_100g=0.6, conversion_method=None, status=VERIFIED, conflict_note=None,
    )
    verified = storage.verified_values(1001)
    assert len(verified) == 1
    assert verified[0].value_per_100g == 0.6


def test_values_filtered_by_status(storage):
    source_id = _add_source(storage)
    other_id = _add_source(storage, "9002")
    storage.upsert_value(
        fdc_id=1001, nutrient_key="fiber_g", source_id=source_id,
        original_amount=0.5, original_unit="G", original_basis="per_100g",
        value_per_100g=0.5, conversion_method=None, status=VERIFIED, conflict_note=None,
    )
    storage.upsert_value(
        fdc_id=1001, nutrient_key="sodium_mg", source_id=other_id,
        original_amount=1.0, original_unit="G", original_basis="per_100g",
        value_per_100g=1000.0, conversion_method="×1000（g→mg）", status=CANDIDATE,
        conflict_note="相似食品，待确认",
    )
    assert len(storage.verified_values(1001)) == 1
    assert len(storage.candidate_values(1001)) == 1
    assert storage.verified_values(9999) == []


def test_attempt_negative_cache_ordering(storage):
    """最新一次检索可读取；freshness 按 TTL 判断。"""
    storage.record_attempt(fdc_id=1001, missing_keys=["fiber_g"], outcome="not_found", detail=None)
    storage.record_attempt(fdc_id=1001, missing_keys=["fiber_g", "sodium_mg"], outcome="error", detail="网络错误")
    latest = storage.latest_attempt(1001)
    assert latest is not None
    assert latest.outcome == "error"
    assert set(latest.missing_keys) == {"fiber_g", "sodium_mg"}
    assert storage.attempt_is_fresh(latest, ttl_minutes=10) is True
    assert storage.attempt_is_fresh(latest, ttl_minutes=0.0001) is False
    assert storage.latest_attempt(8888) is None


def test_storage_does_not_touch_usda_db(storage, tmp_path):
    """向补全库写入后，USDA sample 库文件字节不变。"""
    from pathlib import Path

    usda = Path(__file__).resolve().parents[2] / "data" / "build" / "sample" / "meal_canvas.sqlite"
    if not usda.is_file():
        pytest.skip("sample 库不存在，跳过只读断言")
    before = usda.read_bytes()
    source_id = _add_source(storage)
    storage.upsert_value(
        fdc_id=1001, nutrient_key="fiber_g", source_id=source_id,
        original_amount=1, original_unit="G", original_basis="per_100g",
        value_per_100g=1.0, conversion_method=None, status=VERIFIED, conflict_note=None,
    )
    assert usda.read_bytes() == before

"""补全 API 集成测试：真实 sample 库 + 模拟外部服务。

- USDA sample 库全程只读（文件字节不变）。
- 补全库写入 tmp_path，与 USDA 库物理独立。
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import httpx
import pytest
from backend.app.enrichment.mapper import ALL_NUTRIENT_KEYS
from backend.app.enrichment.service import EnrichmentService, set_service
from fastapi.testclient import TestClient
from test_enrichment_service import fdc_food, fdc_search_response, make_settings, nut

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas.sqlite"
BRANDED_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas_branded.sqlite"
USAGE_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas_usage.sqlite"

pytestmark = pytest.mark.skipif(
    not SAMPLE_DB.is_file(), reason="sample 数据库未构建",
)


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("MEAL_CANVAS_ENRICH_DB_PATH", str(tmp_path / "enrich.sqlite"))
    from backend.app.api import db as dbmod
    from backend.app.api import main as main_mod
    dbmod.set_db_paths(SAMPLE_DB, BRANDED_DB, USAGE_DB)
    client = TestClient(main_mod.app)
    yield client, tmp_path
    set_service(None)
    monkeypatch.delenv("MEAL_CANVAS_ENRICH_DB_PATH", raising=False)


def _pick_food_with_missing(*, missing_key: str = "fiber_g", require_key: str = "protein_g") -> tuple[int, str]:
    with sqlite3.connect(SAMPLE_DB) as conn:
        row = conn.execute(
            f"SELECT f.fdc_id, f.description_en FROM food f JOIN food_summary s ON s.fdc_id = f.fdc_id "
            f"WHERE s.{missing_key} IS NULL AND s.{require_key} IS NOT NULL "
            f"AND f.library_scope = 'default' ORDER BY f.fdc_id ASC LIMIT 1"
        ).fetchone()
    assert row is not None
    return int(row[0]), str(row[1])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resolved_disabled_shape_and_usda_readonly(api):
    client, tmp_path = api
    set_service(EnrichmentService(
        make_settings(tmp_path, fdc_key=None, off_enabled=False),
        db_path=tmp_path / "enrich.sqlite",
    ))
    fdc_id, _desc = _pick_food_with_missing()

    before = _sha(SAMPLE_DB)
    r = client.get(f"/api/enrichment/foods/{fdc_id}/resolved")
    after = _sha(SAMPLE_DB)
    assert r.status_code == 200, r.text
    assert before == after  # USDA 库只读保护仍然有效

    data = r.json()
    assert data["fdc_id"] == fdc_id
    assert data["baseline"] == "每 100 克"
    # 检查范围覆盖 nutrient 元数据表全部 37 项营养素，不止核心 7 项
    assert {v["key"] for v in data["values"]} == set(ALL_NUTRIENT_KEYS)
    assert len(data["values"]) == 37
    assert "fiber_g" in data["missing_keys"]
    assert data["enrichment"]["outcome"] in ("disabled", "not_found", "error")
    for value in data["values"]:
        if value["origin"] == "usda":
            assert value["value"] is not None
        if value["origin"] == "none":
            assert value["value"] is None
        # 每项都附带 nutrient 元数据，供前端渲染非核心补全行
        assert "nutrient_id" in value
        assert "name_zh" in value
        assert "unit_zh" in value
        assert "decimals" in value
    # 补全库独立存在
    assert (tmp_path / "enrich.sqlite").is_file()


def test_resolved_404_for_unknown_food(api):
    client, tmp_path = api
    set_service(EnrichmentService(
        make_settings(tmp_path, fdc_key=None, off_enabled=False),
        db_path=tmp_path / "enrich.sqlite",
    ))
    r = client.get("/api/enrichment/foods/999999999/resolved")
    assert r.status_code == 404
    body = r.json()
    assert "未找到" in body["detail"]["message"]


def test_resolved_usda_values_match_same_food_detail(api):
    """食品 ID、英文名与 USDA 原始营养值必须指向同一条食品记录。"""
    client, tmp_path = api
    set_service(EnrichmentService(
        make_settings(tmp_path, fdc_key=None, off_enabled=False),
        db_path=tmp_path / "enrich.sqlite",
    ))
    fdc_id, description = _pick_food_with_missing()

    detail = client.get(f"/api/foods/{fdc_id}")
    assert detail.status_code == 200, detail.text
    food = detail.json()
    resolved = client.get(f"/api/enrichment/foods/{fdc_id}/resolved")
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()

    assert data["fdc_id"] == food["fdc_id"] == fdc_id
    assert food["description_en"] == description
    assert data["display_name"] == food["display_name"]
    summary = food["summary_per_100g"]
    by_key = {v["key"]: v for v in data["values"]}
    for key, item in by_key.items():
        if item["origin"] != "usda":
            continue
        if key not in summary:
            continue  # 非核心营养素不在 summary 中，跳过逐项比对
        assert item["value"] == summary[key], f"{key} 与食品详情不一致"
        assert item["usda_value"] == summary[key]
        assert item["source_name"] is None  # 原始值不得伪装成外部来源


def test_resolved_enriches_via_mocked_fdc(api):
    """API 全链路：缺失项通过（模拟的）USDA FDC exact 匹配补全。

    检查范围为全部 37 项营养素，mock 只提供 7 项核心值，
    因此整体结果为 partial（部分补全），其余缺失项保持未知。
    """
    client, tmp_path = api
    fdc_id, description = _pick_food_with_missing()

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        return fdc_search_response([
            fdc_food(9001, query, [
                nut(1008, "Energy", "KCAL", 34),
                nut(1003, "Protein", "G", 10.9),
                nut(1004, "Total lipid (fat)", "G", 0.2),
                nut(1005, "Carbohydrate, by difference", "G", 0.7),
                nut(1079, "Fiber, total dietary", "G", 0.42),
                nut(2000, "Total Sugars", "G", 0.7),
                nut(1093, "Sodium, Na", "MG", 166),
            ])
        ])

    settings = make_settings(tmp_path)
    service = EnrichmentService(settings, db_path=tmp_path / "enrich.sqlite",
                                transport=httpx.MockTransport(handler))
    set_service(service)

    before = _sha(SAMPLE_DB)
    r = client.get(f"/api/enrichment/foods/{fdc_id}/resolved")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enrichment"]["outcome"] == "partial", data["enrichment"]
    assert data["enrichment"]["attempted"] is True
    by_key = {v["key"]: v for v in data["values"]}
    assert by_key["fiber_g"]["origin"] == "external"
    assert by_key["fiber_g"]["status"] == "verified_external"
    assert by_key["fiber_g"]["value"] == 0.42
    assert by_key["fiber_g"]["source_name"] == "usda_fdc"
    assert by_key["fiber_g"]["source_url"]
    assert by_key["fiber_g"]["name_zh"]  # 附带 nutrient 元数据
    assert _sha(SAMPLE_DB) == before  # USDA 库未被写入

    # 缓存命中：第二次 GET 命中 partial 负缓存，不再外呼
    r2 = client.get(f"/api/enrichment/foods/{fdc_id}/resolved")
    data2 = r2.json()
    assert data2["enrichment"]["outcome"] == "partial"
    assert data2["enrichment"]["attempted"] is False
    by_key2 = {v["key"]: v for v in data2["values"]}
    assert by_key2["fiber_g"]["origin"] == "external"
    assert by_key2["fiber_g"]["value"] == 0.42

    # POST refresh：强制重查仍只能补到 mock 提供的核心项，结果保持 partial
    r3 = client.post(f"/api/enrichment/foods/{fdc_id}/refresh")
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["enrichment"]["outcome"] == "partial"
    assert data3["enrichment"]["attempted"] is True
    assert _sha(SAMPLE_DB) == before

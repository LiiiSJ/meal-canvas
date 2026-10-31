"""补全服务端到端测试（httpx.MockTransport 模拟外部服务，不发真实网络请求）。

覆盖任务要求的场景：不覆盖已有值、缺失补全、身份不匹配不采纳、生熟不混、
单位/基准不明不进计算、缺失与零值区分、冲突保留、失败保留原数据、缓存去重、
并发隔离、禁用降级、不伪造成功。
"""
from __future__ import annotations

import threading

import httpx
from backend.app.enrichment.config import EnrichSettings
from backend.app.enrichment.identity import LocalFood
from backend.app.enrichment.service import EnrichmentService
from backend.app.enrichment.storage import VERIFIED, EnrichStorage

EGG = LocalFood(fdc_id=1001, description_en="Egg, white, raw", data_type="foundation_food")
LOCALS = {
    1001: EGG,
    1002: LocalFood(fdc_id=1002, description_en="Milk, whole, raw", data_type="foundation_food"),
}


def make_settings(tmp_path, *, enabled=True, fdc_key="TEST_KEY", fdc_enabled=True,
                  off_enabled=True, max_retries=0) -> EnrichSettings:
    return EnrichSettings(
        enabled=enabled,
        db_path=tmp_path / "enrich.sqlite",
        fdc_api_key=fdc_key,
        fdc_enabled=fdc_enabled,
        off_enabled=off_enabled,
        timeout_seconds=1.0,
        max_retries=max_retries,
        off_min_interval=0.0,
        fdc_min_interval=0.0,
        negative_ttl_minutes=24 * 60,
        error_ttl_minutes=10,
        max_candidates=5,
    )


def base_summary(**overrides) -> dict[str, float | None]:
    summary: dict[str, float | None] = {
        "energy_kcal": None, "protein_g": None, "fat_g": None, "carb_g": None,
        "fiber_g": None, "sugar_g": None, "sodium_mg": None,
    }
    summary.update(overrides)
    return summary


def fdc_search_response(foods: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"foods": foods})


def fdc_food(fdc_id: int, description: str, nutrients: list[dict]) -> dict:
    return {"fdcId": fdc_id, "description": description, "foodNutrients": nutrients}


def nut(nid: int, name: str, unit: str, value: float) -> dict:
    return {"nutrientId": nid, "nutrientName": name, "unitName": unit, "value": value}


class Router:
    """按 URL 分发的模拟外部服务；记录请求数便于缓存断言。"""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.fdc_foods: list[dict] = []
        self.off_product: dict | None = None
        self.off_products: list[dict] = []
        self.fail_all = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.fail_all:
            raise httpx.ConnectError("模拟网络不可用", request=request)
        url = str(request.url)
        if "api.nal.usda.gov" in url:
            return fdc_search_response(self.fdc_foods)
        if "/api/v2/product/" in url:
            if self.off_product is None:
                return httpx.Response(404, json={"status": 0})
            return httpx.Response(200, json={"status": 1, "product": self.off_product})
        if "/api/v2/search" in url:
            return httpx.Response(200, json={"count": len(self.off_products), "products": self.off_products})
        raise AssertionError(f"意外请求：{url}")


def make_service(tmp_path, router: Router, **settings_kw) -> EnrichmentService:
    settings = make_settings(tmp_path, **settings_kw)
    return EnrichmentService(settings, db_path=tmp_path / "enrich.sqlite",
                             transport=httpx.MockTransport(router))


# ---------------------------------------------------------------- 场景


def test_usda_value_not_overwritten_and_missing_filled(tmp_path):
    """已有蛋白质不被覆盖；缺失纤维只补纤维；其余仍缺失 → partial。"""
    router = Router()
    router.fdc_foods = [fdc_food(9001, "Egg, white, raw", [
        nut(1079, "Fiber, total dietary", "G", 0.5),
        nut(1003, "Protein", "G", 99.0),
    ])]
    service = make_service(tmp_path, router)
    summary = base_summary(protein_g=2.8)
    result = service.resolve(EGG, summary)

    assert result.outcome == "partial"
    assert "已补全 1 项" in (result.message or "")
    by_key = {v.key: v for v in result.values}
    assert by_key["protein_g"].origin == "usda"
    assert by_key["protein_g"].value == 2.8
    assert by_key["fiber_g"].origin == "external"
    assert by_key["fiber_g"].status == "verified_external"
    assert by_key["fiber_g"].value == 0.5
    assert by_key["fiber_g"].source_url.startswith("https://fdc.nal.usda.gov")
    # partial 结果也进负缓存：再次 resolve 不重复外呼
    calls = len(router.calls)
    second = service.resolve(EGG, summary)
    assert second.outcome == "partial"
    assert second.attempted is False
    assert len(router.calls) == calls


def test_mismatched_identity_not_adopted(tmp_path):
    """名称完全无重叠的外部记录不得采用。"""
    router = Router()
    router.fdc_foods = [fdc_food(9002, "Beef, chuck, braised", [
        nut(1079, "Fiber, total dietary", "G", 3.0),
    ])]
    service = make_service(tmp_path, router)
    result = service.resolve(EGG, base_summary(fiber_g=None))
    assert result.outcome == "not_found"
    by_key = {v.key: v for v in result.values}
    assert by_key["fiber_g"].origin == "none"
    assert by_key["fiber_g"].value is None
    assert service.storage.verified_values(EGG.fdc_id) == []


def test_state_conflict_not_adopted_but_stored_as_candidate(tmp_path):
    """raw vs dried：状态不同，不自动采用，保留为候选。"""
    router = Router()
    router.fdc_foods = [fdc_food(9003, "Egg, white, dried", [
        nut(1079, "Fiber, total dietary", "G", 3.0),
    ])]
    service = make_service(tmp_path, router)
    result = service.resolve(EGG, base_summary(fiber_g=None))
    assert result.outcome == "not_found"
    by_key = {v.key: v for v in result.values}
    assert by_key["fiber_g"].origin == "none"
    candidates = service.storage.candidate_values(EGG.fdc_id)
    assert len(candidates) == 1
    assert candidates[0].source.match_level == "similar"
    assert result.candidates and result.candidates[0].match_level == "similar"


def test_conflicting_sources_stay_candidate(tmp_path):
    """两个来源数值冲突：全部保留为候选，不静默挑选。"""
    router = Router()
    router.fdc_foods = [fdc_food(9001, "Egg, white, raw", [
        nut(1079, "Fiber, total dietary", "G", 0.5),
    ])]
    router.off_products = [{
        "code": "9000001", "product_name": "Egg, white, raw",
        "nutriments": {"fiber_100g": 2.6},
    }]
    service = make_service(tmp_path, router)
    result = service.resolve(EGG, base_summary(fiber_g=None))
    by_key = {v.key: v for v in result.values}
    assert by_key["fiber_g"].origin == "none"
    assert service.storage.verified_values(EGG.fdc_id) == []
    candidates = service.storage.candidate_values(EGG.fdc_id)
    assert len(candidates) == 2
    assert all(c.conflict_note and "冲突" in c.conflict_note for c in candidates)


def test_unit_unknown_never_enters_calculation(tmp_path):
    router = Router()
    router.fdc_foods = [fdc_food(9001, "Egg, white, raw", [
        nut(1093, "Sodium, Na", "PPM", 166),
    ])]
    service = make_service(tmp_path, router)
    result = service.resolve(EGG, base_summary(sodium_mg=None))
    assert result.outcome == "not_found"
    by_key = {v.key: v for v in result.values}
    assert by_key["sodium_mg"].origin == "none"


def test_real_zero_distinct_from_missing(tmp_path):
    """外部明确 0 是真实零值（采纳为 0）；已有 0 不视为缺失。"""
    router = Router()
    router.off_product = {
        "code": "3017620422003", "product_name": "Liquid egg white",
        "nutriments": {"fiber_100g": 0, "proteins_100g": 11.0},
    }
    local = LocalFood(fdc_id=5001, description_en="Liquid egg white", data_type="branded_food",
                      gtin_upc="3017620422003")
    service = make_service(tmp_path, router)
    result = service.resolve(local, base_summary(protein_g=11.0))
    by_key = {v.key: v for v in result.values}
    assert by_key["fiber_g"].origin == "external"
    assert by_key["fiber_g"].value == 0.0
    # protein 已有有效值 11.0 → 不缺失、不被 11.0 之外来源覆盖
    assert by_key["protein_g"].origin == "usda"
    assert "protein_g" not in result.missing_keys
    # carb 保持缺失
    assert by_key["carb_g"].origin == "none"
    assert "carb_g" in result.missing_keys


def test_negative_cache_avoids_repeat_requests(tmp_path):
    """not_found 负缓存：第二次 resolve 不再外呼；force 才会重查。"""
    router = Router()
    service = make_service(tmp_path, router)
    first = service.resolve(EGG, base_summary(fiber_g=None))
    assert first.outcome == "not_found"
    assert first.attempted is True
    calls_after_first = len(router.calls)

    second = service.resolve(EGG, base_summary(fiber_g=None))
    assert second.outcome == "not_found"
    assert second.attempted is False
    assert len(router.calls) == calls_after_first

    forced = service.resolve(EGG, base_summary(fiber_g=None), force=True)
    assert forced.attempted is True
    assert len(router.calls) > calls_after_first


def test_cached_verified_reused_without_network(tmp_path):
    """全部缺失项补全后：第二次 resolve 命中缓存，不再发请求。"""
    router = Router()
    router.fdc_foods = [fdc_food(9001, "Egg, white, raw", [
        nut(1008, "Energy", "KCAL", 34),
        nut(1003, "Protein", "G", 10.9),
        nut(1004, "Total lipid (fat)", "G", 0.2),
        nut(1005, "Carbohydrate, by difference", "G", 0.7),
        nut(1079, "Fiber, total dietary", "G", 0.5),
        nut(2000, "Total Sugars", "G", 0.7),
        nut(1093, "Sodium, Na", "MG", 166),
    ])]
    service = make_service(tmp_path, router)
    first = service.resolve(EGG, base_summary(fiber_g=None))
    assert first.outcome == "enriched"
    calls = len(router.calls)

    second = service.resolve(EGG, base_summary(fiber_g=None))
    assert second.outcome == "cached"
    assert second.attempted is False
    assert len(router.calls) == calls
    by_key = {v.key: v for v in second.values}
    assert by_key["fiber_g"].origin == "external"
    assert by_key["fiber_g"].value == 0.5
    assert by_key["protein_g"].origin == "external"


def test_error_keeps_original_and_prior_verified(tmp_path):
    """外部服务不可用：outcome=error，原始数据与此前 verified 补全都保留。"""
    router = Router()
    router.fail_all = True
    settings = make_settings(tmp_path)
    storage = EnrichStorage(tmp_path / "enrich.sqlite")
    source_id = storage.upsert_source(
        provider="usda_fdc", external_id="9001", external_name_en="Egg, white, raw",
        source_url="https://example.org", match_level="exact", match_score=1.0,
        match_evidence={}, license_note="test",
    )
    storage.upsert_value(
        fdc_id=EGG.fdc_id, nutrient_key="fiber_g", source_id=source_id,
        original_amount=1.0, original_unit="G", original_basis="per_100g",
        value_per_100g=1.0, conversion_method=None, status=VERIFIED, conflict_note=None,
    )
    service = EnrichmentService(settings, db_path=tmp_path / "enrich.sqlite",
                                transport=httpx.MockTransport(router))
    result = service.resolve(EGG, base_summary(fiber_g=None, sodium_mg=None))
    assert result.outcome == "error"
    by_key = {v.key: v for v in result.values}
    assert by_key["fiber_g"].origin == "external"
    assert by_key["fiber_g"].value == 1.0
    assert by_key["sodium_mg"].origin == "none"


def test_disabled_reports_reason_and_never_calls_network(tmp_path):
    router = Router()
    service = make_service(tmp_path, router, fdc_key=None, off_enabled=False)
    result = service.resolve(EGG, base_summary(fiber_g=None))
    assert result.outcome == "disabled"
    assert len(router.calls) == 0
    status = {item["name"]: item for item in result.provider_status}
    assert status["usda_fdc"]["enabled"] is False
    assert "MEAL_CANVAS_FDC_API_KEY" in (status["usda_fdc"]["reason"] or "")
    assert status["openfoodfacts"]["enabled"] is False


def test_off_gtin_sodium_conversion_enriched(tmp_path):
    """品牌商品按 GTIN 精确匹配；sodium g→mg 显式换算后补全。"""
    router = Router()
    router.off_product = {
        "code": "3017620422003", "product_name": "Chocolate spread",
        "nutriments": {"sodium_100g": 0.0428, "sodium_unit": "g"},
    }
    local = LocalFood(fdc_id=5001, description_en="Chocolate spread", data_type="branded_food",
                      gtin_upc="3017620422003")
    service = make_service(tmp_path, router, fdc_enabled=False)
    result = service.resolve(local, base_summary(sodium_mg=None))
    # 候选只含钠 → 只补钠，其余仍缺失 → partial
    assert result.outcome == "partial"
    by_key = {v.key: v for v in result.values}
    assert by_key["sodium_mg"].origin == "external"
    assert abs(by_key["sodium_mg"].value - 42.8) < 1e-9
    assert by_key["sodium_mg"].source_name == "openfoodfacts"
    assert "×1000" in (by_key["sodium_mg"].conversion_method or "")


def test_concurrent_resolves_do_not_cross_write(tmp_path):
    """两个食品并发检索：各自只补自己的缺失项，互不覆盖。"""
    router = Router()

    def handler(request: httpx.Request) -> httpx.Response:
        router.calls.append(request)
        query = request.url.params.get("query", "")
        if "Egg" in query:
            return fdc_search_response([fdc_food(9001, "Egg, white, raw", [
                nut(1079, "Fiber, total dietary", "G", 0.5)])])
        return fdc_search_response([fdc_food(9002, "Milk, whole, raw", [
            nut(1093, "Sodium, Na", "MG", 43.0)])])

    service = EnrichmentService(make_settings(tmp_path), db_path=tmp_path / "enrich.sqlite",
                                transport=httpx.MockTransport(handler))
    barrier = threading.Barrier(2)
    results: dict[int, object] = {}

    def run(fdc_id: int, key: str) -> None:
        barrier.wait()
        results[fdc_id] = service.resolve(
            LOCALS[fdc_id], base_summary(**{key: None})
        )

    t1 = threading.Thread(target=run, args=(1001, "fiber_g"))
    t2 = threading.Thread(target=run, args=(1002, "sodium_mg"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    r1, r2 = results[1001], results[1002]
    v1 = {v.key: v for v in r1.values}
    v2 = {v.key: v for v in r2.values}
    assert v1["fiber_g"].origin == "external"
    assert v1["sodium_mg"].origin == "none"
    assert v2["sodium_mg"].origin == "external"
    assert v2["fiber_g"].origin == "none"
    assert len(service.storage.verified_values(1001)) == 1
    assert len(service.storage.verified_values(1002)) == 1

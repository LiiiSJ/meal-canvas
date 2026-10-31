"""后端 API 集成测试：全部使用真实 sample 数据库。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas.sqlite"
BRANDED_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas_branded.sqlite"
USAGE_DB = PROJECT_ROOT / "data" / "build" / "sample" / "meal_canvas_usage.sqlite"

# sample DB 真实计数（每次重建后可能变化，health 测试应直接 assert 非 None 而不是硬编码）
# food: 1285
# food_nutrient: 34395


def _reset_api_modules():
    to_remove = [k for k in sys.modules if k.startswith("backend.app.api")]
    for k in to_remove:
        sys.modules.pop(k, None)


@pytest.fixture(scope="session")
def client():
    """TestClient，db 已指向 sample DB。session 级别只构建一次。"""
    _reset_api_modules()
    # main.py 顶层会先调 db.set_db_paths(load_api_settings()...)
    # 我们在 import main 之后覆盖 db paths，确保用 sample DB
    from backend.app.api import db as dbmod
    from backend.app.api import main as main_mod
    dbmod.set_db_paths(SAMPLE_DB, BRANDED_DB, USAGE_DB)
    return TestClient(main_mod.app)


@pytest.fixture()
def missing_db_client(tmp_path):
    """指向不存在数据库的 TestClient。health 返回 degraded 200；connect() 抛 DatabaseUnavailableError → 503。"""
    missing = tmp_path / "does_not_exist.sqlite"
    _reset_api_modules()
    from backend.app.api import db as dbmod
    from backend.app.api import main as main_mod
    # 覆盖 main.py 顶层设置的默认路径
    dbmod.set_db_paths(missing, missing)
    return TestClient(main_mod.app)


# ----------------------------------------------------------------------- 测试


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["default_db_exists"] is True
    assert data["branded_db_exists"] is True
    assert data["food_count"] == 1285
    assert data["nutrient_row_count"] == 34395


def test_health_db_degraded_when_missing(missing_db_client):
    """health 路由在 db 文件不存在时返回 degraded（不是 503），但 error 字段明确。"""
    r = missing_db_client.get("/api/health")
    # 当前实现：db 文件不存在 → status="degraded", default_db_exists=False, error 含中文说明
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "degraded"
    assert data["default_db_exists"] is False
    assert "数据库不存在" in (data.get("error") or "")


def test_list_foods_default_pagination(client):
    r = client.get("/api/foods")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == _usage_count()
    assert data["usage_scope"] == "ingredients"
    assert len(data["items"]) == 20
    for item in data["items"]:
        assert "fdc_id" in item
        assert "display_name" in item
        assert "zh_status" in item
        assert item["usage_class"] in {"basic_ingredient", "processed_ingredient"}


def test_list_foods_page_size_default_5(client):
    """验证 page_size=5 返回 5 条。"""
    r = client.get("/api/foods", params={"page_size": 5})
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 5


def test_list_foods_chinese_search(client):
    r = client.get("/api/foods", params={"q": "鸡蛋"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    ids = {it["fdc_id"] for it in data["items"]}
    assert 748967 in ids  # Eggs, Grade A, Large, egg whole


def test_list_foods_english_search(client):
    r = client.get("/api/foods", params={"q": "broccoli"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    ids = {it["fdc_id"] for it in data["items"]}
    assert 747447 in ids  # Broccoli, raw


def test_list_foods_alias_search(client):
    r = client.get("/api/foods", params={"q": "白米饭"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1


def test_list_foods_category_filter(client):
    r = client.get("/api/foods", params={"category_code": "11"})  # Vegetables
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 5
    for item in data["items"]:
        assert item["category_code"] == "11"


def test_list_foods_data_type_filter(client):
    # 用途默认口径只含烹饪原料，因此显式放宽到 all 才能核对 data_type 全量
    r = client.get(
        "/api/foods", params={"data_type": "foundation_food", "usage_scope": "all"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 469
    for item in data["items"]:
        assert item["data_type"] == "foundation_food"


def test_get_food_by_fdc_id(client):
    r = client.get("/api/foods/748967")
    assert r.status_code == 200
    data = r.json()
    assert data["fdc_id"] == 748967
    assert data["name_zh"] == "A级大鸡蛋（全蛋）"
    assert data["display_name"] == "A级大鸡蛋（全蛋）"
    assert data["portions"] is not None
    assert data["summary_per_100g"] is not None


def test_get_food_not_found(client):
    r = client.get("/api/foods/99999999")
    assert r.status_code == 404, r.text
    body = r.json()
    detail = body.get("detail", body)
    code = detail["code"] if isinstance(detail, dict) else None
    assert code == "NOT_FOUND", body


def test_get_food_nutrients_missing_vs_zero(client):
    import sqlite3

    conn = sqlite3.connect(str(SAMPLE_DB))
    conn.row_factory = sqlite3.Row
    negative_row = conn.execute(
        "SELECT fdc_id FROM food_nutrient WHERE quality_flag='negative' LIMIT 1"
    ).fetchone()
    assert negative_row is not None, "sample DB 必须有 negative 营养行"
    fid = negative_row["fdc_id"]
    conn.close()

    r = client.get(f"/api/foods/{fid}/nutrients")
    assert r.status_code == 200
    data = r.json()
    negative_items = [n for n in data["nutrients"] if n["quality_flag"] == "negative"]
    assert negative_items, f"fdc_id={fid} 必须有 negative 营养行"
    assert negative_items[0]["amount"] is None, "negative 行的 amount 必须是 null，不能是 0"
    assert negative_items[0]["is_available"] is False

    ok_items = [n for n in data["nutrients"] if n["quality_flag"] == "ok"]
    assert ok_items, f"fdc_id={fid} 必须有至少 1 行 ok"
    for n in ok_items:
        if n["amount"] == 0:
            assert n["is_available"] is True, f"amount=0 但 is_available=False: {n}"
        elif n["amount"] is not None:
            assert n["is_available"] is True
        else:
            raise AssertionError(f"ok 行却 amount=null: {n}")


def test_metadata_nutrients(client):
    r = client.get("/api/metadata/nutrients")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 37
    core = [n for n in data["items"] if n["is_core"]]
    assert any(n["nutrient_id"] == 1008 for n in core)  # Energy kcal


def test_metadata_nutrients_filter_core(client):
    r = client.get("/api/metadata/nutrients", params={"is_core": "true"})
    assert r.status_code == 200
    data = r.json()
    assert all(n["is_core"] for n in data["items"])


def test_metadata_categories(client):
    r = client.get("/api/metadata/categories")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 28  # FDC 28 个


def test_branded_food_query_via_list(client):
    """library_scope=branded 时，应查询真实品牌样例数据库；用途口径可放宽到 all。"""
    r = client.get(
        "/api/foods", params={"library_scope": "branded", "usage_scope": "all", "page_size": 100}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 349
    assert all(item["library_scope"] == "branded" for item in data["items"])
    assert all(item["data_type"] == "branded_food" for item in data["items"])
    assert all(item["usage_class"] for item in data["items"])


def test_default_scope_ignores_branded(client):
    """不指定 library_scope 时，默认查 default 库，不混入品牌商品。"""
    r = client.get("/api/foods", params={"page_size": 100})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == _usage_count()
    assert all(item["library_scope"] == "default" for item in data["items"])
    assert all(item["data_type"] != "branded_food" for item in data["items"])


def test_branded_food_detail(client):
    """指定 library_scope=branded 查询品牌食品详情，应返回正确库数据。"""
    import sqlite3

    # 从品牌库随机取一条 fdc_id
    conn = sqlite3.connect(str(BRANDED_DB))
    fid = conn.execute("SELECT fdc_id FROM food WHERE library_scope='branded' LIMIT 1").fetchone()[0]
    conn.close()

    r = client.get(f"/api/foods/{fid}", params={"library_scope": "branded"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fdc_id"] == fid
    assert data["library_scope"] == "branded"
    assert data["data_type"] == "branded_food"
    # 品牌库无 food_portion / food_alias / quality_event，应为空数组
    assert data["portions"] == []
    assert data["aliases"] == []
    assert data["quality_events"] == []


def test_branded_food_nutrients(client):
    """指定 library_scope=branded 查询品牌食品营养素。"""
    import sqlite3

    conn = sqlite3.connect(str(BRANDED_DB))
    fid, ncount = conn.execute(
        "SELECT fdc_id, COUNT(*) FROM food_nutrient GROUP BY fdc_id ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert ncount > 0

    r = client.get(f"/api/foods/{fid}/nutrients", params={"library_scope": "branded"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fdc_id"] == fid
    assert data["total_nutrients_returned"] == ncount


def test_get_food_no_scope_fallback(client):
    """不指定 library_scope 时：default 库有则返回 default 库的；没有才 fallback 到 branded。"""
    fdc_in_default = 748967  # 鸡蛋，明确在 default 库
    r = client.get(f"/api/foods/{fdc_in_default}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fdc_id"] == fdc_in_default
    assert data["library_scope"] == "default"  # 应该是 default 库的，不是 fallback 的


def test_list_foods_branded_missing_db(missing_db_client):
    """library_scope=branded 但 branded 库不存在时，应返回 503（connect 会抛 DatabaseUnavailableError）。"""
    # 注意：missing_db_client 把 branded_db 路径也指到了不存在的文件
    r = missing_db_client.get(
        "/api/foods", params={"library_scope": "branded", "page_size": 5}
    )
    assert r.status_code == 503, r.text
    body = r.json()
    assert body["code"] == "DATABASE_UNAVAILABLE"
    assert "数据库不存在" in body["message"]


def test_list_foods_invalid_library_scope_rejected(client):
    """非法的 library_scope 值应被 FastAPI Literal 校验器拒绝（422），不能假装切换成功。"""
    r = client.get("/api/foods", params={"library_scope": "nonexistent", "page_size": 5})
    assert r.status_code == 422, r.text


def test_metadata_categories_include_branded(client):
    """categories endpoint 应同时覆盖 default 库（fdc + wweia）和 branded 库（branded）。"""
    r = client.get("/api/metadata/categories")
    assert r.status_code == 200
    data = r.json()
    # 必须有 branded 的分类
    sources = {it["category_source"] for it in data["items"]}
    assert "branded" in sources, f"branded category 缺失，当前 sources={sources}"
    assert "fdc" in sources
    assert "wweia" in sources
    # 按 source=branded 筛选应返回 >0
    r2 = client.get("/api/metadata/categories", params={"source": "branded"})
    assert r2.status_code == 200
    assert r2.json()["total"] >= 100  # 品牌库 103 条不同分类


# ------------------------------------------------- 食品准入与中文化状态分离


def _db_default_count(where: str = "", params: tuple = ()) -> int:
    import sqlite3

    conn = sqlite3.connect(str(SAMPLE_DB))
    n = conn.execute(
        f"SELECT COUNT(*) FROM food WHERE library_scope='default' {where}", params
    ).fetchone()[0]
    conn.close()
    return int(n)


def _usage_count(usage_class: str | None = None, library_scope: str = "default") -> int:
    """用途库中的计数；usage_class 为 None 时统计默认口径（基础食材 + 加工食材）。"""
    import sqlite3

    conn = sqlite3.connect(str(USAGE_DB))
    if usage_class:
        n = conn.execute(
            "SELECT COUNT(*) FROM food_usage WHERE library_scope=? AND usage_class=?",
            (library_scope, usage_class),
        ).fetchone()[0]
    else:
        n = conn.execute(
            "SELECT COUNT(*) FROM food_usage WHERE library_scope=?"
            " AND usage_class IN ('basic_ingredient','processed_ingredient')",
            (library_scope,),
        ).fetchone()[0]
    conn.close()
    return int(n)


def _pick_no_zh_food(data_type: str = "foundation_food") -> tuple[int, str]:
    """取一条无中文名但有营养数据的默认库烹饪原料（动态，避免硬编码）。"""
    import sqlite3

    conn = sqlite3.connect(str(SAMPLE_DB))
    row = conn.execute(
        "SELECT f.fdc_id, f.description_en FROM food f "
        "WHERE f.library_scope='default' AND f.zh_status='none' AND f.data_type=? "
        "AND EXISTS (SELECT 1 FROM food_nutrient n WHERE n.fdc_id = f.fdc_id) "
        "ORDER BY f.fdc_id LIMIT 1",
        (data_type,),
    ).fetchone()
    conn.close()
    assert row is not None, f"sample 库应有 zh_status='none' 的 {data_type}"
    fdc_id = int(row[0])

    usage = sqlite3.connect(str(USAGE_DB))
    usage_class = usage.execute(
        "SELECT usage_class FROM food_usage WHERE library_scope='default' AND fdc_id=?",
        (fdc_id,),
    ).fetchone()
    usage.close()
    assert usage_class and usage_class[0] in {"basic_ingredient", "processed_ingredient"}, (
        f"无中文名样例 {fdc_id} 必须是烹饪原料（基础或加工食材），实际={usage_class}"
    )
    return fdc_id, str(row[1])


def test_list_foods_total_matches_usage_scope(client):
    """总数口径必须与用途筛选一致：默认=烹饪原料，all=默认库全部食品。"""
    r_all = client.get("/api/foods", params={"usage_scope": "all", "page_size": 1})
    assert r_all.status_code == 200
    assert r_all.json()["total"] == _db_default_count()

    r_ing = client.get("/api/foods", params={"page_size": 1})
    assert r_ing.status_code == 200
    assert r_ing.json()["total"] == _usage_count()
    # 默认列表确实排除了成品菜/即食/未知，因此少于全库
    assert _usage_count() < _db_default_count()
    none_total = _db_default_count("AND zh_status='none'")
    assert none_total > 0  # 无中文名记录仍在库中，不因中文状态删除


def test_no_chinese_food_listed_with_english_fallback(client):
    """无中文名但属于烹饪原料的食品照常出现在默认列表，display_name 回退为英文原名。"""
    fdc_id, description = _pick_no_zh_food()
    token = max(
        (w for w in description.replace(",", " ").split() if len(w) >= 4),
        key=len,
    )
    r2 = client.get("/api/foods", params={"q": token, "page_size": 100})
    assert r2.status_code == 200
    matched = {it["fdc_id"]: it for it in r2.json()["items"]}
    assert fdc_id in matched, f"无中文名烹饪原料应可通过英文名搜索到：{description}"
    item = matched[fdc_id]
    assert item["zh_status"] == "none"
    assert item["name_zh"] is None
    assert item["display_name"] == description
    assert item["usage_class"] in {"basic_ingredient", "processed_ingredient"}
    # 中文名状态不属于筛选条件：全库中仍有无中文名记录
    assert _db_default_count() > _db_default_count("AND zh_status != 'none'")


def test_fndds_usage_is_not_uniform(client):
    """FNDDS 不得整体归为单一用途类别：按描述与类别逐条判断。"""
    import sqlite3

    conn = sqlite3.connect(str(USAGE_DB))
    conn.execute("ATTACH DATABASE ? AS core", (str(SAMPLE_DB),))
    rows = conn.execute(
        "SELECT u.usage_class, COUNT(*) FROM food_usage u"
        " JOIN core.food f ON f.fdc_id = u.fdc_id AND f.library_scope = u.library_scope"
        " WHERE u.library_scope='default' AND f.data_type='survey_fndds_food'"
        " GROUP BY u.usage_class"
    )
    classes = dict(rows.fetchall())
    conn.close()

    assert len(classes) >= 2, f"FNDDS 用途类别不应只有一种：{classes}"
    expected = sum(v for k, v in classes.items() if k in {"basic_ingredient", "processed_ingredient"})
    r = client.get("/api/foods", params={"data_type": "survey_fndds_food", "page_size": 100})
    assert r.status_code == 200
    assert r.json()["total"] == expected


def test_filtered_pagination_uses_same_filter(client):
    """分页总数与各页内容基于同一筛选条件，且页间不重叠。"""
    r = client.get(
        "/api/foods",
        params={"data_type": "foundation_food", "usage_scope": "all", "page_size": 100},
    )
    assert r.status_code == 200
    total = r.json()["total"]
    assert total == _db_default_count("AND data_type='foundation_food'")

    seen: set[int] = set()
    page = 1
    while len(seen) < total:
        resp = client.get(
            "/api/foods",
            params={
                "data_type": "foundation_food",
                "usage_scope": "all",
                "page_size": 100,
                "page": page,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == total
        ids = [it["fdc_id"] for it in body["items"]]
        assert not seen.intersection(ids), f"第 {page} 页出现重复食品"
        seen.update(ids)
        if not ids:
            break
        page += 1
    assert len(seen) == total


# ------------------------------------------------- 食品用途分类与默认搜索


def _collect_all(client, params: dict) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        r = client.get("/api/foods", params={**params, "page_size": 100, "page": page})
        assert r.status_code == 200, r.text
        body = r.json()
        items.extend(body["items"])
        if len(items) >= body["total"] or not body["items"]:
            return items
        page += 1


def test_default_scope_only_contains_ingredients(client):
    """默认列表只含基础食材与加工食材，且分页不重复、总数一致。"""
    items = _collect_all(client, {})
    assert len(items) == _usage_count()
    assert len({it["fdc_id"] for it in items}) == len(items)
    assert {it["usage_class"] for it in items} == {"basic_ingredient", "processed_ingredient"}


def test_usage_class_filter_matches_total(client):
    """用途精确筛选时，total 与逐页内容使用同一条件。"""
    for usage_class in ("basic_ingredient", "processed_ingredient", "prepared_dish", "ready_to_eat", "unknown"):
        expected = _usage_count(usage_class)
        if expected == 0:
            continue
        items = _collect_all(client, {"usage_class": usage_class})
        assert len(items) == expected, f"{usage_class} 计数与列表不一致：{len(items)} != {expected}"
        assert all(it["usage_class"] == usage_class for it in items)


def test_prepared_and_ready_excluded_from_default(client):
    """明确成品菜/即食食品不进入默认基础食材列表，但可在用途范围中查看。"""
    default_ids = {it["fdc_id"] for it in _collect_all(client, {})}
    for usage_class in ("prepared_dish", "ready_to_eat"):
        assert _usage_count(usage_class) > 0
        scoped = _collect_all(client, {"usage_class": usage_class})
        assert scoped, f"{usage_class} 应可通过用途筛选查看"
        assert not default_ids.intersection(it["fdc_id"] for it in scoped)


def test_unknown_not_treated_as_ingredient(client):
    """unknown 不自动视为有效基础食材，只在显式用途范围中出现。"""
    assert _usage_count("unknown") > 0, "sample 用途库应保留至少一条 unknown 作为证据不足示例"
    default_ids = {it["fdc_id"] for it in _collect_all(client, {})}
    unknown_items = _collect_all(client, {"usage_class": "unknown"})
    assert unknown_items
    assert not default_ids.intersection(it["fdc_id"] for it in unknown_items)


def test_milk_human_is_ready_to_eat_not_hidden_by_id(client):
    """Milk, human 依用途归为即食食品，而非通过硬编码 fdc_id 隐藏。"""
    r = client.get("/api/foods/2705383", params={"library_scope": "default"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["usage_class"] == "ready_to_eat"
    assert data["usage_rule_source"] in {"category", "rule", "override"}
    assert data["usage_reason"]

    default_ids = {it["fdc_id"] for it in _collect_all(client, {"q": "human"})}
    assert 2705383 not in default_ids
    all_ids = {it["fdc_id"] for it in _collect_all(client, {"q": "human", "usage_scope": "all"})}
    assert 2705383 in all_ids


def test_usage_db_missing_returns_503(tmp_path):
    """用途库缺失时明确返回 503，而不是悄悄丢失用途字段或放行全部食品。"""
    _reset_api_modules()
    from backend.app.api import db as dbmod
    from backend.app.api import main as main_mod

    missing = tmp_path / "missing_usage.sqlite"
    dbmod.set_db_paths(SAMPLE_DB, BRANDED_DB, missing)
    c = TestClient(main_mod.app)
    r = c.get("/api/foods", params={"page_size": 5})
    assert r.status_code == 503, r.text
    assert "用途分类数据库不存在" in r.json()["message"]

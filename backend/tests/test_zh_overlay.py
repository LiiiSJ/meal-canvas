"""中文化映射层测试：三级状态、品牌不翻译、搜索词。"""
from __future__ import annotations

from backend.app.etl.zh_overlay import GLOSSARY, NONE, REVIEW_PENDING, VERIFIED, ZhOverlay


def _overlay() -> ZhOverlay:
    return ZhOverlay().load()


def test_verified_food_name():
    overlay = _overlay()
    resolved = overlay.resolve(746778, "Milk, reduced fat (2%)", "foundation_food")
    assert resolved.status == VERIFIED
    assert resolved.name_zh
    assert resolved.review_status == "verified"


def test_unknown_food_uses_glossary_candidate():
    overlay = _overlay()
    resolved = overlay.resolve(999999, "Kale, raw", "foundation_food")
    assert resolved.status == GLOSSARY
    assert resolved.name_zh == "羽衣甘蓝"
    assert resolved.review_status == REVIEW_PENDING


def test_food_without_any_mapping_stays_none():
    overlay = _overlay()
    resolved = overlay.resolve(999998, "Dragonfruit, raw", "survey_fndds_food")
    assert resolved.status == NONE
    assert resolved.name_zh is None
    assert resolved.review_status == REVIEW_PENDING


def test_branded_is_never_machine_translated():
    overlay = _overlay()
    resolved = overlay.resolve(999997, "Kale chips brand X", "branded_food")
    assert resolved.status == NONE
    assert resolved.name_zh is None
    assert "品牌" in resolved.reason


def test_category_names_are_chinese():
    overlay = _overlay()
    assert overlay.category_name("fdc", "11", None) == "蔬菜与蔬菜制品"
    assert overlay.category_name("wweia", "6407", None) == "西兰花"


def test_search_tokens_include_bigrams_and_pinyin():
    overlay = _overlay()
    tokens = overlay.build_search_tokens("西兰花", ("绿花菜",), "xi lan hua", "Broccoli, raw")
    assert "西兰花" in tokens
    assert "西兰" in tokens
    assert "绿花菜" in tokens
    assert "xilanhua" in tokens
    assert "xlh" in tokens
    assert "broccoli" in tokens


def test_verified_mapping_covers_required_categories():
    overlay = _overlay()
    verified = [entry for entry in overlay.foods.values() if entry.name_zh]
    assert len(verified) >= 150
    assert len({entry.fdc_id for entry in verified}) == len(verified)
    categories = {entry.category_zh for entry in verified if entry.category_zh}
    for expected in ("谷物与意面", "蔬菜与蔬菜制品", "水果与果汁", "乳制品与蛋类",
                     "鱼类与贝类", "豆类与豆制品", "坚果与种子", "油脂类"):
        assert expected in categories

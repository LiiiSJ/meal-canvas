"""食品用途规则引擎测试：优先级、类别映射、FNDDS 逐条判断与 CSV 校验。"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from backend.app.usage import UNKNOWN
from backend.app.usage.taxonomy import UsageTaxonomyError, load_taxonomy

CATEGORY_HEADER = ["category_source", "category_code", "usage_class", "note"]
RULE_HEADER = [
    "priority",
    "stage",
    "pattern",
    "usage_class",
    "data_type",
    "category_source",
    "category_code",
    "note",
]
OVERRIDE_HEADER = ["fdc_id", "usage_class", "note"]


def _write_curation(
    directory: Path,
    *,
    categories: list[list[str]] | None = None,
    rules: list[list[str]] | None = None,
    overrides: list[list[str]] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "usage_categories.csv": (CATEGORY_HEADER, categories or []),
        "usage_rules.csv": (RULE_HEADER, rules or []),
        "usage_overrides.csv": (OVERRIDE_HEADER, overrides or []),
    }
    for name, (header, rows) in files.items():
        with (directory / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    return directory


def test_real_curation_loads_and_covers_rules():
    tax = load_taxonomy()
    assert tax.rules, "真实 curation 应至少有一条描述规则"
    assert tax.categories, "真实 curation 应至少有类别映射"
    nightmare = [
        rule for rule in tax.rules if rule.pattern_text == r"\bas (an )?ingredient\b"
    ]
    assert nightmare, "“as ingredient”规则必须存在（用于识别烹饪配料）"


def test_before_rule_overrides_category_default():
    """具体描述证据（坚果酱加工品）优先于类别默认值（坚果种子=基础食材）。"""
    tax = load_taxonomy()
    result = tax.classify(
        fdc_id=123,
        data_type="foundation_food",
        category_source="fdc",
        category_code="12",
        description_en="Peanut butter, creamy",
    )
    assert result.usage_class == "processed_ingredient"
    assert result.rule_source == "rule"


def test_category_mapping_applies_when_no_specific_rule():
    tax = load_taxonomy()
    result = tax.classify(
        fdc_id=456,
        data_type="foundation_food",
        category_source="fdc",
        category_code="11",
        description_en="Broccoli, raw",
    )
    assert result.usage_class == "basic_ingredient"
    assert result.rule_source == "category"


def test_after_rule_only_when_category_unknown():
    """类别 unknown 时，宽泛描述规则（生鲜肉类）可作为兜底证据。"""
    tax = load_taxonomy()
    result = tax.classify(
        fdc_id=789,
        data_type="foundation_food",
        category_source="fdc",
        category_code="24",
        description_en="Beef, raw",
    )
    assert result.usage_class == "basic_ingredient"
    assert result.rule_source == "rule"

    unresolved = tax.classify(
        fdc_id=790,
        data_type="foundation_food",
        category_source="fdc",
        category_code="24",
        description_en="Mystery item, no evidence",
    )
    assert unresolved.usage_class == UNKNOWN
    assert unresolved.rule_source == "category"


def test_unknown_without_any_evidence_is_not_guessed():
    tax = load_taxonomy()
    result = tax.classify(
        fdc_id=791,
        data_type="branded_food",
        category_source="branded",
        category_code=None,
        category_en="",
        description_en="Unlabelled product",
    )
    assert result.usage_class == UNKNOWN
    assert result.rule_source == "default"


def test_fndds_is_classified_per_record_not_by_source():
    """FNDDS 记录按类别与描述逐条判定，不因数据源统一归类。"""
    tax = load_taxonomy()
    broccoli = tax.classify(
        fdc_id=6001,
        data_type="survey_fndds_food",
        category_source="wweia",
        category_code="6407",
        description_en="Broccoli, raw",
    )
    pizza = tax.classify(
        fdc_id=6002,
        data_type="survey_fndds_food",
        category_source="wweia",
        category_code="3602",
        description_en="Pizza, cheese",
    )
    cereal = tax.classify(
        fdc_id=6003,
        data_type="survey_fndds_food",
        category_source="wweia",
        category_code="4602",
        description_en="Cereals ready-to-eat",
    )
    assert broccoli.usage_class == "basic_ingredient"
    assert pizza.usage_class == "prepared_dish"
    assert cereal.usage_class == "ready_to_eat"
    assert len({broccoli.usage_class, pizza.usage_class, cereal.usage_class}) == 3


def test_milk_human_is_ready_to_eat_by_category_not_by_fdc_id():
    """母乳按 WWEIA 9602 类别判定为即食食品，规则里没有针对该 fdc_id 的硬编码。"""
    tax = load_taxonomy()
    result = tax.classify(
        fdc_id=2705383,
        data_type="survey_fndds_food",
        category_source="wweia",
        category_code="9602",
        description_en="Milk, human",
    )
    assert result.usage_class == "ready_to_eat"
    assert result.rule_source == "category"
    assert 2705383 not in tax.overrides


def test_branded_category_name_used_when_code_missing():
    tax = load_taxonomy()
    cheese = tax.classify(
        fdc_id=9001,
        data_type="branded_food",
        category_source="branded",
        category_code=None,
        category_en="Cheese",
        description_en="Brand cheese",
    )
    soda = tax.classify(
        fdc_id=9002,
        data_type="branded_food",
        category_source="branded",
        category_code=None,
        category_en="Soda",
        description_en="Brand cola",
    )
    assert cheese.usage_class == "basic_ingredient"
    assert soda.usage_class == "ready_to_eat"


def test_override_has_highest_priority(tmp_path):
    curation = _write_curation(
        tmp_path,
        categories=[["fdc", "11", "basic_ingredient", "蔬菜"]],
        rules=[["0", "before_category", "pizza", "prepared_dish", "", "", "", "披萨"]],
        overrides=[["123", "unknown", "人工复核：用途证据不足"]],
    )
    tax = load_taxonomy(curation)
    result = tax.classify(
        fdc_id=123,
        data_type="foundation_food",
        category_source="fdc",
        category_code="11",
        description_en="Pizza, frozen",
    )
    assert result.usage_class == UNKNOWN
    assert result.rule_source == "override"


def test_duplicate_category_is_rejected(tmp_path):
    curation = _write_curation(
        tmp_path,
        categories=[
            ["fdc", "11", "basic_ingredient", "蔬菜"],
            ["fdc", "11", "processed_ingredient", "重复"],
        ],
    )
    with pytest.raises(UsageTaxonomyError, match="重复"):
        load_taxonomy(curation)


def test_invalid_usage_class_is_rejected(tmp_path):
    curation = _write_curation(
        tmp_path,
        categories=[["fdc", "11", "not_a_class", "非法分类"]],
    )
    with pytest.raises(UsageTaxonomyError, match="用途分类非法"):
        load_taxonomy(curation)


def test_invalid_stage_and_regex_are_rejected(tmp_path):
    curation = _write_curation(
        tmp_path,
        rules=[["0", "mid_category", "pizza", "prepared_dish", "", "", "", "非法阶段"]],
    )
    with pytest.raises(UsageTaxonomyError, match="stage 非法"):
        load_taxonomy(curation)

    curation = _write_curation(
        tmp_path,
        rules=[["0", "before_category", "(", "prepared_dish", "", "", "", "非法正则"]],
    )
    with pytest.raises(UsageTaxonomyError, match="正则表达式无法编译"):
        load_taxonomy(curation)

"""食品用途分类规则引擎（只读 data/curation/ 下的三个 CSV）。

判定优先级（高 → 低）：

1. `usage_overrides.csv`：人工对单个 `fdc_id` 的显式判定。
2. `usage_rules.csv` 中 `stage=before_category` 的描述规则：用于纠正类别默认值的
   具体证据（例如“油炸”“三明治”“酱汁”）。
3. `usage_categories.csv`：类别级默认映射（`category_source` + `category_code`；
   品牌库使用 `branded_food_category` 名称作为 `category_code`）。
4. `usage_rules.csv` 中 `stage=after_category` 的兜底规则：仅在类别映射缺失或为
   `unknown` 时生效（例如“生鲜肉类”“蔬菜”“谷物”这类宽泛证据）。
5. 以上都不命中 → `unknown`，并记录“证据不足”，绝不猜测。

规则按 `priority` 升序执行，同优先级按文件行序；可限定 `data_type` /
`category_source` / `category_code`，留空表示不限。

规则文件只读，构建用途库时不修改任何 USDA 原始字段。
"""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from backend.app.usage import (
    CLASSIFICATION_VERSION,
    UNKNOWN,
    USAGE_CLASSES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CURATION_DIR = PROJECT_ROOT / "data" / "curation"

KNOWN_DATA_TYPES: frozenset[str] = frozenset(
    {"foundation_food", "sr_legacy_food", "survey_fndds_food", "branded_food"}
)
KNOWN_CATEGORY_SOURCES: frozenset[str] = frozenset({"fdc", "wweia", "branded"})

STAGE_BEFORE = "before_category"
STAGE_AFTER = "after_category"
RULE_STAGES: frozenset[str] = frozenset({STAGE_BEFORE, STAGE_AFTER})


class UsageTaxonomyError(RuntimeError):
    """规则文件缺失或内容非法；消息为中文，可直接返回给调用方。"""


@dataclass(frozen=True, slots=True)
class UsageRule:
    """一条描述规则。`rule_id` 用文件行号，便于回溯到维护者手写的原始行。"""

    pattern_text: str
    pattern: re.Pattern[str]
    usage_class: str
    data_type: str | None
    category_source: str | None
    category_code: str | None
    note: str
    priority: int
    stage: str
    line: int

    @property
    def rule_id(self) -> str:
        return f"usage_rules.csv:L{self.line}"

    def matches(
        self,
        *,
        description: str,
        data_type: str,
        category_source: str | None,
        category_code: str | None,
    ) -> bool:
        if self.data_type is not None and self.data_type != data_type:
            return False
        if self.category_source is not None and self.category_source != (category_source or ""):
            return False
        if self.category_code is not None and self.category_code != (category_code or ""):
            return False
        return self.pattern.search(description or "") is not None


@dataclass(frozen=True, slots=True)
class CategoryMapping:
    category_source: str
    category_code: str
    usage_class: str
    note: str
    line: int

    @property
    def rule_id(self) -> str:
        return f"usage_categories.csv:{self.category_source}:{self.category_code}"


@dataclass(frozen=True, slots=True)
class RuleOverride:
    fdc_id: int
    usage_class: str
    note: str
    line: int

    @property
    def rule_id(self) -> str:
        return f"usage_overrides.csv:{self.fdc_id}"


@dataclass(frozen=True, slots=True)
class Classification:
    """单条食品的用途判定结果，含可追溯的规则来源。"""

    usage_class: str
    rule_source: str  # override | rule | category | default
    rule_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class CurationPaths:
    categories: Path
    rules: Path
    overrides: Path


def curation_paths(curation_dir: Path | None = None) -> CurationPaths:
    base = (curation_dir or DEFAULT_CURATION_DIR).expanduser()
    return CurationPaths(
        categories=base / "usage_categories.csv",
        rules=base / "usage_rules.csv",
        overrides=base / "usage_overrides.csv",
    )


@dataclass
class UsageTaxonomy:
    rules: tuple[UsageRule, ...]
    categories: Mapping[tuple[str, str], CategoryMapping]
    overrides: Mapping[int, RuleOverride]
    version: str = CLASSIFICATION_VERSION

    def classify(
        self,
        *,
        fdc_id: int,
        data_type: str,
        category_source: str | None = None,
        category_code: str | None = None,
        category_en: str | None = None,
        description_en: str = "",
    ) -> Classification:
        """按 override → 具体描述规则 → 类别映射 → 兜底描述规则 → unknown 判定用途。"""
        override = self.overrides.get(int(fdc_id))
        if override is not None:
            return Classification(
                usage_class=override.usage_class,
                rule_source="override",
                rule_id=override.rule_id,
                reason=override.note or "人工显式指定的用途判定",
            )

        matched = self._first_rule(
            STAGE_BEFORE,
            data_type=data_type,
            category_source=category_source,
            category_code=category_code,
            description=description_en,
        )
        if matched is not None:
            return Classification(
                usage_class=matched.usage_class,
                rule_source="rule",
                rule_id=matched.rule_id,
                reason=matched.note or f"命中描述规则：{matched.pattern_text}",
            )

        mapping = self.categories.get(_category_key(category_source, category_code, category_en))
        if mapping is not None and mapping.usage_class != UNKNOWN:
            return Classification(
                usage_class=mapping.usage_class,
                rule_source="category",
                rule_id=mapping.rule_id,
                reason=mapping.note or "按类别默认映射判定用途",
            )

        matched = self._first_rule(
            STAGE_AFTER,
            data_type=data_type,
            category_source=category_source,
            category_code=category_code,
            description=description_en,
        )
        if matched is not None:
            return Classification(
                usage_class=matched.usage_class,
                rule_source="rule",
                rule_id=matched.rule_id,
                reason=matched.note or f"命中兜底描述规则：{matched.pattern_text}",
            )

        if mapping is not None:
            # 类别自身就写明“证据不足”，保留这条可追溯说明。
            return Classification(
                usage_class=UNKNOWN,
                rule_source="category",
                rule_id=mapping.rule_id,
                reason=mapping.note or "该类别混合多种用途，证据不足，保持用途未知。",
            )

        return Classification(
            usage_class=UNKNOWN,
            rule_source="default",
            rule_id=None,
            reason="类别映射与描述规则均无可靠证据，保持用途未知，不猜测。",
        )

    def _first_rule(
        self,
        stage: str,
        *,
        data_type: str,
        category_source: str | None,
        category_code: str | None,
        description: str,
    ) -> UsageRule | None:
        for rule in self.rules:
            if rule.stage != stage:
                continue
            if rule.matches(
                description=description,
                data_type=data_type,
                category_source=category_source,
                category_code=category_code,
            ):
                return rule
        return None

    def classify_food_row(self, row: Mapping[str, object]) -> Classification:
        """对一行 food 记录判定用途。行对象可以是 sqlite3.Row 或 dict。"""
        return self.classify(
            fdc_id=int(row["fdc_id"]),  # type: ignore[arg-type]
            data_type=str(row["data_type"] or ""),
            category_source=_optional(row["category_source"]),
            category_code=_optional(row["category_code"]),
            category_en=_optional(row["category_en"]) if "category_en" in row.keys() else None,
            description_en=str(row["description_en"] or ""),
        )


def _category_key(
    category_source: str | None,
    category_code: str | None,
    category_en: str | None,
) -> tuple[str, str]:
    """类别键：优先 category_code；品牌库无 code 时退回 branded_food_category 名称。"""
    return (category_source or "", category_code or (category_en or "").strip())


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_taxonomy(curation_dir: Path | None = None) -> UsageTaxonomy:
    """读取并校验三个规则文件；文件缺失或字段非法时抛出中文错误。"""
    paths = curation_paths(curation_dir)
    return UsageTaxonomy(
        rules=_load_rules(paths.rules),
        categories=_load_categories(paths.categories),
        overrides=_load_overrides(paths.overrides),
    )


# --------------------------------------------------------------------------- 加载


def _read_csv(path: Path, required_columns: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    if not path.is_file():
        raise UsageTaxonomyError(
            f"用途规则文件不存在：{path}。请在 data/curation/ 下补齐该文件后再构建用途库。"
        )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        missing = [col for col in required_columns if col not in header]
        if missing:
            raise UsageTaxonomyError(
                f"{path.name} 表头缺少字段：{', '.join(missing)}。"
                f"需要的字段为：{', '.join(required_columns)}。"
            )
        return [(reader.line_num, dict(row)) for row in reader]


def _require(value: str | None, label: str, filename: str, line: int) -> str:
    text = (value or "").strip()
    if not text:
        raise UsageTaxonomyError(f"{filename} 第 {line} 行缺少{label}。")
    return text


def _validate_class(value: str | None, filename: str, line: int) -> str:
    text = _require(value, "用途分类 usage_class", filename, line)
    if text not in USAGE_CLASSES:
        raise UsageTaxonomyError(
            f"{filename} 第 {line} 行的用途分类非法：{text}。"
            f"只允许：{', '.join(USAGE_CLASSES)}。"
        )
    return text


def _validate_known(value: str | None, allowed: frozenset[str], label: str, filename: str, line: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if text not in allowed:
        raise UsageTaxonomyError(
            f"{filename} 第 {line} 行的{label}非法：{text}。只允许：{', '.join(sorted(allowed))}。"
        )
    return text


def _load_rules(path: Path) -> tuple[UsageRule, ...]:
    rows = _read_csv(
        path,
        (
            "priority",
            "stage",
            "pattern",
            "usage_class",
            "data_type",
            "category_source",
            "category_code",
            "note",
        ),
    )
    rules: list[UsageRule] = []
    for line, row in rows:
        if not any((value or "").strip() for value in row.values()):
            continue
        pattern_text = _require(row.get("pattern"), "描述正则 pattern", path.name, line)
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            raise UsageTaxonomyError(
                f"{path.name} 第 {line} 行的正则表达式无法编译：{pattern_text}（{exc}）。"
            ) from exc
        priority_raw = (row.get("priority") or "").strip() or "0"
        try:
            priority = int(priority_raw)
        except ValueError as exc:
            raise UsageTaxonomyError(
                f"{path.name} 第 {line} 行的 priority 必须是整数，当前为：{priority_raw}。"
            ) from exc
        rules.append(
            UsageRule(
                pattern_text=pattern_text,
                pattern=pattern,
                usage_class=_validate_class(row.get("usage_class"), path.name, line),
                data_type=_validate_known(
                    row.get("data_type"), KNOWN_DATA_TYPES, "data_type", path.name, line
                ),
                category_source=_validate_known(
                    row.get("category_source"),
                    KNOWN_CATEGORY_SOURCES,
                    "category_source",
                    path.name,
                    line,
                ),
                category_code=_optional(row.get("category_code")),
                note=(row.get("note") or "").strip(),
                priority=priority,
                stage=_validate_stage(row.get("stage"), path.name, line),
                line=line,
            )
        )
    # 稳定排序：priority 升序，同优先级保持文件行序（Python sort 是稳定的）。
    rules.sort(key=lambda rule: (rule.priority, rule.line))
    return tuple(rules)


def _validate_stage(value: str | None, filename: str, line: int) -> str:
    text = (value or "").strip() or STAGE_BEFORE
    if text not in RULE_STAGES:
        raise UsageTaxonomyError(
            f"{filename} 第 {line} 行的 stage 非法：{text}。只允许：{STAGE_BEFORE} / {STAGE_AFTER}。"
        )
    return text


def _load_categories(path: Path) -> dict[tuple[str, str], CategoryMapping]:
    rows = _read_csv(path, ("category_source", "category_code", "usage_class", "note"))
    mappings: dict[tuple[str, str], CategoryMapping] = {}
    seen_at: dict[tuple[str, str], int] = {}
    for line, row in rows:
        if not any((value or "").strip() for value in row.values()):
            continue
        source = _validate_known(
            row.get("category_source"), KNOWN_CATEGORY_SOURCES, "category_source", path.name, line
        )
        if source is None:
            raise UsageTaxonomyError(f"{path.name} 第 {line} 行缺少 category_source。")
        code = _require(row.get("category_code"), "category_code", path.name, line)
        key = (source, code)
        if key in mappings:
            raise UsageTaxonomyError(
                f"{path.name} 第 {line} 行的类别 {source}:{code} 与第 {seen_at[key]} 行重复，同一类别只能映射一次。"
            )
        seen_at[key] = line
        mappings[key] = CategoryMapping(
            category_source=source,
            category_code=code,
            usage_class=_validate_class(row.get("usage_class"), path.name, line),
            note=(row.get("note") or "").strip(),
            line=line,
        )
    return mappings


def _load_overrides(path: Path) -> dict[int, RuleOverride]:
    rows = _read_csv(path, ("fdc_id", "usage_class", "note"))
    overrides: dict[int, RuleOverride] = {}
    seen_at: dict[int, int] = {}
    for line, row in rows:
        if not any((value or "").strip() for value in row.values()):
            continue
        raw_id = _require(row.get("fdc_id"), "fdc_id", path.name, line)
        try:
            fdc_id = int(raw_id)
        except ValueError as exc:
            raise UsageTaxonomyError(
                f"{path.name} 第 {line} 行的 fdc_id 必须是正整数，当前为：{raw_id}。"
            ) from exc
        if fdc_id <= 0:
            raise UsageTaxonomyError(f"{path.name} 第 {line} 行的 fdc_id 必须是正整数，当前为：{fdc_id}。")
        if fdc_id in overrides:
            raise UsageTaxonomyError(
                f"{path.name} 第 {line} 行的 fdc_id={fdc_id} 与第 {seen_at[fdc_id]} 行重复。"
            )
        seen_at[fdc_id] = line
        overrides[fdc_id] = RuleOverride(
            fdc_id=fdc_id,
            usage_class=_validate_class(row.get("usage_class"), path.name, line),
            note=(row.get("note") or "").strip(),
            line=line,
        )
    return overrides

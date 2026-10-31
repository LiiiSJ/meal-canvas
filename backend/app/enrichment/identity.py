"""食品身份匹配评分。

只用原始英文描述、GTIN 与状态词判断，绝不用中文名匹配。
匹配分级：
- exact    可靠确认同一食品（GTIN 一致，或归一化描述逐词一致且状态词一致）→ 允许自动补全
- similar  高度相似但状态/品种可能不同 → 仅候选
- partial  仅名称部分重叠 → 仅候选
- none     无法确认 → 完全丢弃
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_LEVEL_EXACT = "exact"
_LEVEL_SIMILAR = "similar"
_LEVEL_PARTIAL = "partial"
_LEVEL_NONE = "none"

# 生食/熟食/加工状态词：状态冲突（如 raw vs roasted）时绝不 exact。
STATE_WORDS = frozenset({
    "raw", "cooked", "roasted", "boiled", "baked", "grilled", "fried", "dried",
    "canned", "frozen", "pickled", "brined", "fresh", "steamed", "smoked",
    "stewed", "braised", "poached", "blanched", "fermented", "reconstituted",
})

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def normalize_tokens(text: str) -> list[str]:
    """小写、去标点、逐词切分。供匹配评分与证据留痕使用。"""
    return [t for t in _TOKEN_SPLIT.split(text.lower()) if t]


def _states(tokens: list[str]) -> frozenset[str]:
    return frozenset(t for t in tokens if t in STATE_WORDS)


@dataclass(frozen=True)
class LocalFood:
    """项目内食品身份（来自只读 USDA 库）。"""

    fdc_id: int
    description_en: str
    data_type: str
    gtin_upc: str | None = None
    brand_name: str | None = None


@dataclass(frozen=True)
class ExternalFood:
    """外部候选记录（由 Provider 返回）。"""

    provider: str
    external_id: str
    name_en: str
    source_url: str
    payload: dict
    gtin_upc: str | None = None


@dataclass(frozen=True)
class MatchResult:
    level: str  # exact / similar / partial / none
    score: float
    evidence: dict = field(default_factory=dict)


def _normalize_gtin(gtin: str | None) -> str | None:
    if not gtin:
        return None
    digits = re.sub(r"\D", "", str(gtin))
    if not digits:
        return None
    # UPC-A（12 位）与 EAN-13（13 位）只差一个前导 0：去前导零后比较
    return digits.lstrip("0") or None


def score_match(local: LocalFood, external: ExternalFood) -> MatchResult:
    """对单个外部候选做身份评分。"""
    local_gtin = _normalize_gtin(local.gtin_upc)
    external_gtin = _normalize_gtin(external.gtin_upc)
    if local_gtin and external_gtin and local_gtin == external_gtin:
        return MatchResult(
            level=_LEVEL_EXACT,
            score=1.0,
            evidence={"method": "gtin", "gtin": local_gtin},
        )

    local_tokens = normalize_tokens(local.description_en)
    external_tokens = normalize_tokens(external.name_en)
    local_states = _states(local_tokens)
    external_states = _states(external_tokens)
    common = set(local_tokens) & set(external_tokens)
    union = set(local_tokens) | set(external_tokens)
    jaccard = len(common) / len(union) if union else 0.0

    evidence = {
        "method": "description",
        "jaccard": round(jaccard, 4),
        "common_words": sorted(common),
        "local_states": sorted(local_states),
        "external_states": sorted(external_states),
    }

    identical = bool(local_tokens) and bool(external_tokens) and local_tokens == external_tokens
    state_conflict = bool(local_states) and bool(external_states) and local_states != external_states

    if identical and not state_conflict:
        return MatchResult(level=_LEVEL_EXACT, score=1.0, evidence=evidence)

    if state_conflict:
        # 生/熟等状态不同：即使名称几乎一致也只能作候选；完全无重叠则丢弃。
        if not common:
            return MatchResult(level=_LEVEL_NONE, score=0.0, evidence=evidence)
        level = _LEVEL_SIMILAR if jaccard >= 0.5 else _LEVEL_PARTIAL
        return MatchResult(level=level, score=round(min(jaccard, 0.7), 4), evidence=evidence)

    if jaccard >= 0.8:
        return MatchResult(level=_LEVEL_SIMILAR, score=round(jaccard, 4), evidence=evidence)
    if common:
        return MatchResult(level=_LEVEL_PARTIAL, score=round(jaccard, 4), evidence=evidence)
    return MatchResult(level=_LEVEL_NONE, score=0.0, evidence=evidence)

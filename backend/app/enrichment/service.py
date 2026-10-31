"""补全服务编排：缺失检测 → 缓存 → 去重 → 检索 → 身份评分 → 逐项核验 → 落库 → 统一解析。

原则：
- USDA 原始有效值永远优先；只补传入 profile 中为 None 的项（真实零值不是缺失）。
- 检查范围由调用方传入的 profile 决定：API 路由传入 nutrient 元数据表全部 37 项，
  因此缺失检测覆盖系统支持的所有营养素，不止核心 7 项。
- 只有 exact 身份匹配 + 单位/基准校验通过的外部值才允许自动采纳（verified_external）。
- 多来源冲突时保留冲突说明并降级为候选，绝不静默挑选。
- 同一 fdc_id 的并发检索用进程内锁去重；负缓存避免重复外呼。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import httpx
from backend.app.enrichment import mapper as mapper_mod
from backend.app.enrichment import storage as storage_mod
from backend.app.enrichment.config import EnrichSettings, load_enrich_settings
from backend.app.enrichment.identity import ExternalFood, LocalFood, MatchResult, score_match
from backend.app.enrichment.mapper import STATUS_CANDIDATE, STATUS_VERIFIED
from backend.app.enrichment.providers.base import USER_AGENT, BaseProvider, ProviderError
from backend.app.enrichment.providers.openfoodfacts import OpenFoodFactsProvider
from backend.app.enrichment.providers.usda_fdc import UsdaFdcProvider
from backend.app.enrichment.storage import (
    OUTCOME_CACHED,
    OUTCOME_DISABLED,
    OUTCOME_ENRICHED,
    OUTCOME_ERROR,
    OUTCOME_NO_MISSING,
    OUTCOME_NOT_FOUND,
    OUTCOME_PARTIAL,
    EnrichStorage,
    ValueRecord,
)

log = logging.getLogger(__name__)

# 多来源数值一致性容差：相对 2%（能量等四舍五入差异视为一致）
_REL_TOL = 0.02
_ABS_TOL = 0.05

_LICENSE_BY_PROVIDER = {
    "usda_fdc": "USDA FoodData Central（公有领域）",
    "openfoodfacts": "Open Food Facts（ODbL / CC-BY-SA，需署名）",
}


@dataclass(frozen=True)
class ResolvedNutrient:
    key: str
    value: float | None
    origin: str  # usda / external / none
    status: str  # usda / verified_external / candidate_review / none
    usda_value: float | None
    source_name: str | None
    source_url: str | None
    conversion_method: str | None
    original_basis: str | None
    note: str | None


@dataclass(frozen=True)
class CandidateView:
    source_name: str
    external_name_en: str
    match_level: str
    source_url: str
    nutrient_key: str | None
    note: str | None


@dataclass
class ResolveResult:
    fdc_id: int
    values: list[ResolvedNutrient] = field(default_factory=list)
    missing_keys: list[str] = field(default_factory=list)
    attempted: bool = False
    outcome: str = OUTCOME_NOT_FOUND
    message: str | None = None
    candidates: list[CandidateView] = field(default_factory=list)
    provider_status: list[dict] = field(default_factory=list)


def _agree(a: float, b: float) -> bool:
    return abs(a - b) <= max(_REL_TOL * max(abs(a), abs(b)), _ABS_TOL)


class EnrichmentService:
    def __init__(
        self,
        settings: EnrichSettings,
        *,
        db_path=None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.storage = EnrichStorage(db_path or settings.db_path)
        self._transport = transport
        self._providers = self._build_providers()
        self._locks_guard = threading.Lock()
        self._fdc_locks: dict[int, threading.Lock] = {}

    # ------------------------------------------------------------------ 基础

    def _build_providers(self) -> list[tuple[int, BaseProvider]]:
        client_kwargs: dict = {
            "timeout": self.settings.timeout_seconds,
            "headers": {"User-Agent": USER_AGENT},
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        client = httpx.Client(**client_kwargs)

        providers: list[tuple[int, BaseProvider]] = []
        if self.settings.fdc_available:
            providers.append((
                0,
                UsdaFdcProvider(
                    client,
                    api_key=self.settings.fdc_api_key or "",
                    min_interval=self.settings.fdc_min_interval,
                    max_retries=self.settings.max_retries,
                ),
            ))
        if self.settings.off_available:
            providers.append((
                1,
                OpenFoodFactsProvider(
                    client,
                    min_interval=self.settings.off_min_interval,
                    max_retries=self.settings.max_retries,
                    allow_name_search=self.settings.off_name_search,
                ),
            ))
        providers.sort(key=lambda item: item[0])
        return providers

    def _lock_for(self, fdc_id: int) -> threading.Lock:
        with self._locks_guard:
            lock = self._fdc_locks.get(fdc_id)
            if lock is None:
                lock = threading.Lock()
                self._fdc_locks[fdc_id] = lock
            return lock

    @property
    def enabled(self) -> bool:
        return self.settings.enabled and bool(self._providers)

    # ------------------------------------------------------------------ 解析

    def resolve(
        self,
        local: LocalFood,
        summary: dict[str, float | None],
        *,
        force: bool = False,
    ) -> ResolveResult:
        result = ResolveResult(fdc_id=local.fdc_id)
        result.provider_status = self.settings.provider_status()

        # 检查范围 = 传入 profile 的全部键（API 路由传入 nutrient 表全部 37 项）
        keys = list(summary.keys())
        missing = [k for k in keys if summary.get(k) is None]
        result.missing_keys = list(missing)

        # 1) 以 USDA 原始值为基础构建解析视图
        resolved: dict[str, ResolvedNutrient] = {}
        for key in keys:
            usda_value = summary.get(key)
            resolved[key] = ResolvedNutrient(
                key=key,
                value=usda_value,
                origin="usda" if usda_value is not None else "none",
                status="usda" if usda_value is not None else "none",
                usda_value=usda_value,
                source_name=None,
                source_url=None,
                conversion_method=None,
                original_basis=None,
                note=None,
            )

        if not self.enabled:
            result.values = list(resolved.values())
            result.outcome = OUTCOME_DISABLED
            result.message = "后端未启用外部数据补全，仅展示原始 USDA 数据。"
            return result

        # 2) 应用已缓存的 verified 补全值（无论是否 force）
        self._apply_stored_verified(local.fdc_id, resolved, missing)

        if not missing:
            result.values = list(resolved.values())
            result.outcome = OUTCOME_NO_MISSING
            result.message = "当前食品核心营养数据完整，无需外部补全。"
            return result

        still_missing = [k for k in missing if resolved[k].origin == "none"]
        if not still_missing:
            result.values = list(resolved.values())
            result.outcome = OUTCOME_CACHED
            result.message = "缺失指标此前已通过外部来源补全，使用缓存结果。"
            result.candidates = self._candidate_views(local.fdc_id)
            return result

        # 3) 负缓存：最近一次 not_found / error 在 TTL 内则不再外呼
        if not force:
            latest = self.storage.latest_attempt(local.fdc_id)
            if latest is not None and set(latest.missing_keys) >= set(still_missing):
                if latest.outcome == OUTCOME_NOT_FOUND and self.storage.attempt_is_fresh(
                    latest, self.settings.negative_ttl_minutes
                ):
                    result.values = list(resolved.values())
                    result.outcome = OUTCOME_NOT_FOUND
                    result.message = "近期检索未找到可靠外部来源，缺失项保持未知。"
                    result.candidates = self._candidate_views(local.fdc_id)
                    return result
                if latest.outcome == OUTCOME_ERROR and self.storage.attempt_is_fresh(
                    latest, self.settings.error_ttl_minutes
                ):
                    result.values = list(resolved.values())
                    result.outcome = OUTCOME_ERROR
                    result.message = "外部数据源近期不可用，已保留原始数据；稍后可重试。"
                    return result
                if latest.outcome == OUTCOME_PARTIAL and self.storage.attempt_is_fresh(
                    latest, self.settings.negative_ttl_minutes
                ):
                    result.values = list(resolved.values())
                    result.outcome = OUTCOME_PARTIAL
                    result.attempted = False
                    result.message = "此前已补全部分缺失项，其余项近期未找到可靠来源；使用缓存结果。"
                    result.candidates = self._candidate_views(local.fdc_id)
                    return result

        # 4) 网络检索（同一 fdc_id 进程内串行，避免并发重复外呼）
        with self._lock_for(local.fdc_id):
            outcome = self._search_and_store(local, resolved, missing)

        result.attempted = True
        self._apply_stored_verified(local.fdc_id, resolved, missing)
        remaining = [k for k in missing if resolved[k].origin == "none"]
        if outcome == OUTCOME_ERROR:
            result.outcome = OUTCOME_ERROR
            result.message = "外部数据源暂时不可用，已保留原始数据；稍后可重试。"
        elif not remaining:
            result.outcome = OUTCOME_ENRICHED
            result.message = f"已通过外部来源补全 {len(missing)} 项缺失指标。"
        elif len(remaining) < len(missing):
            result.outcome = OUTCOME_PARTIAL
            result.message = f"已补全 {len(missing) - len(remaining)} 项，仍有 {len(remaining)} 项未找到可靠来源。"
        else:
            result.outcome = OUTCOME_NOT_FOUND
            result.message = "未在外部数据源中找到可靠匹配，缺失项保持未知。"

        result.values = list(resolved.values())
        result.candidates = self._candidate_views(local.fdc_id)
        return result

    # ------------------------------------------------------------------ 内部

    def _apply_stored_verified(
        self,
        fdc_id: int,
        resolved: dict[str, ResolvedNutrient],
        missing: list[str],
    ) -> None:
        for record in self.storage.verified_values(fdc_id):
            key = record.nutrient_key
            if key not in resolved or key not in missing:
                continue
            if resolved[key].origin != "none":
                continue  # USDA 值永远优先，外部值不覆盖
            value = record.value_per_100g
            if value is None or value < 0:
                continue
            resolved[key] = ResolvedNutrient(
                key=key,
                value=value,
                origin="external",
                status=storage_mod.VERIFIED,
                usda_value=None,
                source_name=record.source.provider,
                source_url=record.source.source_url,
                conversion_method=record.conversion_method,
                original_basis=record.original_basis,
                note=record.conflict_note,
            )

    def _search_and_store(
        self,
        local: LocalFood,
        resolved: dict[str, ResolvedNutrient],
        missing: list[str],
    ) -> str:
        """执行检索并落库。返回 outcome：enriched / partial / not_found / error。"""
        # (priority, match, external, mapped)
        collected: list[tuple[int, MatchResult, ExternalFood, dict[str, mapper_mod.MappedNutrient]]] = []
        provider_errors: list[str] = []

        for priority, provider in self._providers:
            try:
                candidates = provider.find_candidates(
                    local.description_en, local.gtin_upc, local.data_type
                )
            except ProviderError as exc:
                log.warning("[enrichment] %s 检索失败：%s", provider.name, exc)
                provider_errors.append(f"{provider.name}: {exc}")
                continue
            for candidate in candidates[: self.settings.max_candidates]:
                match = score_match(local, candidate)
                if match.level == "none":
                    continue
                mapped = mapper_mod.map_external(provider.name, candidate.payload)
                collected.append((priority, match, candidate, mapped))

        if not collected:
            outcome = OUTCOME_ERROR if provider_errors else OUTCOME_NOT_FOUND
            detail = "；".join(provider_errors) if provider_errors else "无任何身份可确认的外部候选"
            self.storage.record_attempt(
                fdc_id=local.fdc_id, missing_keys=missing, outcome=outcome, detail=detail
            )
            return outcome

        # 逐缺失项汇总 exact 候选的 verified 值
        exact_verified: dict[str, list[tuple[int, MatchResult, ExternalFood, mapper_mod.MappedNutrient]]] = {
            k: [] for k in missing
        }

        for priority, match, external, mapped in collected:
            if match.level == "exact":
                for key in missing:
                    item = mapped.get(key)
                    if item is not None and item.status == STATUS_VERIFIED:
                        exact_verified[key].append((priority, match, external, item))
            elif match.level in ("similar", "partial"):
                for key in missing:
                    item = mapped.get(key)
                    if item is not None and item.status in (STATUS_VERIFIED, STATUS_CANDIDATE):
                        self._store_candidate_value(local.fdc_id, external, match, key, item)

        filled: list[str] = []
        for key in missing:
            values = exact_verified[key]
            if not values:
                continue
            values.sort(key=lambda entry: entry[0])  # 来源优先级：FDC 先于 OFF
            priority, match, external, item = base = values[0]
            divergent = [v for v in values[1:] if not _agree(base[3].value_per_100g or 0.0, v[3].value_per_100g or 0.0)]

            if divergent:
                # 冲突：全部降级为候选，保留全部候选值，绝不自动挑选
                others_text = "；".join(
                    f"{v[2].provider}={v[3].value_per_100g}" for v in values[1:]
                )
                note = (
                    f"多来源数值冲突（{external.provider}={item.value_per_100g} vs {others_text}），"
                    "已保留全部候选，不自动采用"
                )
                for entry in values:
                    _, m, ext, it = entry
                    self._store_candidate_value(local.fdc_id, ext, m, key, it, conflict_note=note)
                continue

            source_id = self.storage.upsert_source(
                provider=external.provider,
                external_id=external.external_id,
                external_name_en=external.name_en,
                source_url=external.source_url,
                match_level=match.level,
                match_score=match.score,
                match_evidence=match.evidence,
                license_note=_LICENSE_BY_PROVIDER.get(external.provider),
            )
            self.storage.upsert_value(
                fdc_id=local.fdc_id,
                nutrient_key=key,
                source_id=source_id,
                original_amount=item.original_amount,
                original_unit=item.original_unit,
                original_basis=item.original_basis,
                value_per_100g=item.value_per_100g,
                conversion_method=item.conversion_method,
                status=storage_mod.VERIFIED,
                conflict_note=None,
            )
            filled.append(key)

        self._prune_candidates(local.fdc_id)

        outcome = (
            OUTCOME_ENRICHED if len(filled) == len(missing)
            else OUTCOME_PARTIAL if filled
            else OUTCOME_NOT_FOUND
        )
        detail = f"补全 {len(filled)}/{len(missing)} 项"
        if provider_errors:
            detail += f"；部分来源失败（{'；'.join(provider_errors)}）"
        self.storage.record_attempt(
            fdc_id=local.fdc_id, missing_keys=missing, outcome=outcome, detail=detail
        )
        return outcome

    def _store_candidate_value(
        self,
        fdc_id: int,
        external: ExternalFood,
        match: MatchResult,
        key: str,
        item: mapper_mod.MappedNutrient,
        *,
        conflict_note: str | None = None,
    ) -> None:
        source_id = self.storage.upsert_source(
            provider=external.provider,
            external_id=external.external_id,
            external_name_en=external.name_en,
            source_url=external.source_url,
            match_level=match.level,
            match_score=match.score,
            match_evidence=match.evidence,
            license_note=_LICENSE_BY_PROVIDER.get(external.provider),
        )
        self.storage.upsert_value(
            fdc_id=fdc_id,
            nutrient_key=key,
            source_id=source_id,
            original_amount=item.original_amount,
            original_unit=item.original_unit,
            original_basis=item.original_basis,
            value_per_100g=item.value_per_100g,
            conversion_method=item.conversion_method,
            status=storage_mod.CANDIDATE,
            conflict_note=conflict_note or item.note,
        )

    def _candidate_views(self, fdc_id: int) -> list[CandidateView]:
        views: list[CandidateView] = []
        seen: set[tuple[str, str]] = set()
        for record in self.storage.candidate_values(fdc_id):
            src = record.source
            dedup_key = (src.provider, src.external_id)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            local_states = src.match_evidence.get("local_states")
            external_states = src.match_evidence.get("external_states")
            note = record.conflict_note
            if not note and local_states and external_states and local_states != external_states:
                note = (
                    f"状态可能不同（本食品：{'/'.join(local_states)}；"
                    f"候选：{'/'.join(external_states)}），未自动采用"
                )
            views.append(
                CandidateView(
                    source_name=src.provider,
                    external_name_en=src.external_name_en,
                    match_level=src.match_level,
                    source_url=src.source_url,
                    nutrient_key=record.nutrient_key,
                    note=note,
                )
            )
        return views

    def _prune_candidates(self, fdc_id: int) -> None:
        """限制候选来源行数，避免无限增长。超出上限时保留分数最高的。"""
        candidates = self.storage.candidate_values(fdc_id)
        by_source: dict[int, list[ValueRecord]] = {}
        for record in candidates:
            by_source.setdefault(record.source.id, []).append(record)
        if len(by_source) <= self.settings.max_candidates:
            return
        ranked = sorted(
            by_source.items(),
            key=lambda kv: max((r.source.match_score for r in kv[1]), default=0.0),
            reverse=True,
        )
        for source_id, _records in ranked[self.settings.max_candidates:]:
            with self.storage.connect() as conn:
                conn.execute("DELETE FROM enrich_value WHERE source_id = ?", (source_id,))
                conn.execute("DELETE FROM enrich_source WHERE id = ?", (source_id,))


# ------------------------------------------------------------------ 单例

_service: EnrichmentService | None = None


def get_service() -> EnrichmentService:
    global _service
    if _service is None:
        _service = EnrichmentService(load_enrich_settings())
    return _service


def set_service(service: EnrichmentService | None) -> None:
    global _service
    _service = service

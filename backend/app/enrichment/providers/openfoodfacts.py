"""Open Food Facts v2 API Provider（来源优先级 3，免 API Key）。

- 使用官方公开 API（条码精确查询 + 名称搜索），遵守其使用条款（≤1 请求/秒、
  自定义 User-Agent、署名 ODbL / CC-BY-SA）。
- 仅用于有明确商品身份的包装食品；名称搜索结果一律不 exact（除非 GTIN 一致）。
"""
from __future__ import annotations

import logging

from backend.app.enrichment.identity import ExternalFood
from backend.app.enrichment.providers.base import USER_AGENT, BaseProvider, ProviderError

log = logging.getLogger(__name__)

PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"


class OpenFoodFactsProvider(BaseProvider):
    name = "openfoodfacts"
    license_note = "Open Food Facts（ODbL / CC-BY-SA，需署名）"

    def __init__(self, *args, allow_name_search: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.allow_name_search = allow_name_search

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    def _by_gtin(self, gtin: str) -> ExternalFood | None:
        resp = self.request("GET", PRODUCT_URL.format(code=gtin), params=None)
        if resp.status_code == 404:
            return None
        data = self.parse_json(resp)
        if data.get("status") != 1:
            return None
        product = data.get("product")
        if not isinstance(product, dict) or not product.get("product_name"):
            return None
        code = str(product.get("code") or gtin)
        return ExternalFood(
            provider=self.name,
            external_id=code,
            name_en=str(product.get("product_name")),
            source_url=f"https://world.openfoodfacts.org/product/{code}.html",
            payload=product,
            gtin_upc=code,
        )

    def _by_name(self, description_en: str, max_items: int) -> list[ExternalFood]:
        resp = self.request(
            "GET",
            SEARCH_URL,
            params={
                "search_terms": description_en,
                "page_size": str(max_items),
                "fields": "code,product_name,brands,nutriments,serving_quantity,serving_unit",
            },
        )
        data = self.parse_json(resp)
        products = data.get("products")
        if not isinstance(products, list):
            return []
        out: list[ExternalFood] = []
        for item in products:
            if not isinstance(item, dict):
                continue
            name = item.get("product_name")
            code = item.get("code")
            if not name or not code:
                continue
            out.append(
                ExternalFood(
                    provider=self.name,
                    external_id=str(code),
                    name_en=str(name),
                    source_url=f"https://world.openfoodfacts.org/product/{code}.html",
                    payload=item,
                    gtin_upc=str(code) if code else None,
                )
            )
        return out

    def find_candidates(
        self, description_en: str, gtin_upc: str | None, data_type: str = ""
    ) -> list[ExternalFood]:
        out: list[ExternalFood] = []
        if gtin_upc:
            try:
                found = self._by_gtin(gtin_upc)
            except ProviderError as exc:
                log.warning("[openfoodfacts] GTIN 查询失败：%s", exc)
                found = None
            if found is not None:
                out.append(found)
        # 名称搜索是辅助路径：已有 GTIN 结果时不让搜索失败拖垮整个来源。
        # 批量品牌库补全可整体关闭名称搜索（GTIN 已精确，避免 search 端点限流）。
        if not self.allow_name_search:
            return out
        try:
            out.extend(self._by_name(description_en, max_items=5))
        except ProviderError as exc:
            if not out:
                raise
            log.warning("[openfoodfacts] 名称搜索失败（保留 GTIN 结果）：%s", exc)
        return out

"""USDA FoodData Central API Provider（来源优先级 1）。

- 需 API Key（环境变量 MEAL_CANVAS_FDC_API_KEY），仅在服务端使用。
- 在其他数据类型记录中检索同一食品；返回数据以每 100 克为基准（官方 API 保证）。
"""
from __future__ import annotations

import logging

import httpx
from backend.app.enrichment.identity import ExternalFood
from backend.app.enrichment.providers.base import BaseProvider, ProviderError

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# 默认食材库跨数据类型找同一食品；品牌库只搜品牌。
_DEFAULT_TYPES = ("foundation_food", "sr_legacy_food", "survey_fndds_food")
_BRANDED_TYPES = ("branded_food",)


class UsdaFdcProvider(BaseProvider):
    name = "usda_fdc"
    license_note = "USDA FoodData Central（美国农业部，公有领域）"

    def __init__(self, client: httpx.Client, *, api_key: str, **kwargs) -> None:
        super().__init__(client, **kwargs)
        self._api_key = api_key

    def find_candidates(
        self, description_en: str, gtin_upc: str | None, data_type: str = ""
    ) -> list[ExternalFood]:
        data_types = _BRANDED_TYPES if data_type == "branded_food" else _DEFAULT_TYPES
        params: list[tuple[str, str]] = [
            ("api_key", self._api_key),
            ("query", description_en),
            ("pageSize", "5"),
        ]
        for dt in data_types:
            params.append(("dataType", dt))

        resp = self.request("GET", SEARCH_URL, params=params)
        if resp.status_code in (400, 401, 403):
            raise ProviderError(
                f"USDA FDC API 拒绝请求（HTTP {resp.status_code}）。"
                "请检查 MEAL_CANVAS_FDC_API_KEY 是否有效。"
            )
        data = self.parse_json(resp)

        out: list[ExternalFood] = []
        foods = data.get("foods")
        if not isinstance(foods, list):
            return out
        for item in foods:
            if not isinstance(item, dict):
                continue
            fdc_id = item.get("fdcId")
            description = item.get("description")
            if not isinstance(fdc_id, int) or not description:
                continue
            out.append(
                ExternalFood(
                    provider=self.name,
                    external_id=str(fdc_id),
                    name_en=str(description),
                    source_url=f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{fdc_id}/nutrients",
                    payload=item,
                    gtin_upc=item.get("gtinUpc"),
                )
            )
        return out

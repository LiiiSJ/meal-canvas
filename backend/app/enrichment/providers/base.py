"""外部数据源 Provider 基类：统一的超时、重试、限速与错误包装。"""
from __future__ import annotations

import logging
import threading
import time

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "MealCanvas/0.1 (local nutrition study project; +https://github.com/meal-canvas)"


class ProviderError(RuntimeError):
    """外部服务不可用 / 响应格式异常 / 鉴权失败。message 为中文。"""


class BaseProvider:
    """同步 HTTP Provider。测试注入 httpx.MockTransport 即可，不发真实网络请求。"""

    name = "base"
    license_note = ""

    def __init__(
        self,
        client: httpx.Client,
        *,
        min_interval: float = 1.0,
        max_retries: int = 2,
    ) -> None:
        self._client = client
        self._min_interval = max(0.0, min_interval)
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._last_request_ts = 0.0

    def _respect_rate_limit(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    def request(self, method: str, url: str, *, params: dict | None = None, json_body: dict | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._respect_rate_limit()
            try:
                resp = self._client.request(method, url, params=params, json=json_body)
            except httpx.TransportError as exc:
                last_error = exc
                log.warning("[%s] 网络错误（第 %d 次）：%s", self.name, attempt + 1, exc)
                if attempt < self._max_retries:
                    time.sleep(0.5 * (2**attempt))
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = ProviderError(f"外部服务返回 HTTP {resp.status_code}")
                log.warning("[%s] HTTP %d（第 %d 次）", self.name, resp.status_code, attempt + 1)
                retry_after = resp.headers.get("Retry-After")
                if attempt < self._max_retries:
                    delay = 0.5 * (2**attempt)
                    # OFF 的 Retry-After 常见为 30–60s，上限放宽到 60s 以尊重服务端要求
                    if retry_after and retry_after.isdigit():
                        delay = max(delay, min(float(retry_after), 60.0))
                    time.sleep(delay)
                continue
            return resp

        raise ProviderError(f"外部数据源 {self.name} 暂时不可用：{last_error}")

    def parse_json(self, resp: httpx.Response) -> dict:
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f"外部数据源 {self.name} 返回了非 JSON 响应") from exc
        if not isinstance(data, dict):
            raise ProviderError(f"外部数据源 {self.name} 返回的数据结构不符合预期")
        return data

    # 子类实现：返回候选列表；失败抛 ProviderError。
    def find_candidates(self, description_en: str, gtin_upc: str | None) -> list:  # noqa: ANN201
        raise NotImplementedError

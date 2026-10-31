"""四个数据源适配器。每个适配器独立实现字段语义。"""
from __future__ import annotations

from backend.app.etl.sources.branded import BrandedAdapter
from backend.app.etl.sources.foundation import FoundationAdapter
from backend.app.etl.sources.sr_legacy import SRLegacyAdapter
from backend.app.etl.sources.survey import SurveyAdapter

ADAPTERS = {
    "foundation": FoundationAdapter,
    "sr_legacy": SRLegacyAdapter,
    "survey": SurveyAdapter,
    "branded": BrandedAdapter,
}

__all__ = [
    "ADAPTERS",
    "BrandedAdapter",
    "FoundationAdapter",
    "SRLegacyAdapter",
    "SurveyAdapter",
]

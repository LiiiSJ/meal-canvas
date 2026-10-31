"""独立的外部补全存储层。

独立 SQLite 库（默认 data/build/meal_canvas_enrichment.sqlite），
与 USDA 原始库物理隔离；本模块的连接绝不指向 USDA 数据库，
也不提供任何写入 USDA 表的能力。

三张表：
- enrich_source   外部食品身份与匹配证据
- enrich_value    逐营养素补全值（UNIQUE(fdc_id, nutrient_key, source_id)，天然去重）
- enrich_attempt  检索历史（含负缓存：not_found 24h、error 10min 内不重复外呼）
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enrich_source (
    id               INTEGER PRIMARY KEY,
    provider         TEXT NOT NULL,
    external_id      TEXT NOT NULL,
    external_name_en TEXT NOT NULL,
    source_url       TEXT NOT NULL,
    match_level      TEXT NOT NULL,
    match_score      REAL NOT NULL,
    match_evidence   TEXT NOT NULL,
    retrieved_at     TEXT NOT NULL,
    license_note     TEXT,
    UNIQUE(provider, external_id)
);

CREATE TABLE IF NOT EXISTS enrich_value (
    id                INTEGER PRIMARY KEY,
    fdc_id            INTEGER NOT NULL,
    nutrient_key      TEXT NOT NULL,
    source_id         INTEGER NOT NULL REFERENCES enrich_source(id) ON DELETE CASCADE,
    original_amount   REAL,
    original_unit     TEXT,
    original_basis    TEXT,
    value_per_100g    REAL,
    conversion_method TEXT,
    status            TEXT NOT NULL,
    conflict_note     TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(fdc_id, nutrient_key, source_id)
);

CREATE TABLE IF NOT EXISTS enrich_attempt (
    id           INTEGER PRIMARY KEY,
    fdc_id       INTEGER NOT NULL,
    missing_keys TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    detail       TEXT,
    attempted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enrich_value_fdc ON enrich_value(fdc_id);
CREATE INDEX IF NOT EXISTS idx_enrich_value_status ON enrich_value(status);
CREATE INDEX IF NOT EXISTS idx_enrich_attempt_fdc ON enrich_attempt(fdc_id, attempted_at);
"""

VERIFIED = "verified_external"
CANDIDATE = "candidate_review"
REJECTED = "rejected"

OUTCOME_NO_MISSING = "no_missing"
OUTCOME_DISABLED = "disabled"
OUTCOME_ENRICHED = "enriched"
OUTCOME_PARTIAL = "partial"
OUTCOME_NOT_FOUND = "not_found"
OUTCOME_ERROR = "error"
OUTCOME_CACHED = "cached"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SourceRecord:
    id: int
    provider: str
    external_id: str
    external_name_en: str
    source_url: str
    match_level: str
    match_score: float
    match_evidence: dict
    retrieved_at: str
    license_note: str | None


@dataclass(frozen=True)
class ValueRecord:
    fdc_id: int
    nutrient_key: str
    source: SourceRecord
    original_amount: float | None
    original_unit: str | None
    original_basis: str | None
    value_per_100g: float | None
    conversion_method: str | None
    status: str
    conflict_note: str | None
    updated_at: str


@dataclass(frozen=True)
class AttemptRecord:
    fdc_id: int
    missing_keys: list[str]
    outcome: str
    detail: str | None
    attempted_at: str


class EnrichStorage:
    """补全库读写。所有写入只发生在本库；USDA 库连接与本类无关。"""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(str(self._path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ---------------------------------------------------------------- 来源

    def upsert_source(
        self,
        *,
        provider: str,
        external_id: str,
        external_name_en: str,
        source_url: str,
        match_level: str,
        match_score: float,
        match_evidence: dict,
        license_note: str | None,
    ) -> int:
        now = _now_iso()
        evidence = json.dumps(match_evidence, ensure_ascii=False, sort_keys=True)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO enrich_source
                    (provider, external_id, external_name_en, source_url,
                     match_level, match_score, match_evidence, retrieved_at, license_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, external_id) DO UPDATE SET
                    external_name_en = excluded.external_name_en,
                    source_url = excluded.source_url,
                    match_level = excluded.match_level,
                    match_score = excluded.match_score,
                    match_evidence = excluded.match_evidence,
                    retrieved_at = excluded.retrieved_at,
                    license_note = excluded.license_note
                """,
                (provider, external_id, external_name_en, source_url,
                 match_level, match_score, evidence, now, license_note),
            )
            row = conn.execute(
                "SELECT id FROM enrich_source WHERE provider = ? AND external_id = ?",
                (provider, external_id),
            ).fetchone()
            assert row is not None
            return int(row["id"])

    # ---------------------------------------------------------------- 数值

    def upsert_value(
        self,
        *,
        fdc_id: int,
        nutrient_key: str,
        source_id: int,
        original_amount: float | None,
        original_unit: str | None,
        original_basis: str | None,
        value_per_100g: float | None,
        conversion_method: str | None,
        status: str,
        conflict_note: str | None,
    ) -> None:
        now = _now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO enrich_value
                    (fdc_id, nutrient_key, source_id, original_amount, original_unit,
                     original_basis, value_per_100g, conversion_method, status,
                     conflict_note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fdc_id, nutrient_key, source_id) DO UPDATE SET
                    original_amount = excluded.original_amount,
                    original_unit = excluded.original_unit,
                    original_basis = excluded.original_basis,
                    value_per_100g = excluded.value_per_100g,
                    conversion_method = excluded.conversion_method,
                    status = excluded.status,
                    conflict_note = excluded.conflict_note,
                    updated_at = excluded.updated_at
                """,
                (fdc_id, nutrient_key, source_id, original_amount, original_unit,
                 original_basis, value_per_100g, conversion_method, status,
                 conflict_note, now, now),
            )

    def _row_to_value(self, vrow: sqlite3.Row, srow: sqlite3.Row) -> ValueRecord:
        source = SourceRecord(
            id=int(srow["id"]),
            provider=srow["provider"],
            external_id=srow["external_id"],
            external_name_en=srow["external_name_en"],
            source_url=srow["source_url"],
            match_level=srow["match_level"],
            match_score=float(srow["match_score"]),
            match_evidence=json.loads(srow["match_evidence"]),
            retrieved_at=srow["retrieved_at"],
            license_note=srow["license_note"],
        )
        return ValueRecord(
            fdc_id=int(vrow["fdc_id"]),
            nutrient_key=vrow["nutrient_key"],
            source=source,
            original_amount=vrow["original_amount"],
            original_unit=vrow["original_unit"],
            original_basis=vrow["original_basis"],
            value_per_100g=vrow["value_per_100g"],
            conversion_method=vrow["conversion_method"],
            status=vrow["status"],
            conflict_note=vrow["conflict_note"],
            updated_at=vrow["updated_at"],
        )

    def values_by_status(self, fdc_id: int, statuses: tuple[str, ...]) -> list[ValueRecord]:
        placeholders = ",".join("?" * len(statuses))
        with self.connect() as conn:
            vrows = conn.execute(
                f"SELECT * FROM enrich_value WHERE fdc_id = ? AND status IN ({placeholders})",
                (fdc_id, *statuses),
            ).fetchall()
            out: list[ValueRecord] = []
            for vrow in vrows:
                srow = conn.execute(
                    "SELECT * FROM enrich_source WHERE id = ?", (vrow["source_id"],)
                ).fetchone()
                if srow is None:
                    continue
                out.append(self._row_to_value(vrow, srow))
        return out

    def verified_values(self, fdc_id: int) -> list[ValueRecord]:
        return self.values_by_status(fdc_id, (VERIFIED,))

    def candidate_values(self, fdc_id: int) -> list[ValueRecord]:
        return self.values_by_status(fdc_id, (CANDIDATE,))

    # ---------------------------------------------------------------- 检索历史

    def record_attempt(self, *, fdc_id: int, missing_keys: list[str], outcome: str, detail: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO enrich_attempt (fdc_id, missing_keys, outcome, detail, attempted_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (fdc_id, json.dumps(missing_keys, ensure_ascii=False), outcome, detail, _now_iso()),
            )

    def latest_attempt(self, fdc_id: int) -> AttemptRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM enrich_attempt WHERE fdc_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (fdc_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            missing = json.loads(row["missing_keys"])
        except (TypeError, ValueError):
            missing = []
        return AttemptRecord(
            fdc_id=int(row["fdc_id"]),
            missing_keys=missing if isinstance(missing, list) else [],
            outcome=row["outcome"],
            detail=row["detail"],
            attempted_at=row["attempted_at"],
        )

    def attempt_is_fresh(self, attempt: AttemptRecord, ttl_minutes: float) -> bool:
        ts = _parse_iso(attempt.attempted_at)
        if ts is None:
            return False
        return datetime.now(UTC) - ts < timedelta(minutes=ttl_minutes)

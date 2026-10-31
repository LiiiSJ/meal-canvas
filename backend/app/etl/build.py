"""SQLite 构建入口（sample 与 full 共用一套导入逻辑）。

用法（Windows 固定命令）：

    .\\.venv\\Scripts\\python.exe -m backend.app.etl.build --mode sample --library default
    .\\.venv\\Scripts\\python.exe -m backend.app.etl.build --mode sample --library branded

硬约束：
- 必须显式指定 --mode；full 模式还需 --confirm-full，且不得覆盖已存在的正式库。
- sample 只写 data/build/sample/，与正式库路径隔离（由 config.resolve_library_paths 强制）。
- 先写 .tmp，完整性检查通过后再原子替换。
- 缺失营养不写 0；负数保留 raw_amount、amount=NULL、quality_flag='negative'。
- 能量按 1008 → 2048 → 2047 只取一个；1062 kJ 独立存储，不参与 kcal。
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from backend.app.core.config import (
    BRANDED_LIBRARY_SOURCES,
    DEFAULT_LIBRARY_SOURCES,
    Settings,
    load_settings,
    resolve_library_paths,
    validate_data_dir,
)
from backend.app.etl import nutrients as nutrient_rules
from backend.app.etl.base import FoodRow, NutrientRow, SourceAdapter, parse_amount
from backend.app.etl.nutrients import (
    ENERGY_IDS,
    load_nutrient_defs,
    normalize_row,
    resolve_energy,
)
from backend.app.etl.sample_manifest import SAMPLE_MANIFEST_NAME, load_manifest, manifest_sha256
from backend.app.etl.sources import ADAPTERS
from backend.app.etl.zh_overlay import VERIFIED, ZhOverlay

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
COMMIT_EVERY_FOODS = 500

CORE_SUMMARY_COLUMNS = {
    1008: "energy_kcal",
    1003: "protein_g",
    1004: "fat_g",
    1005: "carb_g",
    1079: "fiber_g",
    2000: "sugar_g",
    1093: "sodium_mg",
}

FOOD_INSERT_SQL = """
INSERT OR REPLACE INTO food (
    fdc_id, data_type, description_en, name_zh, zh_status, zh_review_status,
    brand_owner, brand_name, gtin_upc, category_source, category_code, category_en,
    category_zh, publication_date, source_dataset, source_version,
    serving_size, serving_unit, household_serving, ingredients_en,
    is_default_library, library_scope, search_tokens
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

NUTRIENT_INSERT_SQL = """
INSERT INTO food_nutrient (fdc_id, nutrient_id, amount, raw_amount, quality_flag, origin_nutrient_id)
VALUES (?,?,?,?,?,?)
"""


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def open_build_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def load_canonical_defs(settings: Settings):
    """以 Foundation 的 nutrient.csv 作为主字典，并与其余数据源比对。"""
    canonical = load_nutrient_defs(settings.zip_path("foundation"))
    for key in ("sr_legacy", "survey", "branded"):
        other = load_nutrient_defs(settings.zip_path(key))
        conflicts = nutrient_rules.compare_definitions(canonical, other)
        for line in conflicts:
            logging.warning("营养字典差异（%s）：%s", key, line)
    return canonical


def insert_nutrients(conn: sqlite3.Connection, overlay: ZhOverlay, defs) -> None:
    stmt = (
        "INSERT OR REPLACE INTO nutrient"
        " (id, nbr, name_en, unit_name, rank, name_zh, unit_zh, group_zh, is_core, decimals)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)"
    )
    rows = []
    for nid, zh in sorted(overlay.nutrients.items()):
        definition = defs.get(nid)
        if definition is None:
            logging.warning("营养素 %s 不在数据源 nutrient.csv 中，跳过", nid)
            continue
        rows.append((
            nid, definition.nbr, definition.name_en, definition.unit_name, definition.rank,
            zh.name_zh, zh.unit_zh, zh.group_zh, zh.is_core, zh.decimals,
        ))
    conn.executemany(stmt, rows)
    conn.commit()


class Builder:
    def __init__(self, conn: sqlite3.Connection, overlay: ZhOverlay, defs, mode: str, library: str):
        self.conn = conn
        self.overlay = overlay
        self.defs = defs
        self.mode = mode
        self.library = library
        self.cursor = conn.cursor()
        self.allowed_ids = frozenset(overlay.nutrients)
        self.core_ids = frozenset(nid for nid, zh in overlay.nutrients.items() if zh.is_core)
        self.unit_by_id = {nid: d.unit_name for nid, d in defs.items()}
        self.events: list[tuple] = []
        self.pending_rows: list[dict] = []
        self.stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.summary_rows: list[tuple] = []
        self.food_ids_by_source: dict[str, set[int]] = defaultdict(set)
        self._since_commit = 0

    # ------------------------------------------------------------ 食品
    def import_foods(self, source_key: str, adapter: SourceAdapter, ids: set[int] | None) -> set[int]:
        seen: set[int] = set()
        for food in adapter.iter_foods(ids):
            self._insert_food(food, source_key)
            seen.add(food.fdc_id)
            self.stats[source_key]["foods"] += 1
        self.conn.commit()
        self.food_ids_by_source[source_key] = seen
        logging.info("%s：导入食品 %s 条（请求 %s 条）", source_key, len(seen),
                     "全量" if ids is None else len(ids))
        return seen

    def _insert_food(self, food: FoodRow, source_key: str) -> None:
        resolved = self.overlay.resolve(food.fdc_id, food.description_en, food.data_type)
        category_zh = self.overlay.category_name(
            food.category_source, food.category_code, food.category_en
        )
        tokens = self.overlay.build_search_tokens(
            resolved.name_zh, resolved.aliases, resolved.pinyin, food.description_en
        )
        self.cursor.execute(FOOD_INSERT_SQL, (
            food.fdc_id, food.data_type, food.description_en, resolved.name_zh,
            resolved.status, resolved.review_status,
            food.brand_owner, food.brand_name, food.gtin_upc,
            food.category_source, food.category_code, food.category_en, category_zh,
            food.publication_date, food.source_dataset, food.source_version,
            food.serving_size, food.serving_unit, food.household_serving, food.ingredients_en,
            food.is_default_library, food.library_scope, tokens,
        ))
        self.cursor.execute(
            "INSERT OR REPLACE INTO food_fts (fdc_id, tokens) VALUES (?,?)",
            (food.fdc_id, tokens),
        )
        for alias in resolved.aliases:
            self.cursor.execute(
                "INSERT OR REPLACE INTO food_alias (fdc_id, alias, alias_type, status, review_status)"
                " VALUES (?,?,?,?,?)",
                (food.fdc_id, alias, "alias", resolved.status, resolved.review_status),
            )
        if resolved.status != VERIFIED:
            self.pending_rows.append({
                "fdc_id": food.fdc_id,
                "description_en": food.description_en,
                "data_type": food.data_type,
                "source_dataset": food.source_dataset,
                "category_en": food.category_en or "",
                "candidate_zh": resolved.name_zh or "",
                "zh_status": resolved.status,
                "review_status": resolved.review_status,
                "reason": resolved.reason,
            })
        self.stats[source_key][f"zh_{resolved.status}"] += 1

    # ------------------------------------------------------------ 营养
    def import_nutrients(self, source_key: str, adapter: SourceAdapter, ids: set[int]) -> None:
        buffer: dict[int, list[NutrientRow]] = defaultdict(list)
        total = 0
        flush_foods = 2000
        for row in adapter.iter_nutrients(ids):
            if row.fdc_id not in ids:
                continue
            total += 1
            if row.fdc_id not in buffer and len(buffer) >= flush_foods:
                self._flush_buffer(buffer, source_key)
                buffer = defaultdict(list)
            buffer[row.fdc_id].append(row)
        self._flush_buffer(buffer, source_key)
        self.conn.commit()
        self.stats[source_key]["nutrient_rows"] = total
        logging.info("%s：读取营养行 %s 行", source_key, total)

    def _flush_buffer(self, buffer: dict[int, list[NutrientRow]], source_key: str) -> None:
        for fdc_id, rows in buffer.items():
            self._flush_food(fdc_id, rows, source_key)
        buffer.clear()
        self.conn.commit()
        self._since_commit = 0

    def _flush_food(self, fdc_id: int, rows: list[NutrientRow], source_key: str) -> None:
        written: dict[int, float] = {}
        energy_candidates: dict[int, float | None] = {}
        energy_raw: dict[int, float | None] = {}

        # 按处理阶段计数（用于事后对账，不是日志）
        counter = defaultdict(int)

        for row in rows:
            counter["input_rows"] += 1
            nid = row.nutrient_id
            if nid is None:
                self._event(fdc_id, "unmapped_nutrient", None, row.amount_raw,
                            f"原始营养编号 {row.raw_nutrient_id} 无法映射")
                counter["unmapped_unknown_nid"] += 1
                continue
            if nid in ENERGY_IDS:
                if nid in energy_candidates:
                    self._event(fdc_id, "duplicate", nid, row.amount_raw, "重复能量口径")
                    counter["duplicate_energy_drop"] += 1
                    continue
                parsed = parse_amount(row.amount_text)
                energy_candidates[nid] = parsed.value if parsed.status == "ok" else None
                energy_raw[nid] = row.amount_raw
                continue
            if nid not in self.defs:
                self._event(fdc_id, "unmapped_nutrient", nid, row.amount_raw,
                            "营养编号不在数据源 nutrient.csv 中")
                counter["unmapped_not_in_defs"] += 1
                continue
            if nid not in self.allowed_ids:
                # 未纳入中文化白名单的营养素不写入，也不当作错误（属于既定范围）
                self.stats[source_key]["nutrient_rows_skipped"] += 1
                counter["whitelist_skipped"] += 1
                continue
            if nid in written:
                self._event(fdc_id, "duplicate", nid, row.amount_raw, "同一食品重复营养行")
                counter["duplicate_non_energy_drop"] += 1
                continue
            canonical, value, flag = normalize_row(row, self.allowed_ids, self.unit_by_id)
            if canonical is None:
                self._event(fdc_id, "unmapped_nutrient", nid, row.amount_raw, "无法映射的营养编号")
                counter["unmapped_not_in_defs"] += 1
                continue
            if flag == "missing":
                # 缺失 = 数据库无行，禁止写 0
                counter["missing_amount_drop"] += 1
                continue
            self.cursor.execute(NUTRIENT_INSERT_SQL, (
                fdc_id, canonical, value, row.amount_raw, flag, nid,
            ))
            counter["written_other"] += 1
            written[canonical] = value if value is not None else float("nan")

        # 能量候选折叠：原始 N 条能量候选 → 最终 1 条写入
        energy_input = len(energy_candidates)
        counter["energy_candidates_input"] = energy_input
        counter["energy_collapsed"] = max(energy_input - 1, 0)

        resolution = resolve_energy(energy_candidates)
        if resolution.nutrient_id is not None:
            self.cursor.execute(NUTRIENT_INSERT_SQL, (
                fdc_id, 1008, resolution.value, energy_raw.get(resolution.nutrient_id),
                resolution.quality_flag, resolution.nutrient_id,
            ))
            counter["written_energy"] = 1
            written[1008] = resolution.value if resolution.value is not None else float("nan")
        else:
            counter["written_energy"] = 0
        if resolution.conflict:
            detail = ", ".join(f"{nid}={value}" for nid, value in sorted(energy_candidates.items()))
            self._event(fdc_id, "energy_conflict", 1008, None, f"多口径能量：{detail}")

        # 汇总到 source 级统计（用显式名称避免混用）
        for key in (
            "energy_candidates_input", "energy_collapsed",
            "unmapped_unknown_nid", "unmapped_not_in_defs",
            "duplicate_energy_drop", "duplicate_non_energy_drop",
            "missing_amount_drop",
            "written_energy", "written_other",
        ):
            if counter[key]:
                self.stats[source_key][f"_{key}"] += counter[key]

        summary = [written.get(nid) for nid in CORE_SUMMARY_COLUMNS]
        summary = [None if value is None or value != value else value for value in summary]
        known_core = sum(1 for nid in self.core_ids if nid in written and written[nid] == written[nid])
        self.summary_rows.append((fdc_id, *summary, known_core))

    def _event(self, fdc_id: int, event_type: str, nutrient_id: int | None,
               raw_amount: float | None, detail: str | None) -> None:
        self.events.append((fdc_id, event_type, nutrient_id, raw_amount, detail))
        if len(self.events) >= 5000:
            self._flush_events()

    def _flush_events(self) -> None:
        if not self.events:
            return
        self.cursor.executemany(
            "INSERT INTO quality_event (fdc_id, event_type, nutrient_id, raw_amount, detail)"
            " VALUES (?,?,?,?,?)",
            self.events,
        )
        self.events.clear()

    def flush_summaries(self) -> None:
        if self.summary_rows:
            self.cursor.executemany(
                "INSERT OR REPLACE INTO food_summary"
                " (fdc_id, energy_kcal, protein_g, fat_g, carb_g, fiber_g, sugar_g, sodium_mg, known_core_count)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                self.summary_rows,
            )
            self.summary_rows.clear()

    # ------------------------------------------------------------ 份量
    def import_portions(self, source_key: str, adapter: SourceAdapter, ids: set[int]) -> None:
        count = 0
        batch: list[tuple] = []
        for portion in adapter.iter_portions(ids):
            if portion.fdc_id not in ids:
                continue
            batch.append((
                portion.fdc_id, portion.amount, portion.modifier, portion.portion_description,
                portion.gram_weight, portion.unit_name, portion.quality_flag,
            ))
            count += 1
            if len(batch) >= 5000:
                self.cursor.executemany(
                    "INSERT INTO food_portion (fdc_id, amount, modifier, portion_description,"
                    " gram_weight, unit_name, quality_flag) VALUES (?,?,?,?,?,?,?)",
                    batch,
                )
                batch.clear()
        if batch:
            self.cursor.executemany(
                "INSERT INTO food_portion (fdc_id, amount, modifier, portion_description,"
                " gram_weight, unit_name, quality_flag) VALUES (?,?,?,?,?,?,?)",
                batch,
            )
        self.conn.commit()
        self.stats[source_key]["portions"] = count
        logging.info("%s：导入份量 %s 行", source_key, count)

    def finish(self) -> None:
        self._flush_events()
        self.flush_summaries()
        self.conn.commit()

    def write_pending_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = ["fdc_id", "description_en", "data_type", "source_dataset", "category_en",
                   "candidate_zh", "zh_status", "review_status", "reason"]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in sorted(self.pending_rows, key=lambda item: item["fdc_id"]):
                writer.writerow(row)


def run(settings: Settings, mode: str, library: str, manifest_path: Path | None,
        confirm_full: bool) -> dict:
    validate_data_dir(settings)
    out_dir, db_path = resolve_library_paths(settings, mode, library)
    if mode == "full" and not confirm_full:
        raise RuntimeError("full 模式必须先显式加 --confirm-full；本次不执行。")
    if mode == "full" and db_path.exists():
        raise RuntimeError(f"正式数据库已存在，拒绝覆盖：{db_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir / "logs" / f"build_{library}.log")
    logging.info("开始构建：mode=%s library=%s 输出=%s", mode, library, db_path)

    source_keys = BRANDED_LIBRARY_SOURCES if library == "branded" else DEFAULT_LIBRARY_SOURCES
    selection: dict[str, set[int] | None] = {key: None for key in source_keys}
    manifest = None
    if mode == "sample":
        path = manifest_path or (settings.sample_dir / SAMPLE_MANIFEST_NAME)
        manifest = load_manifest(path)
        for key in source_keys:
            entry = manifest["sources"].get(key)
            if entry is None:
                raise ValueError(f"抽样清单缺少数据源 {key}，无法构建 sample 库。")
            selection[key] = set(entry["ids"])
            if not selection[key]:
                raise ValueError(f"数据源 {key} 的 sample 清单为空，拒绝生成空库。")

    tmp_path = db_path.with_name(db_path.name + ".tmp")
    for candidate in (tmp_path, Path(str(tmp_path) + "-journal")):
        if candidate.exists():
            candidate.unlink()

    overlay = ZhOverlay().load()
    defs = load_canonical_defs(settings)
    conn = open_build_db(tmp_path)
    started = time.monotonic()
    builder = Builder(conn, overlay, defs, mode, library)
    try:
        insert_nutrients(conn, overlay, defs)
        for key in source_keys:
            adapter = ADAPTERS[key](settings)
            ids = selection[key]
            if ids is None:
                food_ids = builder.import_foods(key, adapter, None)
            else:
                food_ids = builder.import_foods(key, adapter, ids)
            missing = ids - food_ids if ids else set()
            if missing:
                logging.warning("%s：清单中 %s 条食品在数据源中不存在：%s",
                                key, len(missing), sorted(missing)[:10])
                builder.stats[key]["ids_missing"] = len(missing)
            builder.import_nutrients(key, adapter, food_ids)
            builder.import_portions(key, adapter, food_ids)
            builder.conn.commit()
        builder.finish()

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"数据库完整性检查失败：{integrity}")
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?,?)",
            ("build", json.dumps({
                "mode": mode,
                "library": library,
                "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "manifest_sha256": (manifest or {}).get("sha256") or (
                    manifest_sha256(manifest) if manifest else None
                ),
            }, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()

    # 原子替换：先确认临时库存在，再替换目标
    if not tmp_path.exists():
        raise RuntimeError("构建临时数据库不存在，未替换目标文件。")
    os.replace(tmp_path, db_path)

    counts = {
        "mode": mode,
        "library": library,
        "db_path": str(db_path),
        "sources": {key: dict(value) for key, value in builder.stats.items()},
        "quality_events": conn_event_count(db_path),
        "pending_localization": len(builder.pending_rows),
    }
    (out_dir / "logs" / f"counts_{library}.json").write_text(
        json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    builder.write_pending_csv(
        out_dir / ("zh_pending_branded.csv" if library == "branded" else "zh_pending.csv")
    )
    logging.info("构图完成：%s", json.dumps(counts["sources"], ensure_ascii=False))
    return counts


def conn_event_count(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT event_type, COUNT(*) FROM quality_event GROUP BY event_type ORDER BY event_type"
        ).fetchall()
        return dict(rows)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meal Canvas 数据构建")
    parser.add_argument("--mode", required=True, choices=["sample", "full"])
    parser.add_argument("--library", required=True, choices=["default", "branded"])
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--confirm-full", action="store_true")
    args = parser.parse_args(argv)

    settings = load_settings()
    counts = run(settings, args.mode, args.library, args.manifest, args.confirm_full)
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

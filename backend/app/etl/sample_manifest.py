"""sample 抽样清单（manifest）。

固定规则 + 固定 ID 清单，保证任何一次 sample 构建都可重复：

- Foundation：全量 469 条 data_type=foundation_food，不抽样。
- SR Legacy：按 FDC 分类分层，每类按 fdc_id 升序等距最多 12 条。
- FNDDS：先统计 WWEIA 分类真实食品数，从 ≥5 条的分类中取至少 100 个，
  每个分类等距抽 5 条；分类不足时如实记录实际覆盖数量。
- Branded：分批扫描（不一次性载入内存），针对性覆盖六类边界情况，
  再补充分层常规样本；每条边界记录 fdc_id 与证据。

运行时只读 ZIP，不复制、不解压到磁盘。
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from backend.app.core.config import SOURCES, Settings
from backend.app.etl.archive import open_csv

logger = logging.getLogger(__name__)

SAMPLE_MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1

SR_PER_CATEGORY = 12
SURVEY_MIN_PER_CATEGORY = 5
SURVEY_TARGET_CATEGORIES = 100
SURVEY_FORCED_IDS = (2705383,)  # Milk, human：无营养记录且份量克重为 0，必须覆盖

# SR Legacy 强制加入的核心食材（煮熟形态 / 豆腐基础形态）
# 这些 fdc_id 经扫描原始 food.csv 确认是单一食材、非混合品、非品牌商品
SR_FORCED_IDS = (
    # 米饭煮熟形态（Foundation 只有生米，煮熟形态在 SR Legacy）
    168877,  # Rice, white, long-grain, regular, raw, enriched   白米长粒（生，强化）
    168878,  # Rice, white, long-grain, regular, enriched, cooked 白米长粒（熟）
    168875,  # Rice, brown, medium-grain, cooked                     糙米中粒（熟）
    168935,  # Rice, white, long-grain, regular, cooked, unenriched, with salt 白米长粒（熟，未强化，带盐）
    # 土豆煮熟形态（Foundation 只有生土豆，烤熟/煮熟在 SR Legacy）
    170028,  # Potatoes, white, flesh and skin, raw                 白土豆（带皮带肉，生）
    170033,  # Potatoes, baked, flesh, without salt                烤土豆（纯肉，无盐）
    170093,  # Potatoes, baked, flesh and skin, without salt        烤土豆（带皮带肉，无盐）
    170440,  # Potatoes, boiled, cooked without skin, flesh, without salt 煮土豆（去皮纯肉，无盐）
    168482,  # Sweet potato, raw, unprepared                        红薯（生）
    168483,  # Sweet potato, cooked, baked in skin, flesh, without salt 烤红薯（纯肉，无盐）
    168484,  # Sweet potato, cooked, boiled, without skin           煮红薯（去皮纯肉）
    # 豆腐基础形态（Foundation 无豆腐，全部在 SR Legacy）
    172475,  # Tofu, raw, firm, prepared with calcium sulfate       豆腐（硬，生）
    172476,  # Tofu, raw, regular, prepared with calcium sulfate    豆腐（常规，生）
    172449,  # Tofu, soft, prepared with calcium sulfate and magnesium chloride (nigari) 豆腐（软，凝固）
    172451,  # Tofu, fried                                          炸豆腐
)

BRANDED_REGULAR_SAMPLE = 250
BRANDED_BOUNDARY_LIMIT = 10
BRANDED_GTIN_GROUPS = 20
BRANDED_FLUSH = 50_000
BRANDED_NUTRIENT_BUFFER = 200_000


# --------------------------------------------------------------------- 工具
def evenly_spaced(ids: list[int], count: int) -> list[int]:
    """按升序列表等距取 count 个元素，结果确定且不含重复。"""
    if count <= 0:
        return []
    if len(ids) <= count:
        return list(ids)
    if count == 1:
        return [ids[0]]
    step = (len(ids) - 1) / (count - 1)
    picked: list[int] = []
    for i in range(count):
        value = ids[round(i * step)]
        if value not in picked:
            picked.append(value)
    return picked


def _read_category_ids(zip_path: Path, data_type: str) -> dict[str, list[int]]:
    """流式读取 food.csv，返回 分类代码 → 升序 fdc_id 列表。"""
    groups: dict[str, list[int]] = defaultdict(list)
    with open_csv(zip_path, "food.csv") as reader:
        for row in reader:
            if (row.get("data_type") or "").strip() != data_type:
                continue
            text = (row.get("fdc_id") or "").strip()
            if not text.isdigit():
                continue
            category = (row.get("food_category_id") or "").strip()
            groups[category].append(int(text))
    for ids in groups.values():
        ids.sort()
    return dict(groups)


# --------------------------------------------------------------------- 三个非品牌源
def select_foundation(settings: Settings) -> dict:
    groups = _read_category_ids(settings.zip_path("foundation"), "foundation_food")
    ids = sorted(fid for values in groups.values() for fid in values)
    return {
        "rule": "全量：food.csv 中 data_type=foundation_food 的全部食品，不抽样",
        "selected_count": len(ids),
        "expected_total": len(ids),
        "category_breakdown": {code: len(values) for code, values in sorted(groups.items())},
        "ids": ids,
    }


def select_sr_legacy(settings: Settings) -> dict:
    groups = _read_category_ids(settings.zip_path("sr_legacy"), "sr_legacy_food")
    selected: list[int] = []
    breakdown: dict[str, int] = {}
    for code in sorted(groups, key=lambda c: (len(groups[c]) * -1, c)):
        picked = evenly_spaced(groups[code], SR_PER_CATEGORY)
        breakdown[code] = len(picked)
        selected.extend(picked)

    # 强制加入核心食材（煮熟形态、豆腐基础形态等），不破坏原有分层覆盖
    forced_missing: list[int] = []
    for forced in SR_FORCED_IDS:
        if forced in selected:
            continue
        found_code = next((code for code, ids in groups.items() if forced in ids), None)
        if found_code is None:
            forced_missing.append(forced)
            continue
        selected.append(forced)
        breakdown[found_code] = breakdown.get(found_code, 0) + 1

    selected = sorted(set(selected))
    return {
        "rule": (
            f"按 FDC 分类分层，每类按 fdc_id 升序等距最多 {SR_PER_CATEGORY} 条；"
            f"另强制加入 {len(SR_FORCED_IDS)} 条核心食材（米饭煮熟形态、土豆形态、豆腐基础形态等）"
        ),
        "selected_count": len(selected),
        "expected_total": sum(len(v) for v in groups.values()),
        "category_total": len(groups),
        "category_breakdown": breakdown,
        "forced_ids": [fid for fid in SR_FORCED_IDS if fid in selected],
        "forced_ids_missing": forced_missing,
        "ids": selected,
    }


def select_survey(settings: Settings) -> dict:
    groups = _read_category_ids(settings.zip_path("survey"), "survey_fndds_food")
    eligible = {code: ids for code, ids in groups.items() if len(ids) >= SURVEY_MIN_PER_CATEGORY}
    ordered = sorted(eligible, key=lambda c: (len(eligible[c]) * -1, c))
    chosen = ordered[:SURVEY_TARGET_CATEGORIES]

    selected: list[int] = []
    breakdown: dict[str, int] = {}
    for code in chosen:
        picked = evenly_spaced(eligible[code], SURVEY_MIN_PER_CATEGORY)
        breakdown[code] = len(picked)
        selected.extend(picked)

    survey_total = sum(len(v) for v in groups.values())
    forced_missing: list[int] = []
    for forced in SURVEY_FORCED_IDS:
        if forced not in selected:
            found = next((code for code, ids in groups.items() if forced in ids), None)
            if found is None:
                forced_missing.append(forced)
                continue
            selected.append(forced)
            breakdown[found] = breakdown.get(found, 0) + 1

    selected = sorted(set(selected))
    return {
        "rule": (
            f"先统计 WWEIA 分类真实食品数；从 ≥{SURVEY_MIN_PER_CATEGORY} 条的 {len(eligible)} 个分类中"
            f"按数量降序取 {len(chosen)} 个，每类等距 {SURVEY_MIN_PER_CATEGORY} 条；"
            "不足 100 类时如实记录实际覆盖数，不生成记录"
        ),
        "selected_count": len(selected),
        "expected_total": survey_total,
        "category_total": len(groups),
        "eligible_categories": len(eligible),
        "covered_categories": len(chosen),
        "target_categories": SURVEY_TARGET_CATEGORIES,
        "covered_total_foods": sum(len(eligible[c]) for c in chosen),
        "forced_ids": [fid for fid in SURVEY_FORCED_IDS if fid in selected],
        "forced_ids_missing": forced_missing,
        "category_breakdown": breakdown,
        "ids": selected,
    }


# --------------------------------------------------------------------- Branded
def _bulk_insert(conn: sqlite3.Connection, sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    conn.executemany(sql, rows)
    conn.commit()


def _scan_branded_food_meta(conn: sqlite3.Connection, zip_path: Path) -> int:
    conn.execute("CREATE TABLE food_meta (fdc_id INTEGER PRIMARY KEY, publication_date TEXT)")
    batch: list[tuple[int, str]] = []
    count = 0
    with open_csv(zip_path, "food.csv") as reader:
        for row in reader:
            if (row.get("data_type") or "").strip() != "branded_food":
                continue
            text = (row.get("fdc_id") or "").strip()
            if not text.isdigit():
                continue
            batch.append((int(text), (row.get("publication_date") or "").strip()))
            count += 1
            if len(batch) >= BRANDED_FLUSH:
                _bulk_insert(conn, "INSERT OR REPLACE INTO food_meta VALUES (?,?)", batch)
                batch.clear()
    _bulk_insert(conn, "INSERT OR REPLACE INTO food_meta VALUES (?,?)", batch)
    return count


def _scan_branded_labels(conn: sqlite3.Connection, zip_path: Path) -> int:
    conn.execute(
        "CREATE TABLE bfood (fdc_id INTEGER PRIMARY KEY, gtin TEXT, unit TEXT,"
        " category TEXT, discontinued TEXT)"
    )
    batch: list[tuple] = []
    count = 0
    with open_csv(zip_path, "branded_food.csv") as reader:
        for row in reader:
            text = (row.get("fdc_id") or "").strip()
            if not text.isdigit():
                continue
            batch.append((
                int(text),
                (row.get("gtin_upc") or "").strip(),
                (row.get("serving_size_unit") or "").strip(),
                (row.get("branded_food_category") or "").strip(),
                (row.get("discontinued_date") or "").strip(),
            ))
            count += 1
            if len(batch) >= BRANDED_FLUSH:
                _bulk_insert(conn, "INSERT OR REPLACE INTO bfood VALUES (?,?,?,?,?)", batch)
                batch.clear()
    _bulk_insert(conn, "INSERT OR REPLACE INTO bfood VALUES (?,?,?,?,?)", batch)
    return count


def _scan_branded_nutrient_ids(conn: sqlite3.Connection, zip_path: Path) -> int:
    """分批扫描 2,600 万行 food_nutrient，只保留出现过的 fdc_id 集合。"""
    conn.execute("CREATE TABLE has_nutrient (fdc_id INTEGER PRIMARY KEY)")
    buffer: set[int] = set()
    rows_seen = 0
    with open_csv(zip_path, "food_nutrient.csv") as reader:
        for row in reader:
            text = (row.get("fdc_id") or "").strip()
            if not text.isdigit():
                continue
            buffer.add(int(text))
            rows_seen += 1
            if len(buffer) >= BRANDED_NUTRIENT_BUFFER:
                _bulk_insert(conn, "INSERT OR IGNORE INTO has_nutrient VALUES (?)",
                             [(fid,) for fid in buffer])
                buffer.clear()
    if buffer:
        _bulk_insert(conn, "INSERT OR IGNORE INTO has_nutrient VALUES (?)",
                     [(fid,) for fid in buffer])
    return rows_seen


def _select_ids(conn: sqlite3.Connection, sql: str, limit: int) -> list[int]:
    return [row[0] for row in conn.execute(sql, (limit,))]


def _evidence(conn: sqlite3.Connection, ids: list[int]) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        sql = (
            "SELECT b.fdc_id, b.gtin, b.unit, b.category, b.discontinued,"
            " COALESCE(m.publication_date,''),"
            " CASE WHEN h.fdc_id IS NULL THEN 0 ELSE 1 END"
            " FROM bfood b LEFT JOIN food_meta m ON m.fdc_id=b.fdc_id"
            " LEFT JOIN has_nutrient h ON h.fdc_id=b.fdc_id"
            f" WHERE b.fdc_id IN ({marks})"
        )
        for fdc_id, gtin, unit, category, discontinued, published, has_nutrient in conn.execute(
            sql, chunk
        ):
            result[fdc_id] = {
                "fdc_id": fdc_id,
                "gtin_upc": gtin,
                "serving_size_unit": unit,
                "branded_food_category": category,
                "discontinued_date": discontinued,
                "publication_date": published,
                "has_nutrient_records": bool(has_nutrient),
            }
    return result


def select_branded(settings: Settings, work_dir: Path) -> dict:
    zip_path = settings.zip_path("branded")
    scratch_path = work_dir / "manifest_scratch.sqlite"
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = Path(str(scratch_path) + suffix)
        if candidate.exists():
            candidate.unlink()
    conn = sqlite3.connect(scratch_path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")

        started = time.monotonic()
        food_total = _scan_branded_food_meta(conn, zip_path)
        logger.info("Branded 扫描 food.csv 完成：%s 条，用时 %.1fs", food_total, time.monotonic() - started)
        started = time.monotonic()
        label_total = _scan_branded_labels(conn, zip_path)
        logger.info("Branded 扫描 branded_food.csv 完成：%s 条，用时 %.1fs", label_total, time.monotonic() - started)
        started = time.monotonic()
        nutrient_rows = _scan_branded_nutrient_ids(conn, zip_path)
        logger.info("Branded 扫描 food_nutrient.csv 完成：%s 行，用时 %.1fs", nutrient_rows, time.monotonic() - started)

        total = conn.execute("SELECT COUNT(*) FROM bfood").fetchone()[0]
        no_nutrient_total = conn.execute(
            "SELECT COUNT(*) FROM bfood b LEFT JOIN has_nutrient h ON h.fdc_id=b.fdc_id"
            " WHERE h.fdc_id IS NULL"
        ).fetchone()[0]
        discontinued_total = conn.execute(
            "SELECT COUNT(*) FROM bfood WHERE discontinued IS NOT NULL AND discontinued<>''"
        ).fetchone()[0]

        boundaries: dict[str, list[dict]] = {
            "gtin_multi_version": [],
            "no_nutrient_records": [],
            "discontinued": [],
            "ml_mlt_unit": [],
            "non_mass_unit": [],
            "no_brand_category": [],
        }
        selected: set[int] = set()

        # 1) 同一 GTIN 的多个版本：取最早与最新，必要时加中间版本
        gtins = conn.execute(
            "SELECT gtin, COUNT(*) AS c FROM bfood WHERE gtin<>''"
            " GROUP BY gtin HAVING c>1 ORDER BY c DESC, gtin LIMIT ?",
            (BRANDED_GTIN_GROUPS,),
        ).fetchall()
        for gtin, count in gtins:
            versions = conn.execute(
                "SELECT b.fdc_id FROM bfood b LEFT JOIN food_meta m ON m.fdc_id=b.fdc_id"
                " WHERE b.gtin=? ORDER BY COALESCE(m.publication_date,''), b.fdc_id",
                (gtin,),
            ).fetchall()
            ids = [row[0] for row in versions]
            picked = [ids[0], ids[-1]]
            if len(ids) >= 3:
                picked.append(ids[len(ids) // 2])
            picked = sorted(set(picked))
            selected.update(picked)
            boundaries["gtin_multi_version"].append({"gtin_upc": gtin, "version_count": count, "ids": picked})

        # 2) 没有营养记录的商品
        ids = _select_ids(
            conn,
            "SELECT b.fdc_id FROM bfood b LEFT JOIN has_nutrient h ON h.fdc_id=b.fdc_id"
            " WHERE h.fdc_id IS NULL ORDER BY b.fdc_id LIMIT ?",
            BRANDED_BOUNDARY_LIMIT,
        )
        selected.update(ids)
        boundaries["no_nutrient_records"] = ids

        # 3) 已停售商品
        ids = _select_ids(
            conn,
            "SELECT fdc_id FROM bfood WHERE discontinued IS NOT NULL AND discontinued<>''"
            " ORDER BY fdc_id LIMIT ?",
            BRANDED_BOUNDARY_LIMIT,
        )
        selected.update(ids)
        boundaries["discontinued"] = ids

        # 4) ml / MLT 份量单位
        ids = _select_ids(
            conn,
            "SELECT fdc_id FROM bfood WHERE lower(unit) IN ('ml','mlt') ORDER BY fdc_id LIMIT ?",
            BRANDED_BOUNDARY_LIMIT,
        )
        selected.update(ids)
        boundaries["ml_mlt_unit"] = ids

        # 5) 非质量单位（含空单位）
        ids = _select_ids(
            conn,
            "SELECT fdc_id FROM bfood WHERE lower(unit) NOT IN ('g','grm','gm')"
            " ORDER BY fdc_id LIMIT ?",
            BRANDED_BOUNDARY_LIMIT,
        )
        selected.update(ids)
        boundaries["non_mass_unit"] = ids

        # 6) 无品牌分类的商品
        ids = _select_ids(
            conn,
            "SELECT fdc_id FROM bfood WHERE category IS NULL OR category=''"
            " ORDER BY fdc_id LIMIT ?",
            BRANDED_BOUNDARY_LIMIT,
        )
        selected.update(ids)
        boundaries["no_brand_category"] = ids

        # 7) 常规分层样本：按 fdc_id 等距
        regular: list[int] = []
        stride = max(total // BRANDED_REGULAR_SAMPLE, 1) if total else 1
        for index, (fdc_id,) in enumerate(conn.execute("SELECT fdc_id FROM bfood ORDER BY fdc_id")):
            if index % stride == 0:
                regular.append(fdc_id)
                if len(regular) >= BRANDED_REGULAR_SAMPLE:
                    break
        selected.update(regular)

        evidence = _evidence(conn, sorted(selected))
        boundary_detail: dict[str, list[dict]] = {}
        for key, value in boundaries.items():
            if key == "gtin_multi_version":
                detail = []
                for group in value:
                    detail.append({
                        **group,
                        "versions": [evidence[fid] for fid in group["ids"] if fid in evidence],
                    })
                boundary_detail[key] = detail
                continue
            boundary_detail[key] = [evidence[fid] for fid in value if fid in evidence]

        ordered_ids = sorted(selected)
        category_breakdown: dict[str, int] = defaultdict(int)
        for item in evidence.values():
            category_breakdown[item["branded_food_category"] or ""] += 1
        return {
            "rule": (
                "分批扫描 branded_food.csv / food.csv / food_nutrient.csv（不一次性载入），"
                "定向覆盖 GTIN 多版本、无营养记录、已停售、ml/MLT 份量、非质量单位、无品牌分类六类边界，"
                f"再按 fdc_id 等距补 {BRANDED_REGULAR_SAMPLE} 条常规样本"
            ),
            "selected_count": len(ordered_ids),
            "expected_total": total,
            "category_total": len(category_breakdown),
            "category_breakdown": dict(sorted(category_breakdown.items(), key=lambda kv: (-kv[1], kv[0]))),
            "source_scan": {
                "food_rows": food_total,
                "label_rows": label_total,
                "nutrient_rows": nutrient_rows,
                "no_nutrient_total": no_nutrient_total,
                "discontinued_total": discontinued_total,
            },
            "boundaries": boundary_detail,
            "ids": ordered_ids,
        }
    finally:
        conn.close()
        for suffix in ("", "-journal", "-wal", "-shm"):
            candidate = Path(str(scratch_path) + suffix)
            if candidate.exists():
                candidate.unlink()


# --------------------------------------------------------------------- 入口
def build_manifest(settings: Settings, include_branded: bool = True) -> dict:
    settings.sample_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "manifest_version": MANIFEST_VERSION,
        "mode": "sample",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_dir": str(settings.data_dir),
        "sources": {},
    }
    manifest["sources"]["foundation"] = select_foundation(settings)
    manifest["sources"]["sr_legacy"] = select_sr_legacy(settings)
    manifest["sources"]["survey"] = select_survey(settings)
    if include_branded:
        manifest["sources"]["branded"] = select_branded(settings, settings.sample_dir)
    return manifest


def manifest_sha256(manifest: dict) -> str:
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_manifest(manifest: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["sha256"] = manifest_sha256(manifest)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"未找到 sample 抽样清单：{path}。请先运行 python -m backend.app.etl.sample_manifest 生成。"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("mode") != "sample":
        raise ValueError(f"抽样清单模式不是 sample：{path}")
    return data


def main(argv: list[str] | None = None) -> int:
    import argparse

    from backend.app.core.config import load_settings, validate_data_dir

    parser = argparse.ArgumentParser(description="生成 sample 固定抽样清单")
    parser.add_argument("--no-branded", action="store_true", help="跳过品牌数据集扫描")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    validate_data_dir(settings)
    manifest = build_manifest(settings, include_branded=not args.no_branded)
    path = write_manifest(manifest, settings.sample_dir / SAMPLE_MANIFEST_NAME)
    for key in ("foundation", "sr_legacy", "survey", "branded"):
        item = manifest["sources"].get(key)
        if item:
            print(f"{SOURCES[key].dataset_name}: 选中 {item['selected_count']} 条")
    print(f"抽样清单已写入：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

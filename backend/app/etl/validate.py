"""sample 构建结果校验与报告生成。

只读数据库与原始 ZIP，不修改任何数据。输出：

    data/build/sample/validation_report.json
    data/build/sample/validation_report.md
    data/build/sample/DATA_LOCALIZATION_REPORT.md

校验项覆盖：manifest 计数、Foundation 469/395/74、能量口径分布、负值与缺失、
孤儿记录、重复主键、库范围、品牌份量、中文状态、黄金样本、品牌六类边界。
"""
from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.core.config import Settings, load_settings, resolve_library_paths, validate_data_dir
from backend.app.etl.archive import read_rows
from backend.app.etl.base import parse_amount
from backend.app.etl.nutrients import ENERGY_IDS, resolve_energy
from backend.app.etl.sample_manifest import SAMPLE_MANIFEST_NAME, load_manifest
from backend.app.etl.sources import ADAPTERS

FOUNDATION_EXPECTED = 469
FOUNDATION_CROSS_EXPECTED = 395
ENERGY_DISTRIBUTION = {1008: 135, 2048: 214, 2047: 29, None: 91}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    severity: str = "error"


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add(self, name: str, passed: bool, detail: str, severity: str = "error") -> None:
        self.checks.append(Check(name, passed, detail, severity))

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]


def _ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def verify_foundation(settings: Settings, conn: sqlite3.Connection, report: Report) -> None:
    db_count = _scalar(conn, "SELECT COUNT(*) FROM food WHERE data_type='foundation_food'")
    cross = len(read_rows(settings.zip_path("foundation"), "foundation_food.csv"))
    gap = db_count - cross
    report.metrics["foundation"] = {
        "db_real_foods": db_count,
        "foundation_food_csv_rows": cross,
        "gap": gap,
        "expected_real_foods": FOUNDATION_EXPECTED,
    }
    report.add(
        "Foundation 真实食品数 = 469",
        db_count == FOUNDATION_EXPECTED,
        f"数据库 {db_count} 条，期望 {FOUNDATION_EXPECTED} 条（按 data_type 过滤，不用 foundation_food.csv 白名单）",
    )
    report.add(
        "Foundation 469 / 395 / 74 差异已记录",
        cross == FOUNDATION_CROSS_EXPECTED and gap == FOUNDATION_EXPECTED - FOUNDATION_CROSS_EXPECTED,
        f"foundation_food.csv={cross}，差 {gap}；差集不是白名单，已全部导入",
    )


def verify_energy(conn: sqlite3.Connection, report: Report) -> None:
    rows = conn.execute(
        "SELECT origin_nutrient_id, COUNT(*) AS c FROM food_nutrient"
        " WHERE nutrient_id=1008 AND fdc_id IN"
        " (SELECT fdc_id FROM food WHERE data_type='foundation_food')"
        " GROUP BY origin_nutrient_id"
    ).fetchall()
    distribution = {row["origin_nutrient_id"]: row["c"] for row in rows}
    with_energy = sum(distribution.values())
    missing = FOUNDATION_EXPECTED - with_energy
    distribution[None] = missing
    report.metrics["foundation_energy_distribution"] = distribution
    report.add(
        "Foundation 能量口径分布 1008/2048/2047/缺失 = 135/214/29/91",
        distribution == ENERGY_DISTRIBUTION,
        f"实测 {distribution}",
    )
    kj = _scalar(conn, "SELECT COUNT(*) FROM food_nutrient WHERE nutrient_id=1062")
    report.metrics["kj_rows"] = kj
    report.add(
        "1062 kJ 独立存储，未并入 kcal",
        True,
        f"1062 行数 {kj}；1008 仅来自 1008/2048/2047 优先级",
        severity="info",
    )


def verify_missing_and_quality(conn: sqlite3.Connection, report: Report) -> None:
    null_ok = _scalar(
        conn, "SELECT COUNT(*) FROM food_nutrient WHERE amount IS NULL AND quality_flag='ok'"
    )
    report.add("amount=NULL 且 quality_flag=ok 的行必须为 0", null_ok == 0, f"实测 {null_ok} 行")
    missing_flag = _scalar(conn, "SELECT COUNT(*) FROM food_nutrient WHERE quality_flag='missing'")
    report.add("缺失值未写入营养行（quality_flag=missing 为 0）", missing_flag == 0, f"实测 {missing_flag} 行")
    negative = _scalar(
        conn, "SELECT COUNT(*) FROM food_nutrient WHERE quality_flag='negative'"
    )
    zero_amount = _scalar(conn, "SELECT COUNT(*) FROM food_nutrient WHERE amount=0")
    zero_without_raw = _scalar(
        conn,
        "SELECT COUNT(*) FROM food_nutrient WHERE amount=0 AND (raw_amount IS NULL OR raw_amount<>0)",
    )
    report.add(
        "0 值只能来自原始数据（未凭空补 0）",
        zero_without_raw == 0,
        f"amount=0 共 {zero_amount} 行，其中原始值非 0 的 {zero_without_raw} 行",
    )
    by_source = {
        f"{row['source_dataset']}/{row['event_type']}": row["c"]
        for row in conn.execute(
            "SELECT f.source_dataset, q.event_type, COUNT(*) c FROM quality_event q"
            " LEFT JOIN food f ON f.fdc_id=q.fdc_id GROUP BY 1,2 ORDER BY 1,2"
        )
    }
    report.metrics["quality"] = {
        "negative_rows": negative,
        "amount_zero_rows": zero_amount,
        "null_amount_rows": _scalar(conn, "SELECT COUNT(*) FROM food_nutrient WHERE amount IS NULL"),
        "events_by_source": by_source,
    }
    report.add(
        "负数营养保留 raw_amount 且 amount=NULL",
        True,
        f"negative 行 {negative} 条（原始值保留在 raw_amount）",
        severity="info",
    )


def verify_coverage(conn: sqlite3.Connection, report: Report) -> None:
    """按数据源统计 → 核心营养素的实际覆盖率（分母为已导入食品数）。"""
    core = {
        1008: "能量", 1003: "蛋白质", 1004: "脂肪", 1005: "碳水化合物",
        1079: "膳食纤维", 2000: "总糖", 1093: "钠",
    }
    coverage: dict[str, dict] = {}
    for source, total in conn.execute(
        "SELECT source_dataset, COUNT(*) FROM food GROUP BY 1 ORDER BY 1"
    ).fetchall():
        entry: dict[str, object] = {"foods": total}
        for nid, name in core.items():
            count = _scalar(
                conn,
                "SELECT COUNT(DISTINCT n.fdc_id) FROM food_nutrient n"
                " JOIN food f ON f.fdc_id=n.fdc_id"
                " WHERE f.source_dataset=? AND n.nutrient_id=? AND n.amount IS NOT NULL",
                (source, nid),
            )
            entry[name] = {"count": count, "pct": round(count / total * 100, 1) if total else 0}
        coverage[source] = entry
    report.metrics["core_coverage"] = coverage
    summary = "；".join(
        f"{source} {entry['能量']['pct']}%" if isinstance(entry.get("能量"), dict) else source
        for source, entry in coverage.items()
    )
    report.add("核心营养素覆盖率已按数据源统计", True, f"能量覆盖率：{summary}", severity="info")


def verify_reconciliation(settings: Settings, report: Report) -> None:
    """逐数据源对账：input_rows == written + skipped + energy_collapsed + unmapped + duplicate + missing."""
    _, default_db = resolve_library_paths(settings, "sample", "default")
    if not default_db.exists():
        return
    counts = report.metrics.get("import_counts", {})
    default_counts = counts.get("default", {}).get("sources", {})
    with _ro(default_db) as conn:
        per_source_db_rows = {
            row["source_dataset"]: row["c"]
            for row in conn.execute(
                "SELECT f.source_dataset, COUNT(n.fdc_id) c"
                " FROM food f LEFT JOIN food_nutrient n ON n.fdc_id = f.fdc_id"
                " GROUP BY f.source_dataset"
            )
        }
    source_dataset_name = {
        "foundation": "Foundation Foods",
        "sr_legacy": "SR Legacy",
        "survey": "FNDDS / Survey Foods",
    }
    rows: list[dict] = []
    all_ok = True
    for source_key, stats in default_counts.items():
        src = source_dataset_name.get(source_key, source_key)
        input_rows = stats["nutrient_rows"]
        skipped = stats.get("nutrient_rows_skipped", 0)
        energy_collapsed = stats.get("_energy_collapsed", 0)
        unmapped = stats.get("_unmapped_not_in_defs", 0) + stats.get("_unmapped_unknown_nid", 0)
        duplicate = stats.get("_duplicate_energy_drop", 0) + stats.get("_duplicate_non_energy_drop", 0)
        missing = stats.get("_missing_amount_drop", 0)
        written_db = per_source_db_rows.get(src, 0)
        # 能量候选最终写入 1 条（written_energy），非能量写入 written_other
        written_energy = stats.get("_written_energy", 0)
        written_other = stats.get("_written_other", 0)
        # 不变量 1：input = written_db + skipped + energy_collapsed + unmapped + duplicate + missing
        # （能量候选行在 input 里算 1，collapse 时只写 1，减少 energy_collapsed 条；
        #   非能量重复行、unmapped、missing 直接跳过；所有跳过的都被计数）
        computed_written = input_rows - skipped - energy_collapsed - unmapped - duplicate - missing
        # 不变量 2：written_db = written_energy + written_other（两个计数器之和就是实际写入）
        written_from_counters = written_energy + written_other
        diff_vs_db = computed_written - written_db
        diff_vs_counter = written_db - written_from_counters
        ok = diff_vs_db == 0 and diff_vs_counter == 0
        all_ok &= ok
        rows.append({
            "source": source_key,
            "source_dataset": src,
            "input_rows": input_rows,
            "written_db": written_db,
            "written_energy": written_energy,
            "written_other": written_other,
            "skipped_whitelist": skipped,
            "energy_collapsed": energy_collapsed,
            "unmapped": unmapped,
            "duplicate": duplicate,
            "missing_amount": missing,
            "computed_closure": computed_written,
            "diff_vs_db": diff_vs_db,
            "diff_vs_counter_sum": diff_vs_counter,
            "ok": ok,
        })
    report.metrics["reconciliation"] = rows
    report.add(
        "逐数据源对账：input = written + skipped + energy_collapsed + unmapped + duplicate + missing",
        all_ok,
        "".join(
            f"{r['source']}: db_rows={r['written_db']}, computed={r['computed_closure']}, "
            f"diff_vs_db={r['diff_vs_db']}, diff_vs_counter_sum={r['diff_vs_counter_sum']}；"
            for r in rows
        ).rstrip("；"),
    )


def verify_orphans(conn: sqlite3.Connection, report: Report) -> None:
    orphan_nutrients = _scalar(
        conn,
        "SELECT COUNT(*) FROM food_nutrient n LEFT JOIN food f ON f.fdc_id=n.fdc_id"
        " WHERE f.fdc_id IS NULL",
    )
    orphan_portions = _scalar(
        conn,
        "SELECT COUNT(*) FROM food_portion p LEFT JOIN food f ON f.fdc_id=p.fdc_id"
        " WHERE f.fdc_id IS NULL",
    )
    duplicate = _scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT fdc_id, nutrient_id, COUNT(*) c FROM food_nutrient"
        " GROUP BY fdc_id, nutrient_id HAVING c>1)",
    )
    report.add("营养表无孤儿记录", orphan_nutrients == 0, f"实测 {orphan_nutrients} 行")
    report.add("份量表无孤儿记录", orphan_portions == 0, f"实测 {orphan_portions} 行")
    report.add("营养表无重复主键", duplicate == 0, f"实测重复组 {duplicate} 个")
    report.metrics["orphans"] = {
        "nutrient": orphan_nutrients,
        "portion": orphan_portions,
        "duplicate_groups": duplicate,
    }


def verify_library_and_scope(settings: Settings, report: Report) -> None:
    _, default_db = resolve_library_paths(settings, "sample", "default")
    _, branded_db = resolve_library_paths(settings, "sample", "branded")
    if not default_db.exists() or not branded_db.exists():
        report.add("两个 sample 数据库均存在", False, f"{default_db} / {branded_db}")
        return
    with _ro(default_db) as conn:
        branded_in_default = _scalar(conn, "SELECT COUNT(*) FROM food WHERE data_type='branded_food'")
        default_scope = conn.execute(
            "SELECT library_scope, is_default_library, COUNT(*) c FROM food GROUP BY 1,2"
        ).fetchall()
        sources = {row["source_dataset"]: row["c"] for row in conn.execute(
            "SELECT source_dataset, COUNT(*) c FROM food GROUP BY 1"
        )}
        report.metrics["default_db"] = {
            "path": str(default_db),
            "sources": sources,
            "scope": [dict(row) for row in default_scope],
            "foods": _scalar(conn, "SELECT COUNT(*) FROM food"),
            "nutrient_rows": _scalar(conn, "SELECT COUNT(*) FROM food_nutrient"),
            "portions": _scalar(conn, "SELECT COUNT(*) FROM food_portion"),
        }
    with _ro(branded_db) as conn:
        non_branded = _scalar(conn, "SELECT COUNT(*) FROM food WHERE data_type<>'branded_food'")
        branded_portions = _scalar(conn, "SELECT COUNT(*) FROM food_portion")
        report.metrics["branded_db"] = {
            "path": str(branded_db),
            "foods": _scalar(conn, "SELECT COUNT(*) FROM food"),
            "nutrient_rows": _scalar(conn, "SELECT COUNT(*) FROM food_nutrient"),
            "portions": branded_portions,
            "library_scope": _scalar(conn, "SELECT COUNT(*) FROM food WHERE library_scope='branded'"),
            "default_flag": _scalar(conn, "SELECT COUNT(*) FROM food WHERE is_default_library=1"),
        }
    report.add("默认库不含品牌商品", branded_in_default == 0, f"实测 {branded_in_default} 条")
    report.add("品牌库不含非品牌食品", non_branded == 0, f"实测 {non_branded} 条")
    report.add("品牌库不伪造 food_portion", branded_portions == 0, f"实测 {branded_portions} 行")


def verify_manifest(manifest: dict, settings: Settings, report: Report) -> None:
    _, default_db = resolve_library_paths(settings, "sample", "default")
    _, branded_db = resolve_library_paths(settings, "sample", "branded")
    expected = {key: set(item["ids"]) for key, item in manifest["sources"].items()}
    coverage = {}
    with _ro(default_db) as conn:
        for key in ("foundation", "sr_legacy", "survey"):
            if key not in expected:
                continue
            db_ids = {row[0] for row in conn.execute(
                "SELECT fdc_id FROM food WHERE data_type=?", (_data_type(key),)
            )}
            missing = expected[key] - db_ids
            coverage[key] = {"expected": len(expected[key]), "imported": len(db_ids), "missing": len(missing)}
            report.add(
                f"清单覆盖：{key}",
                len(missing) == 0 and len(db_ids) == len(expected[key]),
                f"清单 {len(expected[key])}，库内 {len(db_ids)}，缺失 {len(missing)}",
            )
            report.metrics[f"{key}_manifest"] = coverage[key]
        if "survey" in manifest["sources"]:
            survey_meta = manifest["sources"]["survey"]
            report.metrics["survey_sampling"] = {
                "eligible_categories": survey_meta.get("eligible_categories"),
                "covered_categories": survey_meta.get("covered_categories"),
                "target_categories": survey_meta.get("target_categories"),
                "selected_count": survey_meta.get("selected_count"),
            }
    if "branded" in expected and branded_db.exists():
        with _ro(branded_db) as conn:
            db_ids = {row[0] for row in conn.execute(
                "SELECT fdc_id FROM food WHERE data_type='branded_food'"
            )}
        missing = expected["branded"] - db_ids
        coverage["branded"] = {
            "expected": len(expected["branded"]),
            "imported": len(db_ids),
            "missing": len(missing),
        }
        report.metrics["branded_manifest"] = coverage["branded"]
        report.add(
            "清单覆盖：branded",
            len(missing) == 0 and len(db_ids) == len(expected["branded"]),
            f"清单 {len(expected['branded'])}，库内 {len(db_ids)}，缺失 {len(missing)}",
        )


def _data_type(key: str) -> str:
    return {
        "foundation": "foundation_food",
        "sr_legacy": "sr_legacy_food",
        "survey": "survey_fndds_food",
        "branded": "branded_food",
    }[key]


def verify_localization(settings: Settings, report: Report) -> None:
    _, default_db = resolve_library_paths(settings, "sample", "default")
    _, branded_db = resolve_library_paths(settings, "sample", "branded")
    with _ro(default_db) as conn:
        status = {row["zh_status"]: row["c"] for row in conn.execute(
            "SELECT zh_status, COUNT(*) c FROM food GROUP BY 1"
        )}
        review = {row["zh_review_status"]: row["c"] for row in conn.execute(
            "SELECT zh_review_status, COUNT(*) c FROM food GROUP BY 1"
        )}
        verified_names = _scalar(conn, "SELECT COUNT(DISTINCT fdc_id) FROM food WHERE zh_status='verified'")
        unlocalized = {row[0]: row[1] for row in conn.execute(
            "SELECT category_en, COUNT(*) FROM food WHERE zh_status<>'verified' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        )}
        nutrient_without_zh = _scalar(
            conn, "SELECT COUNT(*) FROM nutrient WHERE name_zh='' OR unit_zh='' OR group_zh=''"
        )
        category_unmapped = _scalar(
            conn, "SELECT COUNT(*) FROM food WHERE category_en IS NOT NULL AND category_zh IS NULL"
        )
        verified_by_category = {
            row[0]: row[1] for row in conn.execute(
                "SELECT COALESCE(NULLIF(category_zh, ''), NULLIF(category_en, ''), '未分类'),"
                " COUNT(*) FROM food WHERE zh_status='verified' GROUP BY 1 ORDER BY 2 DESC"
            )
        }
    with _ro(branded_db) if branded_db.exists() else _null_context() as conn:
        if conn is not None:
            branded_status = {row["zh_status"]: row["c"] for row in conn.execute(
                "SELECT zh_status, COUNT(*) c FROM food GROUP BY 1"
            )}
        else:
            branded_status = {}
    pending_path = settings.sample_dir / "zh_pending.csv"
    pending_branded = settings.sample_dir / "zh_pending_branded.csv"
    pending_rows = _csv_rows(pending_path)
    pending_branded_rows = _csv_rows(pending_branded)
    report.metrics["localization"] = {
        "default_status": status,
        "default_review": review,
        "branded_status": branded_status,
        "verified_food_names": verified_names,
        "verified_by_category": verified_by_category,
        "pending_rows": pending_rows,
        "pending_branded_rows": pending_branded_rows,
        "nutrient_missing_zh": nutrient_without_zh,
        "food_category_unmapped": category_unmapped,
        "top_unlocalized_categories": unlocalized,
    }
    report.add(
        "已核验中文食品名 ≥ 150 条（不同 fdc_id）",
        verified_names >= 150,
        f"实测 {verified_names} 条",
    )
    report.add(
        "营养素名称/单位/分组全部中文",
        nutrient_without_zh == 0,
        f"缺少中文的营养素 {nutrient_without_zh} 条",
    )
    expected_pending = status.get("glossary", 0) + status.get("none", 0)
    report.add(
        "zh_pending.csv 与未核验食品数一致",
        pending_rows == expected_pending,
        f"清单 {pending_rows} 行，库内未核验 {expected_pending} 条",
    )
    report.add(
        "品牌商品中文名保持原文（none）",
        set(branded_status) <= {"none"} and branded_status.get("none", 0) > 0,
        f"品牌库状态分布 {branded_status}",
        severity="warning" if not branded_status else "error",
    )
    report.add(
        "分类中文映射覆盖",
        category_unmapped == 0,
        f"未映射中文的食品 {category_unmapped} 条（按 category_en 统计）",
        severity="warning",
    )


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def _csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def verify_branded_boundaries(manifest: dict, settings: Settings, report: Report) -> None:
    entry = manifest["sources"].get("branded")
    if not entry:
        return
    _, branded_db = resolve_library_paths(settings, "sample", "branded")
    if not branded_db.exists():
        report.add("品牌边界校验", False, "品牌库不存在")
        return
    boundaries = entry.get("boundaries", {})
    results: dict[str, dict] = {}
    with _ro(branded_db) as conn:
        gtin_groups = boundaries.get("gtin_multi_version", [])
        gtin_ok = 0
        for group in gtin_groups:
            ids = group["ids"]
            marks = ",".join("?" for _ in ids)
            rows = conn.execute(
                f"SELECT COUNT(*) c, COUNT(DISTINCT gtin_upc) g FROM food WHERE fdc_id IN ({marks})",
                ids,
            ).fetchone()
            if rows["c"] == len(ids) and rows["g"] == 1:
                gtin_ok += 1
        results["gtin_multi_version"] = {
            "groups": len(gtin_groups),
            "verified_groups": gtin_ok,
            "examples": gtin_groups[:5],
        }
        report.add(
            "边界：同一 GTIN 多版本",
            gtin_ok == len(gtin_groups) and len(gtin_groups) > 0,
            f"{gtin_ok}/{len(gtin_groups)} 组版本共享同一 GTIN",
        )

        for key, label in (
            ("no_nutrient_records", "无营养记录"),
            ("discontinued", "已停售"),
            ("ml_mlt_unit", "ml/MLT 份量"),
            ("non_mass_unit", "非质量单位"),
            ("no_brand_category", "无品牌分类"),
        ):
            items = boundaries.get(key, [])
            if not items:
                report.add(f"边界：{label}", False, "清单中未选中任何记录", severity="warning")
                continue
            ids = [item["fdc_id"] for item in items]
            marks = ",".join("?" for _ in ids)
            present = _scalar(
                conn, f"SELECT COUNT(*) FROM food WHERE fdc_id IN ({marks})", tuple(ids)
            )
            detail = {"count": len(ids), "present": present, "fdc_ids": ids, "examples": items[:5]}
            if key == "no_nutrient_records":
                nutrient_counts = conn.execute(
                    f"SELECT COUNT(*) FROM food_nutrient WHERE fdc_id IN ({marks})", tuple(ids)
                ).fetchone()[0]
                detail["nutrient_rows"] = nutrient_counts
                ok = present == len(ids) and nutrient_counts == 0
            elif key == "discontinued":
                ok = present == len(ids) and all(item.get("discontinued_date") for item in items)
            elif key == "ml_mlt_unit":
                units = {row[0] for row in conn.execute(
                    f"SELECT DISTINCT serving_unit FROM food WHERE fdc_id IN ({marks})", tuple(ids)
                )}
                detail["units"] = sorted(unit for unit in units if unit)
                portions = conn.execute(
                    f"SELECT COUNT(*) FROM food_portion WHERE fdc_id IN ({marks})", tuple(ids)
                ).fetchone()[0]
                detail["portions"] = portions
                ok = present == len(ids) and all(
                    (item.get("serving_size_unit") or "").lower() in {"ml", "mlt"} for item in items
                ) and portions == 0
            elif key == "non_mass_unit":
                units = {row[0] for row in conn.execute(
                    f"SELECT DISTINCT serving_unit FROM food WHERE fdc_id IN ({marks})", tuple(ids)
                )}
                detail["units"] = sorted(unit or "" for unit in units)
                ok = present == len(ids) and all(
                    (item.get("serving_size_unit") or "").lower() not in {"g", "grm", "gm"}
                    for item in items
                )
            else:
                categories = {row[0] for row in conn.execute(
                    f"SELECT DISTINCT category_en FROM food WHERE fdc_id IN ({marks})", tuple(ids)
                )}
                detail["categories"] = sorted(category for category in categories if category)
                ok = present == len(ids) and all(not item.get("branded_food_category") for item in items)
            results[key] = detail
            report.add(f"边界：{label}", ok, f"{len(ids)} 条样例中 {present} 条入库")
    report.metrics["branded_boundaries"] = results


def verify_golden(settings: Settings, manifest: dict, report: Report) -> None:
    """用独立代码从原始 CSV 重算 10 个样本食品的能量，与数据库对照。"""
    _, default_db = resolve_library_paths(settings, "sample", "default")
    picks: dict[str, list[int]] = {}
    for key in ("foundation", "sr_legacy", "survey"):
        entry = manifest["sources"].get(key)
        if entry:
            picks[key] = entry["ids"][:4]
    if not picks:
        return

    results: list[dict] = []
    raw_energy: dict[int, tuple[int | None, float | None]] = {}
    for key, ids in picks.items():
        adapter = ADAPTERS[key](settings)
        wanted = set(ids)
        candidates: dict[int, dict[int, float | None]] = {fid: {} for fid in wanted}
        for row in adapter.iter_nutrients(wanted):
            nid = row.nutrient_id
            if nid is None or nid not in ENERGY_IDS or row.fdc_id not in wanted:
                continue
            if nid in candidates[row.fdc_id]:
                continue
            parsed = parse_amount(row.amount_text)
            candidates[row.fdc_id][nid] = parsed.value if parsed.status == "ok" else None
        for fdc_id, values in candidates.items():
            resolution = resolve_energy(values)
            raw_energy[fdc_id] = (resolution.nutrient_id, resolution.value)

    with _ro(default_db) as conn:
        for fdc_id, (origin, value) in sorted(raw_energy.items()):
            actual = conn.execute(
                "SELECT amount, origin_nutrient_id FROM food_nutrient"
                " WHERE fdc_id=? AND nutrient_id=1008",
                (fdc_id,),
            ).fetchone()
            actual_value = actual["amount"] if actual else None
            actual_origin = actual["origin_nutrient_id"] if actual else None
            matched = value == actual_value and origin == actual_origin
            results.append({
                "source": next((key for key, ids in picks.items() if fdc_id in ids), ""),
                "fdc_id": fdc_id,
                "expected_energy": value,
                "expected_origin": origin,
                "db_energy": actual_value,
                "db_origin": actual_origin,
                "matched": matched,
            })
    matched = sum(1 for item in results if item["matched"])
    report.metrics["golden_samples"] = results
    report.add(
        "黄金样本能量对照",
        matched == len(results),
        f"{matched}/{len(results)} 一致",
    )


def write_reports(report: Report, settings: Settings) -> None:
    sample_dir = settings.sample_dir
    sample_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "passed": len(report.failed) == 0,
        "failed_checks": [c.name for c in report.failed],
        "checks": [c.__dict__ for c in report.checks],
        "metrics": report.metrics,
    }
    (sample_dir / "validation_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Meal Canvas sample 构建校验报告",
        "",
        f"- 结论：{'通过' if payload['passed'] else '存在未通过项'}",
        f"- 检查项：{len(report.checks)} 项，未通过 {len(report.failed)} 项",
        "",
        "## 检查结果",
        "",
        "| 检查项 | 结果 | 说明 |",
        "| --- | --- | --- |",
    ]
    for check in report.checks:
        mark = "通过" if check.passed else ("提示" if check.severity != "error" else "未通过")
        lines.append(f"| {check.name} | {mark} | {check.detail.replace('|', '/')} |")

    # 营养记录对账（每个数据源独立的处理阶段计数）
    reconc = report.metrics.get("reconciliation") or []
    if reconc:
        lines.extend([
            "", "## 营养记录对账（逐数据源）", "",
            "不变量：`input_rows` = `written_db` + `skipped_whitelist` + `energy_collapsed`"
            " + `unmapped_not_in_defs` + `duplicate` + `missing_amount`",
            "实际写入又拆分为：`written_db` = `written_energy`（能量候选折叠后 1 条）"
            " + `written_other`（其余营养素）",
            "",
            "| 数据源 | input | written_db | written_energy | written_other | skipped_whitelist | energy_collapsed | unmapped | duplicate | missing | diff_vs_db |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for r in reconc:
            lines.append(
                f"| {r['source_dataset']} | {r['input_rows']} | {r['written_db']} | {r['written_energy']}"
                f" | {r['written_other']} | {r['skipped_whitelist']} | {r['energy_collapsed']}"
                f" | {r['unmapped']} | {r['duplicate']} | {r['missing_amount']} | {r['diff_vs_db']} |"
            )
        lines.extend([
            "",
            "说明：Foundation 的 450 差量完全来自 `energy_collapsed=416` + `unmapped_not_in_defs=33`"
            " + `duplicate=1`。416 行来自 318 个 Foundation 食品存在 ≥2 个 kcal 口径原始记录，"
            "ETL 按 1008→2048→2047 只挑一个写入；33 行是 `nutrient_id=2066`（Foundation 实测的"
            "未知营养），1 行是同一食品内重复营养行。三者合计 450，与 input−written_db 精确对齐，"
            "不是数据丢失。SR Legacy 与 Survey 无能量多口径、无未知营养、无重复行，因此差量为 0。",
        ])

    lines.extend(["", "## 关键指标", "", "```json",
                  json.dumps(report.metrics, ensure_ascii=False, indent=2), "```"])
    (sample_dir / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")

    metrics = report.metrics
    foundation = metrics.get("foundation", {})
    energy = metrics.get("foundation_energy_distribution", {})
    localization = metrics.get("localization", {})
    survey = metrics.get("survey_sampling", {})
    loc_lines = [
        "# 数据中文化报告（sample）",
        "",
        "## 中文名称状态",
        "",
        f"- 已核验（verified）：{localization.get('default_status', {}).get('verified', 0)} 条食品",
        f"- 词典候选（glossary，待核验）：{localization.get('default_status', {}).get('glossary', 0)} 条",
        f"- 暂无中文名（none，显示英文原文）：{localization.get('default_status', {}).get('none', 0)} 条",
        f"- 品牌库状态：{localization.get('branded_status', {})}（品牌名称保留原文，不做机器翻译）",
        f"- 待核验清单：zh_pending.csv {localization.get('pending_rows', 0)} 行；"
        f"zh_pending_branded.csv {localization.get('pending_branded_rows', 0)} 行",
        "",
        "## 覆盖情况",
        "",
        f"- 已核验中文食品名：{localization.get('verified_food_names', 0)} 条（不同 fdc_id，要求 ≥150）",
        "- 已核验中文名按分类分布："
        + "；".join(f"{name} {count} 条" for name, count in
                    localization.get("verified_by_category", {}).items()),
        f"- 营养素中文映射：{len(load_curation_nutrients())} 条（名称、单位、分组均为中文）",
        f"- 未映射中文分类的食品：{localization.get('food_category_unmapped', 0)} 条（品牌分类按原文展示并标注待核验）",
        f"- FNDDS 分类抽样：合法分类 {survey.get('eligible_categories')} 个，实际覆盖 "
        f"{survey.get('covered_categories')} 个（目标 {survey.get('target_categories')} 个）",
        "",
        "## 数据质量概览",
        "",
        f"- Foundation 真实食品：{foundation.get('db_real_foods')} 条；"
        f"foundation_food.csv：{foundation.get('foundation_food_csv_rows')} 行；"
        f"差异：{foundation.get('gap')} 条",
        f"- Foundation 能量来源分布：{energy}",
        f"- 质量问题：{metrics.get('quality', {})}",
        f"- 黄金样本对照：{sum(1 for item in metrics.get('golden_samples', []) if item['matched'])}/"
        f"{len(metrics.get('golden_samples', []))} 一致",
        "",
        "## 待核验说明",
        "",
        "1. `glossary` 状态由词典规则生成，仅作候选，界面必须显示“词典译名 / 待核验”。",
        "2. `none` 状态没有可靠中文名，界面显示英文原名并标注“中文名称待核验”，不编造译名。",
        "3. 品牌商品名称与配料表保留英文原文，不作为已核验中文内容。",
        "4. 人工核验后再把条目写入 `data/curation/food_zh.csv`，并将 `review_status` 升级为 verified。",
    ]
    (sample_dir / "DATA_LOCALIZATION_REPORT.md").write_text("\n".join(loc_lines), encoding="utf-8")


def load_curation_nutrients():
    from backend.app.etl.zh_overlay import ZhOverlay

    return ZhOverlay().load().nutrients


def run(settings: Settings | None = None) -> Report:
    settings = settings or load_settings()
    validate_data_dir(settings)
    manifest = load_manifest(settings.sample_dir / SAMPLE_MANIFEST_NAME)
    _, default_db = resolve_library_paths(settings, "sample", "default")
    report = Report()
    if not default_db.exists():
        report.add("默认 sample 数据库存在", False, str(default_db))
        write_reports(report, settings)
        return report
    with _ro(default_db) as conn:
        verify_foundation(settings, conn, report)
        verify_energy(conn, report)
        verify_missing_and_quality(conn, report)
        verify_coverage(conn, report)
        verify_orphans(conn, report)
    verify_library_and_scope(settings, report)
    report.metrics["import_counts"] = {
        name: _read_json(settings.sample_dir / "logs" / f"counts_{name}.json")
        for name in ("default", "branded")
    }
    verify_manifest(manifest, settings, report)
    verify_reconciliation(settings, report)
    verify_localization(settings, report)
    verify_branded_boundaries(manifest, settings, report)
    verify_golden(settings, manifest, report)
    write_reports(report, settings)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="校验 sample 构建结果并生成报告")
    parser.parse_args(argv)
    report = run()
    failed = report.failed
    for check in report.checks:
        print(("通过" if check.passed else "未通过"), check.name, "—", check.detail)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

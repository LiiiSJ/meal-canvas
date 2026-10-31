"""全库营养数据完整性扫描器。

对默认库与品牌库的每条食品 × nutrient 元数据表中的全部营养素做覆盖检查：
- 统计：食品总数、有/无营养记录的食品数、部分缺失数、每种营养素缺失数、真实 0 值数量。
- 明细 CSV：每行 = 一个具体食品 × 一个缺失营养素（无行 / amount 为 NULL 分别标注）。

用法（Windows，项目根目录）：
    .\\.venv\\Scripts\\python.exe scripts\\nutrient_completeness_scan.py --stats-only
    .\\.venv\\Scripts\\python.exe scripts\\nutrient_completeness_scan.py \
        --out-md data/reports/NUTRIENT_COMPLETENESS_BEFORE.md \
        --out-csv-default data/reports/NUTRIENT_MISSING_INVENTORY.csv \
        --out-csv-branded data/reports/NUTRIENT_MISSING_INVENTORY_BRANDED.csv

说明：
- 缺失定义：food_nutrient 中无该 (fdc_id, nutrient_id) 行，或行存在但 amount IS NULL。
- 真实 0 值（amount = 0）不算缺失，单独统计。
- 能量以 nutrient_id=1008 为准（ETL 已按 1008→2048→2047 取单值，origin_nutrient_id 留痕）。
- 明细 CSV 默认库与品牌库分文件输出（品牌库约数千万行，单文件过大）。
- 品牌库扫描分批进行（默认每批 2 万条食品），每批打印进度；中断后可用
  --start-fdc-id 从断点继续（需自行拼接或重跑该库明细）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas.sqlite"
BRANDED_DB = PROJECT_ROOT / "data" / "build" / "meal_canvas_branded.sqlite"

CHUNK_SIZE = 20_000


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_nutrients(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM nutrient ORDER BY rank").fetchall()


def aggregate_stats(db_path: Path, label: str) -> dict:
    """快速聚合统计（不输出明细）。"""
    conn = connect_ro(db_path)
    nutrients = load_nutrients(conn)
    (total_foods,) = conn.execute("SELECT COUNT(*) FROM food").fetchone()
    (foods_with_row,) = conn.execute("SELECT COUNT(DISTINCT fdc_id) FROM food_nutrient").fetchone()
    (foods_with_value,) = conn.execute(
        "SELECT COUNT(DISTINCT fdc_id) FROM food_nutrient WHERE amount IS NOT NULL"
    ).fetchone()

    per_nutrient: dict[int, dict] = {}
    for row in conn.execute(
        """
        SELECT nutrient_id,
               COUNT(*) AS rows_total,
               SUM(CASE WHEN amount IS NOT NULL THEN 1 ELSE 0 END) AS foods_with_value,
               SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS rows_null,
               SUM(CASE WHEN amount = 0 THEN 1 ELSE 0 END) AS rows_zero
        FROM food_nutrient GROUP BY nutrient_id
        """
    ):
        per_nutrient[int(row["nutrient_id"])] = {
            "rows_total": int(row["rows_total"]),
            "foods_with_value": int(row["foods_with_value"]),
            "rows_null": int(row["rows_null"]),
            "rows_zero": int(row["rows_zero"]),
        }

    # 完整度分布：每个食品拥有的有效值数量
    dist: dict[int, int] = {}
    for row in conn.execute(
        """
        SELECT cnt, COUNT(*) AS foods FROM (
            SELECT fdc_id, COUNT(*) AS cnt FROM food_nutrient
            WHERE amount IS NOT NULL GROUP BY fdc_id
        ) GROUP BY cnt
        """
    ):
        dist[int(row["cnt"])] = int(row["foods"])

    n_nutrients = len(nutrients)
    foods_zero_value = total_foods - foods_with_value
    foods_full = dist.get(n_nutrients, 0)
    foods_partial = foods_with_value - foods_full

    nutrient_rows = []
    total_missing_cells = 0
    for n in nutrients:
        nid = int(n["id"])
        st = per_nutrient.get(nid, {"rows_total": 0, "foods_with_value": 0, "rows_null": 0, "rows_zero": 0})
        missing = total_foods - st["foods_with_value"]
        total_missing_cells += missing
        nutrient_rows.append({
            "nutrient_id": nid,
            "nbr": n["nbr"],
            "name_en": n["name_en"],
            "name_zh": n["name_zh"],
            "unit_name": n["unit_name"],
            "is_core": int(n["is_core"]),
            "foods_with_value": st["foods_with_value"],
            "rows_null": st["rows_null"],
            "rows_zero": st["rows_zero"],
            "missing_foods": missing,
            "coverage_pct": round(100.0 * st["foods_with_value"] / total_foods, 2) if total_foods else 0.0,
        })

    # 默认库按 data_type 分解核心营养素覆盖
    by_type: dict[str, dict] = {}
    try:
        for row in conn.execute(
            """
            SELECT f.data_type,
                   COUNT(*) AS foods,
                   SUM(CASE WHEN fn.fdc_id IS NOT NULL THEN 1 ELSE 0 END) AS with_rows
            FROM food f LEFT JOIN (
                SELECT DISTINCT fdc_id FROM food_nutrient WHERE amount IS NOT NULL
            ) fn ON fn.fdc_id = f.fdc_id
            GROUP BY f.data_type
            """
        ):
            by_type[str(row["data_type"])] = {"foods": int(row["foods"]), "with_value": int(row["with_rows"])}
    except sqlite3.Error:
        pass

    # 能量 origin 分布（核验 1008→2048→2047 单值规则留痕）
    energy_origin: dict[str, int] = {}
    try:
        for row in conn.execute(
            "SELECT origin_nutrient_id, COUNT(*) AS c FROM food_nutrient "
            "WHERE nutrient_id = 1008 GROUP BY origin_nutrient_id"
        ):
            energy_origin[str(row["origin_nutrient_id"])] = int(row["c"])
    except sqlite3.Error:
        pass

    conn.close()
    return {
        "label": label,
        "db_path": str(db_path),
        "total_foods": total_foods,
        "nutrient_slots": n_nutrients,
        "foods_with_value": foods_with_value,
        "foods_with_row": foods_with_row,
        "foods_zero_value": foods_zero_value,
        "foods_full": foods_full,
        "foods_partial": foods_partial,
        "total_cells": total_foods * n_nutrients,
        "total_missing_cells": total_missing_cells,
        "coverage_pct": round(100.0 * (total_foods * n_nutrients - total_missing_cells) / (total_foods * n_nutrients), 4) if total_foods else 0.0,
        "per_nutrient": nutrient_rows,
        "by_data_type": by_type,
        "energy_origin": energy_origin,
        "value_count_dist": {str(k): dist[k] for k in sorted(dist)},
    }


def iter_food_chunks(conn: sqlite3.Connection, start_fdc_id: int, chunk: int) -> Iterator[list[sqlite3.Row]]:
    last = start_fdc_id
    while True:
        rows = conn.execute(
            "SELECT fdc_id, data_type, description_en FROM food WHERE fdc_id > ? ORDER BY fdc_id LIMIT ?",
            (last, chunk),
        ).fetchall()
        if not rows:
            return
        yield rows
        last = int(rows[-1]["fdc_id"])


def write_missing_inventory(
    db_path: Path,
    label: str,
    out_csv: Path,
    start_fdc_id: int = 0,
    chunk: int = CHUNK_SIZE,
) -> dict:
    """流式输出明细 CSV：每行一个 (食品 × 缺失营养素)。"""
    conn = connect_ro(db_path)
    nutrients = load_nutrients(conn)
    n_ids = [int(n["id"]) for n in nutrients]
    n_meta = {int(n["id"]): n for n in nutrients}

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    foods_done = 0
    t0 = time.time()
    mode = "ab" if start_fdc_id > 0 and out_csv.exists() else "wb"
    with open(out_csv, mode + "", buffering=1024 * 1024) as raw:
        import io
        text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        writer = csv.writer(text, lineterminator="\n")
        if mode == "wb":
            writer.writerow([
                "fdc_id", "library_scope", "data_type", "description_en",
                "nutrient_id", "nutrient_name_en", "nutrient_name_zh", "unit_name",
                "missing_kind", "raw_amount", "reason",
            ])
        for foods in iter_food_chunks(conn, start_fdc_id, chunk):
            lo = int(foods[0]["fdc_id"])
            hi = int(foods[-1]["fdc_id"])
            present: dict[int, set[int]] = {}
            null_rows: dict[int, dict[int, float | None]] = {}
            for row in conn.execute(
                "SELECT fdc_id, nutrient_id, amount, raw_amount FROM food_nutrient "
                "WHERE fdc_id >= ? AND fdc_id <= ?",
                (lo, hi),
            ):
                fid = int(row["fdc_id"])
                nid = int(row["nutrient_id"])
                if row["amount"] is None:
                    null_rows.setdefault(fid, {})[nid] = row["raw_amount"]
                else:
                    present.setdefault(fid, set()).add(nid)
            for f in foods:
                fid = int(f["fdc_id"])
                have = present.get(fid, set())
                nulls = null_rows.get(fid, {})
                for nid in n_ids:
                    if nid in have:
                        continue
                    n = n_meta[nid]
                    if nid in nulls:
                        kind = "null_amount"
                        reason = "源记录存在但数值不可用（amount 为空，原始值保留于 raw_amount）"
                        raw_amount = nulls[nid]
                    else:
                        kind = "no_row"
                        reason = "源数据无该营养素记录"
                        raw_amount = None
                    writer.writerow([
                        fid, label, f["data_type"], f["description_en"],
                        nid, n["name_en"], n["name_zh"], n["unit_name"],
                        kind, raw_amount, reason,
                    ])
                    written += 1
            foods_done += len(foods)
            text.flush()
            print(
                f"[{label}] foods {foods_done}（最后 fdc_id={hi}），已写缺失行 {written}，"
                f"耗时 {time.time() - t0:.1f}s",
                flush=True,
            )
        text.flush()
    conn.close()
    return {"library": label, "csv": str(out_csv), "rows_written": written, "foods_scanned": foods_done}


def render_report(stats_list: list[dict], out_md: Path, csv_paths: dict[str, str]) -> None:
    lines: list[str] = []
    lines.append("# 全库营养数据完整性扫描报告（补全前基线）")
    lines.append("")
    lines.append("- 扫描口径：每个食品 × `nutrient` 元数据表中全部营养素（37 项，含能量 kJ、维生素A(IU)、氮、灰分、水分等）。")
    lines.append("- 缺失定义：`food_nutrient` 中无该行，或行存在但 `amount IS NULL`（原始值仍在 `raw_amount` 中保留）。")
    lines.append("- 真实 0 值（amount = 0）不计入缺失，单独统计。")
    lines.append("- 能量 kcal 以 nutrient_id=1008 为准（ETL 已按 1008→2048→2047 取单值）。")
    lines.append("")
    for st in stats_list:
        lines.append(f"## {st['label']}（`{st['db_path']}`）")
        lines.append("")
        lines.append(f"- 食品总数：{st['total_foods']:,}")
        lines.append(f"- 检查的营养素种数：{st['nutrient_slots']}")
        lines.append(f"- 理论字段总数（食品×营养素）：{st['total_cells']:,}")
        lines.append(f"- 已有 ≥1 个有效营养值的食品：{st['foods_with_value']:,}")
        lines.append(f"- 完全没有任何有效营养记录的食品：{st['foods_zero_value']:,}")
        lines.append(f"- 37 项全部有值的食品：{st['foods_full']:,}")
        lines.append(f"- 部分缺失的食品（1–36 项有值）：{st['foods_partial']:,}")
        lines.append(f"- 缺失字段总数：{st['total_missing_cells']:,}")
        lines.append(f"- 字段级覆盖率：{st['coverage_pct']}%")
        if st["by_data_type"]:
            lines.append("")
            lines.append("按数据集：")
            lines.append("")
            lines.append("| data_type | 食品数 | 有有效营养值的食品 |")
            lines.append("| --- | ---: | ---: |")
            for dt, d in sorted(st["by_data_type"].items()):
                lines.append(f"| {dt} | {d['foods']:,} | {d['with_value']:,} |")
        if st["energy_origin"]:
            lines.append("")
            lines.append("能量（1008）origin_nutrient_id 分布：" +
                         "；".join(f"{k}: {v:,}" for k, v in sorted(st["energy_origin"].items())))
        lines.append("")
        lines.append("| nutrient_id | 营养素 | 单位 | 核心 | 有值食品数 | 缺失食品数 | 覆盖率 | 空值行 | 真实 0 值行 |")
        lines.append("| ---: | --- | --- | :-: | ---: | ---: | ---: | ---: | ---: |")
        for n in st["per_nutrient"]:
            lines.append(
                f"| {n['nutrient_id']} | {n['name_zh']}（{n['name_en']}） | {n['unit_name']} | "
                f"{'是' if n['is_core'] else '否'} | {n['foods_with_value']:,} | {n['missing_foods']:,} | "
                f"{n['coverage_pct']}% | {n['rows_null']:,} | {n['rows_zero']:,} |"
            )
        lines.append("")
    lines.append("## 明细清单文件")
    lines.append("")
    for label, p in csv_paths.items():
        lines.append(f"- {label}：`{p}`（每行 = 一个食品 × 一个缺失营养素，含 missing_kind 与原因）")
    lines.append("")
    lines.append("> 本报告由 `scripts/nutrient_completeness_scan.py` 实测生成，数字来自数据库扫描，非估计。")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="全库营养完整性扫描")
    ap.add_argument("--default-db", default=str(DEFAULT_DB))
    ap.add_argument("--branded-db", default=str(BRANDED_DB))
    ap.add_argument("--stats-only", action="store_true", help="只聚合统计并打印 JSON，不写明细 CSV")
    ap.add_argument("--library", choices=["default", "branded", "both"], default="both")
    ap.add_argument("--out-md", default=None, help="输出 Markdown 报告路径")
    ap.add_argument("--out-csv-default", default=None)
    ap.add_argument("--out-csv-branded", default=None)
    ap.add_argument("--start-fdc-id", type=int, default=0, help="仅品牌库：从该 fdc_id 之后续跑明细")
    ap.add_argument("--stats-json", default=None, help="把统计结果另存为 JSON")
    ap.add_argument("--chunk", type=int, default=CHUNK_SIZE)
    args = ap.parse_args()

    stats_list: list[dict] = []
    csv_paths: dict[str, str] = {}

    targets = []
    if args.library in ("default", "both"):
        targets.append((Path(args.default_db), "default"))
    if args.library in ("branded", "both"):
        targets.append((Path(args.branded_db), "branded"))

    for db_path, label in targets:
        if not db_path.is_file():
            print(f"错误：数据库不存在：{db_path}", file=sys.stderr)
            sys.exit(1)
        print(f"===== 聚合统计 {label}: {db_path} =====", flush=True)
        st = aggregate_stats(db_path, label)
        stats_list.append(st)
        print(json.dumps({k: v for k, v in st.items() if k not in ("per_nutrient", "value_count_dist")},
                         ensure_ascii=False, indent=2), flush=True)

        if not args.stats_only:
            out_csv = args.out_csv_default if label == "default" else args.out_csv_branded
            if out_csv:
                start = args.start_fdc_id if label == "branded" else 0
                print(f"===== 明细扫描 {label} → {out_csv} =====", flush=True)
                res = write_missing_inventory(db_path, label, Path(out_csv), start, args.chunk)
                csv_paths[label] = res["csv"]
                print(f"[{label}] 明细完成：{res}", flush=True)

    if args.stats_json:
        Path(args.stats_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.stats_json).write_text(json.dumps(stats_list, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"统计 JSON 已写入 {args.stats_json}")

    if args.out_md and stats_list:
        render_report(stats_list, Path(args.out_md), csv_paths)
        print(f"Markdown 报告已写入 {args.out_md}")


if __name__ == "__main__":
    main()

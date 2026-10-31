r"""全库批量外部营养补全 runner：分批处理、断点续跑、进度落盘。

工作清单：缺 ≥1 项项目营养素（共 37 项）且有 GTIN 的食品，按"缺核心营养最多"优先。
品牌库默认只用 OFF GTIN 精确查询（关闭名称搜索，避免 search 端点限流）；
默认库在配置 MEAL_CANVAS_FDC_API_KEY 后可走 USDA FDC。

用法（Windows）：
    .\.venv\Scripts\python.exe scripts\enrichment_batch.py --library branded --max-foods 2000
    .\.venv\Scripts\python.exe scripts\enrichment_batch.py --library branded   # 断点续跑

进度实时写入 --progress-json（默认 data/build/enrichment_batch_progress_<library>.json），
中断后用同一命令继续。补全数据只写 data/build/meal_canvas_enrichment.sqlite，不改 USDA 库。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.enrichment.config import DEFAULT_ENRICH_DB, EnrichSettings
from backend.app.enrichment.identity import LocalFood
from backend.app.enrichment.mapper import ALL_NUTRIENT_KEYS, NUTRIENT_KEY_BY_ID
from backend.app.enrichment.service import EnrichmentService
from backend.app.enrichment.storage import VERIFIED

DB_BY_LIBRARY = {
    "default": PROJECT_ROOT / "data" / "build" / "meal_canvas.sqlite",
    "branded": PROJECT_ROOT / "data" / "build" / "meal_canvas_branded.sqlite",
}

# 核心 7 项对应的 FDC 营养 ID（能量并集 1008/2047/2048 视为一项）
CORE_IDS = (1008, 2047, 2048, 1003, 1004, 1005, 1079, 2000, 1093)
ALL_IDS = tuple(NUTRIENT_KEY_BY_ID.keys())

BATCH_SQL = f"""
SELECT * FROM (
    SELECT f.fdc_id, f.description_en, f.data_type, f.gtin_upc,
        (SELECT COUNT(DISTINCT fn.nutrient_id) FROM food_nutrient fn
            WHERE fn.fdc_id = f.fdc_id AND fn.amount IS NOT NULL
            AND fn.nutrient_id IN ({",".join(str(i) for i in CORE_IDS)})) AS core_present,
        (SELECT COUNT(DISTINCT fn2.nutrient_id) FROM food_nutrient fn2
            WHERE fn2.fdc_id = f.fdc_id AND fn2.amount IS NOT NULL
            AND fn2.nutrient_id IN ({",".join(str(i) for i in ALL_IDS)})) AS total_present
    FROM food f
    WHERE f.gtin_upc IS NOT NULL AND f.gtin_upc <> ''
)
WHERE total_present < {len(ALL_IDS)}
  AND (core_present, fdc_id) > (?, ?)
ORDER BY core_present ASC, fdc_id ASC
LIMIT ?
"""


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def load_profile(conn: sqlite3.Connection, fdc_id: int) -> dict[str, float | None]:
    profile: dict[str, float | None] = {key: None for key in ALL_NUTRIENT_KEYS}
    for nutrient_id, amount in conn.execute(
        "SELECT nutrient_id, amount FROM food_nutrient WHERE fdc_id = ?", (fdc_id,)
    ):
        key = NUTRIENT_KEY_BY_ID.get(int(nutrient_id))
        if key is not None:
            profile[key] = amount
    return profile


def save_progress(path: Path, progress: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Meal Canvas 全库批量营养补全")
    parser.add_argument("--library", choices=sorted(DB_BY_LIBRARY), default="branded")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--max-foods", type=int, default=0, help="0 表示不限制")
    parser.add_argument("--off-interval", type=float, default=1.2, help="OFF 请求最小间隔秒数")
    parser.add_argument("--name-search", action="store_true", help="允许 OFF 名称搜索（默认关闭）")
    parser.add_argument("--progress-json", type=Path, default=None)
    args = parser.parse_args()

    db_path = DB_BY_LIBRARY[args.library]
    if not db_path.is_file():
        print(f"错误：数据库不存在：{db_path}。请先完成正式数据构建。", file=sys.stderr)
        return 2

    progress_path = args.progress_json or (
        PROJECT_ROOT / "data" / "build" / f"enrichment_batch_progress_{args.library}.json"
    )
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    settings = EnrichSettings(
        enabled=True,
        db_path=Path(os.environ.get("MEAL_CANVAS_ENRICH_DB_PATH", str(DEFAULT_ENRICH_DB))),
        fdc_api_key=(os.environ.get("MEAL_CANVAS_FDC_API_KEY", "").strip() or None),
        fdc_enabled=True,
        off_enabled=True,
        timeout_seconds=8.0,
        max_retries=2,
        off_min_interval=max(1.0, args.off_interval),
        fdc_min_interval=0.5,
        negative_ttl_minutes=24 * 60,
        error_ttl_minutes=10,
        max_candidates=5,
        off_name_search=bool(args.name_search),
    )
    service = EnrichmentService(settings)
    if not service.enabled:
        print("错误：没有可用的外部来源（OFF 未启用或配置缺失）。", file=sys.stderr)
        return 2

    # 断点恢复
    cursor_core, cursor_fdc = -1, 0
    counters: dict[str, int] = {}
    scanned = 0
    if progress_path.is_file():
        try:
            old = json.loads(progress_path.read_text(encoding="utf-8"))
            if old.get("library") == args.library:
                cursor_core = int(old["cursor"]["core_present"])
                cursor_fdc = int(old["cursor"]["last_fdc_id"])
                counters = dict(old.get("counters", {}))
                scanned = int(old.get("scanned", 0))
                print(f"断点续跑：从 (core_present={cursor_core}, fdc_id={cursor_fdc}) 继续，"
                      f"此前已扫描 {scanned} 条。")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"警告：进度文件损坏（{exc}），从头开始。", file=sys.stderr)

    def verified_total() -> int:
        with service.storage.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM enrich_value WHERE status = ?", (VERIFIED,)
            ).fetchone()
        return int(row[0])

    verified_before = verified_total()
    started = time.monotonic()
    consecutive_errors = 0
    run_scanned = 0

    print(f"[{now_iso()}] 开始批量补全：库={args.library}，批大小={args.batch_size}，"
          f"OFF 间隔={settings.off_min_interval}s，名称搜索={'开' if settings.off_name_search else '关'}，"
          f"FDC={'可用' if settings.fdc_available else '不可用（无 Key）'}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    completed_all = False
    interrupted = False
    try:
        stop = False
        while not stop:
            rows = conn.execute(BATCH_SQL, (cursor_core, cursor_fdc, args.batch_size)).fetchall()
            if not rows:
                completed_all = True
                break
            for fdc_id, description_en, data_type, gtin_upc, core_present, _total in rows:
                profile = load_profile(conn, fdc_id)
                local = LocalFood(
                    fdc_id=int(fdc_id),
                    description_en=str(description_en),
                    data_type=str(data_type),
                    gtin_upc=str(gtin_upc) if gtin_upc else None,
                )
                try:
                    result = service.resolve(local, profile)
                except Exception as exc:  # noqa: BLE001 单条失败不中断整批
                    counters["error"] = counters.get("error", 0) + 1
                    print(f"[{now_iso()}] fdc={fdc_id} 解析异常：{exc}", file=sys.stderr)
                else:
                    counters[result.outcome] = counters.get(result.outcome, 0) + 1
                    consecutive_errors = 0 if result.outcome != "error" else consecutive_errors + 1
                    if result.attempted:
                        print(f"[{now_iso()}] fdc={fdc_id} 核心已有{core_present}/9"
                              f" → {result.outcome}（{result.message or ''}）")
                scanned += 1
                run_scanned += 1
                cursor_core, cursor_fdc = int(core_present), int(fdc_id)

                if consecutive_errors >= 20:
                    print(f"[{now_iso()}] 连续 {consecutive_errors} 次外部服务失败，停止。"
                          "稍后可用同一命令断点续跑。", file=sys.stderr)
                    stop = True
                    break
                if consecutive_errors in (5, 10):
                    delay = 60 if consecutive_errors == 5 else 300
                    print(f"[{now_iso()}] 连续 {consecutive_errors} 次失败，退避 {delay}s")
                    time.sleep(delay)
                if args.max_foods and run_scanned >= args.max_foods:
                    stop = True
                    break
            save_progress(progress_path, {
                "library": args.library,
                "cursor": {"core_present": cursor_core, "last_fdc_id": cursor_fdc},
                "scanned": scanned,
                "counters": counters,
                "updated_at": now_iso(),
                "finished": False,
            })
    except KeyboardInterrupt:
        interrupted = True
        print(f"\n[{now_iso()}] 收到中断信号，保存进度后退出。")
    finally:
        conn.close()

    verified_after = verified_total()
    elapsed = time.monotonic() - started
    finished = completed_all and not interrupted
    save_progress(progress_path, {
        "library": args.library,
        "cursor": {"core_present": cursor_core, "last_fdc_id": cursor_fdc},
        "scanned": scanned,
        "counters": counters,
        "updated_at": now_iso(),
        "finished": finished,
    })

    print(f"[{now_iso()}] 本轮结束：扫描 {run_scanned} 条（累计 {scanned}），耗时 {elapsed:.0f}s")
    print(f"  结果分布：{json.dumps(counters, ensure_ascii=False, sort_keys=True)}")
    print(f"  补全库 verified 值总数：{verified_after}（本轮净增 {verified_after - verified_before}）")
    print(f"  进度文件：{progress_path}")
    if not finished:
        print("  本轮受 --max-foods / 中断 / 连续失败限制未跑完；同一命令再次执行即可续跑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

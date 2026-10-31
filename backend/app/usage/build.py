"""构建独立的食品用途库 `meal_canvas_usage.sqlite`。

用法（Windows 固定命令）：

    .\\.venv\\Scripts\\python.exe -m backend.app.usage.build --mode sample
    .\\.venv\\Scripts\\python.exe -m backend.app.usage.build --mode full --confirm-full

约束：

- 必须显式指定 `--mode`；`full` 还需 `--confirm-full`，且不得覆盖已存在的正式用途库。
- sample 只写 `data/build/sample/`，与正式库物理隔离。
- 只读取已构建的 `meal_canvas.sqlite` 与 `meal_canvas_branded.sqlite`，不修改任何 USDA 原始数据。
- 用途分类不等于 USDA `data_type`，也不等于中文映射状态 `zh_status`。
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.app.core.config import Settings, load_settings
from backend.app.usage import CLASSIFICATION_VERSION, USAGE_CLASSES
from backend.app.usage.taxonomy import UsageTaxonomy, UsageTaxonomyError, load_taxonomy

log = logging.getLogger("meal-canvas.usage")

USAGE_SCHEMA = """
CREATE TABLE food_usage (
    fdc_id                 INTEGER NOT NULL,
    library_scope          TEXT NOT NULL,      -- default / branded，与来源库隔离
    usage_class            TEXT NOT NULL,      -- basic_ingredient / processed_ingredient / prepared_dish / ready_to_eat / unknown
    rule_source            TEXT NOT NULL,      -- override / rule / category / default
    rule_id                TEXT,               -- 规则文件行号或类别键，便于追溯
    reason                 TEXT,               -- 中文判定说明
    classification_version TEXT NOT NULL,
    PRIMARY KEY (fdc_id, library_scope)
);
CREATE INDEX idx_food_usage_class ON food_usage(usage_class);
CREATE INDEX idx_food_usage_scope ON food_usage(library_scope, usage_class);
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@dataclass(frozen=True)
class BuildReport:
    mode: str
    output_path: Path
    total: int
    per_scope_class: dict[tuple[str, str], int]
    per_rule_source: dict[str, int]
    examples: dict[tuple[str, str], list[str]]


def usage_db_path(settings: Settings, mode: str) -> Path:
    """用途库输出路径：sample 落在 sample 目录，full 落在正式库目录。"""
    if mode == "sample":
        return settings.sample_dir / "meal_canvas_usage.sqlite"
    if mode == "full":
        return settings.formal_db.parent / "meal_canvas_usage.sqlite"
    raise ValueError(f"未知构建模式：{mode}。必须显式指定 --mode sample 或 --mode full。")


def source_dbs(settings: Settings, mode: str) -> list[tuple[str, Path]]:
    if mode == "sample":
        return [
            ("default", settings.sample_dir / "meal_canvas.sqlite"),
            ("branded", settings.sample_dir / "meal_canvas_branded.sqlite"),
        ]
    if mode == "full":
        return [("default", settings.formal_db), ("branded", settings.formal_branded_db)]
    raise ValueError(f"未知构建模式：{mode}。必须显式指定 --mode sample 或 --mode full。")


def build_usage_db(
    *,
    mode: str,
    settings: Settings,
    taxonomy: UsageTaxonomy,
    confirm_full: bool = False,
    force: bool = False,
) -> BuildReport:
    """按 mode 构建用途库并原子替换输出文件。"""
    if mode not in {"sample", "full"}:
        raise ValueError(f"未知构建模式：{mode}。必须显式指定 --mode sample 或 --mode full。")
    if mode == "full" and not confirm_full:
        raise ValueError("full 模式必须同时显式传入 --confirm-full，否则拒绝执行。")

    sources = source_dbs(settings, mode)
    missing = [str(path) for _, path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "待分类的数据库不存在：" + "；".join(missing)
            + "。请先运行 backend.app.etl.build 构建 sample 或正式库。"
        )

    output = usage_db_path(settings, mode)
    if mode == "full" and output.exists() and not force:
        raise FileExistsError(
            f"正式用途库已存在：{output}。为避免覆盖，full 模式默认拒绝写入；"
            "确认需要重建时请追加 --force。"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output.with_name(output.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    per_scope_class: Counter[tuple[str, str]] = Counter()
    per_rule_source: Counter[str] = Counter()
    examples: dict[tuple[str, str], list[str]] = {}
    total = 0

    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.executescript(USAGE_SCHEMA)
        batch: list[tuple] = []
        for scope, db_path in sources:
            source = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            source.row_factory = sqlite3.Row
            try:
                cursor = source.execute(
                    "SELECT fdc_id, data_type, description_en, category_source, category_code, "
                    "category_en FROM food ORDER BY fdc_id"
                )
                for row in cursor:
                    result = taxonomy.classify_food_row(row)
                    batch.append(
                        (
                            int(row["fdc_id"]),
                            scope,
                            result.usage_class,
                            result.rule_source,
                            result.rule_id,
                            result.reason,
                            taxonomy.version,
                        )
                    )
                    per_scope_class[(scope, result.usage_class)] += 1
                    per_rule_source[result.rule_source] += 1
                    bucket = examples.setdefault((scope, result.usage_class), [])
                    if len(bucket) < 5:
                        bucket.append(str(row["description_en"]))
                    total += 1
                    if len(batch) >= 500:
                        conn.executemany(
                            "INSERT INTO food_usage (fdc_id, library_scope, usage_class, rule_source, "
                            "rule_id, reason, classification_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT INTO food_usage (fdc_id, library_scope, usage_class, rule_source, "
                        "rule_id, reason, classification_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    batch.clear()
            finally:
                source.close()

        meta = {
            "classification_version": taxonomy.version,
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "total_rows": str(total),
            "default_db": str(sources[0][1]),
            "branded_db": str(sources[1][1]),
            "expected_classification_version": CLASSIFICATION_VERSION,
        }
        conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", list(meta.items()))
        conn.commit()

        _verify(conn, sources, expected_total=total)
    finally:
        conn.close()

    os.replace(tmp_path, output)
    return BuildReport(
        mode=mode,
        output_path=output,
        total=total,
        per_scope_class=dict(per_scope_class),
        per_rule_source=dict(per_rule_source),
        examples=examples,
    )


def _verify(
    conn: sqlite3.Connection,
    sources: list[tuple[str, Path]],
    *,
    expected_total: int,
) -> None:
    """重建前的完整性校验：任何一项不通过都必须失败，而不是带着可疑数据替换输出。"""
    check = conn.execute("PRAGMA integrity_check").fetchone()
    if not check or check[0] != "ok":
        raise RuntimeError(f"用途库完整性检查失败：{check[0] if check else '无结果'}")

    row_count = conn.execute("SELECT COUNT(*) FROM food_usage").fetchone()[0]
    if int(row_count) != expected_total:
        raise RuntimeError(
            f"用途库行数不一致：写入 {expected_total}，实际 {row_count}。"
        )

    placeholders = ",".join("?" * len(USAGE_CLASSES))
    bad_class = conn.execute(
        f"SELECT COUNT(*) FROM food_usage WHERE usage_class NOT IN ({placeholders})",
        list(USAGE_CLASSES),
    ).fetchone()[0]
    if int(bad_class) > 0:
        raise RuntimeError(f"用途库出现非法分类值 {bad_class} 行。")

    for scope, db_path in sources:
        source = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            food_ids = {int(r[0]) for r in source.execute("SELECT fdc_id FROM food")}
        finally:
            source.close()
        usage_ids = {
            int(r[0])
            for r in conn.execute("SELECT fdc_id FROM food_usage WHERE library_scope = ?", (scope,))
        }
        extra = usage_ids - food_ids
        missing = food_ids - usage_ids
        if extra or missing:
            raise RuntimeError(
                f"{scope} 库用途记录与食品记录不匹配：多出 {len(extra)} 条，缺失 {len(missing)} 条。"
            )


def _print_report(report: BuildReport) -> None:
    print(f"用途库已生成：{report.output_path}")
    print(f"模式：{report.mode}，分类口径版本：{CLASSIFICATION_VERSION}，总记录：{report.total}")
    print("按库类型与用途分类统计：")
    for scope in ("default", "branded"):
        for usage_class in USAGE_CLASSES:
            count = report.per_scope_class.get((scope, usage_class), 0)
            print(f"  {scope:8s} {usage_class:22s} {count:6d}")
    print("按判定来源统计：")
    for source, count in sorted(report.per_rule_source.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {source:10s} {count:6d}")
    print("各类样例（最多 5 条）：")
    for scope in ("default", "branded"):
        for usage_class in USAGE_CLASSES:
            samples = report.examples.get((scope, usage_class), [])
            if samples:
                print(f"  {scope}/{usage_class}: " + " | ".join(samples))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="构建独立的食品用途库（basic/processed/prepared/ready/unknown）。"
    )
    parser.add_argument("--mode", required=True, choices=("sample", "full"), help="必须显式指定 sample 或 full")
    parser.add_argument(
        "--confirm-full",
        action="store_true",
        help="full 模式必需的二次确认（防止误写正式库）",
    )
    parser.add_argument("--force", action="store_true", help="full 模式允许覆盖已存在的正式用途库")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_settings()
    try:
        taxonomy = load_taxonomy()
        report = build_usage_db(
            mode=args.mode,
            settings=settings,
            taxonomy=taxonomy,
            confirm_full=args.confirm_full,
            force=args.force,
        )
    except (UsageTaxonomyError, FileNotFoundError) as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

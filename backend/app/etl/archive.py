"""流式读取 ZIP 内 CSV 的工具。原始 ZIP 只读，不解压。"""
from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class ArchiveError(RuntimeError):
    """ZIP 结构不符合预期时抛出，消息为中文。"""


def find_entry(zf: zipfile.ZipFile, filename: str) -> str:
    for name in zf.namelist():
        if name.rsplit("/", 1)[-1] == filename:
            return name
    raise ArchiveError(f"ZIP 内缺少文件：{filename}。")


@contextmanager
def open_csv(zip_path: Path, filename: str) -> Iterator[csv.DictReader]:
    """逐行读取 ZIP 内的 CSV，不一次性载入内存。"""
    with zipfile.ZipFile(zip_path) as zf:
        entry = find_entry(zf, filename)
        with zf.open(entry) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            try:
                yield csv.DictReader(text)
            finally:
                text.close()


def read_rows(zip_path: Path, filename: str, limit: int | None = None) -> list[dict[str, str]]:
    """读取小型 CSV（分类、营养字典、份量单位）到内存。"""
    rows: list[dict[str, str]] = []
    with open_csv(zip_path, filename) as reader:
        for row in reader:
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    return rows

# -*- coding: utf-8 -*-
"""
统计 tujia_calendar_data.json 与 tujia_calendar_data_tags.json 的 unit_id 覆盖情况。

完整房源 = 两文件**均存在**的 unit_id（交集）。仅在一侧存在的 id 数据不完整，导入脚本可跳过。

用法:
  python scripts/listing_source_intersection.py
  python scripts/listing_source_intersection.py --write-ids data/hive_import/complete_unit_ids.txt
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ijson  # type: ignore

from scripts.listing_sources import load_tags_unit_id_set


def calendar_id_set(calendar_json: Path) -> set:
    ids: set = set()
    with open(calendar_json, "rb") as f:
        for house in ijson.items(f, "houses.item", use_float=True):
            uid = house.get("unit_id")
            if uid is None:
                continue
            u = str(uid).strip()
            if u:
                ids.add(u)
    return ids


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="两源 JSON unit_id 交集统计")
    p.add_argument(
        "--calendar",
        type=Path,
        default=root / "tujia_calendar_data.json",
    )
    p.add_argument(
        "--tags",
        type=Path,
        default=root / "tujia_calendar_data_tags.json",
    )
    p.add_argument(
        "--write-ids",
        type=Path,
        default=None,
        help="将交集 unit_id 逐行写入该文件",
    )
    args = p.parse_args()

    if not args.calendar.is_file() or not args.tags.is_file():
        print("请确认日历与 tags 两个 JSON 路径存在。")
        sys.exit(1)

    print("加载 tags 的 unit_id 集合（流式）…")
    tags_set = load_tags_unit_id_set(args.tags)
    print("扫描日历 JSON unit_id 集合（流式）…")
    cal_set = calendar_id_set(args.calendar)

    inter = cal_set & tags_set
    print("=" * 60)
    print(f"日历唯一 unit_id 数:     {len(cal_set)}")
    print(f"tags 唯一 unit_id 数:    {len(tags_set)}")
    print(f"交集（两源均存在）:    {len(inter)}")
    print(f"仅日历有（缺详情）:    {len(cal_set - tags_set)}")
    print(f"仅 tags 有（缺日历）:  {len(tags_set - cal_set)}")
    print("=" * 60)
    print("论文/答辩可写：全量分析以交集为「完整样本」，单侧仅存在 id 不纳入严谨对比。")

    if args.write_ids:
        args.write_ids.parent.mkdir(parents=True, exist_ok=True)
        def _sort_key(x: str):
            try:
                return (0, int(x))
            except ValueError:
                return (1, x)

        with open(args.write_ids, "w", encoding="utf-8") as out:
            for uid in sorted(inter, key=_sort_key):
                out.write(uid + "\n")
        print(f"已写入 {len(inter)} 条 id → {args.write_ids}")


if __name__ == "__main__":
    main()

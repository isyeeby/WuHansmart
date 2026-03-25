# -*- coding: utf-8 -*-
"""
从 tujia_calendar_data.json 流式读取房源经纬度，回填到 MySQL listings 表。

大文件内嵌 price_calendar，不宜 json.load 整文件；使用 ijson 按条解析 houses[*]。

用法:
  python scripts/backfill_listing_coordinates.py
  python scripts/backfill_listing_coordinates.py --path D:/path/to/tujia_calendar_data.json
  python scripts/backfill_listing_coordinates.py --dry-run
  python scripts/backfill_listing_coordinates.py --force   # 覆盖已有非空坐标
  python scripts/backfill_listing_coordinates.py --both-sources-only
      # 仅当 unit_id 在 tujia_calendar_data_tags.json 的 tags 中也存在时才回填（完整样本）
"""
from __future__ import annotations

import argparse
from typing import Optional, Set
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from pathlib import Path

import ijson  # type: ignore

from app.db.database import Listing, SessionLocal
from scripts.listing_sources import load_tags_unit_id_set


def _num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if abs(x) < 1e-9:
        return None
    return x


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 listings 经纬度（来自日历 JSON）")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tujia_calendar_data.json",
        help="tujia_calendar_data.json 路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使库中已有坐标也按 JSON 覆盖",
    )
    parser.add_argument("--batch-commit", type=int, default=200, help="每批提交条数")
    parser.add_argument(
        "--both-sources-only",
        action="store_true",
        help="仅处理日历与 tags 两文件均存在的 unit_id（推荐，与「完整房源」定义一致）",
    )
    parser.add_argument(
        "--tags-json",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tujia_calendar_data_tags.json",
        help="与 --both-sources-only 联用：tags 文件路径",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"文件不存在: {args.path}")
        sys.exit(1)

    tags_allow: Optional[Set[str]] = None
    if args.both_sources_only:
        if not args.tags_json.is_file():
            print(f"--both-sources-only 需要有效的 tags 文件: {args.tags_json}")
            sys.exit(1)
        print("加载 tags unit_id 集合（仅回填两源交集）…")
        tags_allow = load_tags_unit_id_set(args.tags_json)
        print(f"  tags 中 unit_id 数: {len(tags_allow)}")

    updated = 0
    skipped_no_row = 0
    skipped_has_coords = 0
    skipped_no_coords_in_json = 0
    skipped_not_in_tags = 0
    seen = 0

    db = SessionLocal()
    pending = 0
    try:
        with open(args.path, "rb") as f:
            for house in ijson.items(f, "houses.item", use_float=True):
                seen += 1
                uid = house.get("unit_id")
                if uid is None:
                    skipped_no_coords_in_json += 1
                    continue
                unit_id = str(uid).strip()
                lat = _num(house.get("latitude"))
                lon = _num(house.get("longitude"))
                if lat is None or lon is None:
                    skipped_no_coords_in_json += 1
                    continue

                if tags_allow is not None and unit_id not in tags_allow:
                    skipped_not_in_tags += 1
                    continue

                row = db.query(Listing).filter(Listing.unit_id == unit_id).one_or_none()
                if not row:
                    skipped_no_row += 1
                    continue

                if not args.force:
                    if row.latitude is not None and row.longitude is not None:
                        skipped_has_coords += 1
                        continue

                if args.dry_run:
                    updated += 1
                    continue

                row.latitude = Decimal(str(round(lat, 8)))
                row.longitude = Decimal(str(round(lon, 8)))
                updated += 1
                pending += 1
                if pending >= args.batch_commit:
                    db.commit()
                    pending = 0
                    print(f"  已提交… 累计更新 {updated}")

        if not args.dry_run and pending:
            db.commit()
    finally:
        db.close()

    print("=" * 60)
    print(f"JSON 房源条数(流式): {seen}")
    print(f"将更新条数{'(预览)' if args.dry_run else ''}: {updated}")
    print(f"库中无对应 unit_id: {skipped_no_row}")
    print(f"跳过(已有坐标且未 --force): {skipped_has_coords}")
    print(f"跳过(JSON 无 unit_id 或无有效经纬度): {skipped_no_coords_in_json}")
    if tags_allow is not None:
        print(f"跳过(未在 tags 中，非完整样本): {skipped_not_in_tags}")
    if args.dry_run:
        print("(dry-run，未修改数据库)")
    print("=" * 60)


if __name__ == "__main__":
    main()

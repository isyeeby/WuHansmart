# -*- coding: utf-8 -*-
"""
将详情属性写入 MySQL listings（与日历字段对齐）
=============================================
数据源约定：
- **tujia_calendar_data.json**：流式读取，提供 unit_id 集合、价、经纬度、标题等（价日历体积大，禁止整文件 json.load）。
- **tujia_calendar_data_tags.json**：流式读取 `tags` 各条，提供户型摘要、位置模块等。

**仅处理两源交集**：`unit_id` 必须同时出现在日历与 tags 中，否则跳过（单侧数据不完整）。

若仍需使用历史合并文件 `listings_with_tags_and_calendar.json` 仅作价目补充，可传
`--legacy-price-json`（一般不必，日历已含 final_price）。
"""

import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ijson  # type: ignore

from app.db.database import Listing, SessionLocal, engine
from sqlalchemy import text

from scripts.listing_sources import build_calendar_maps


TAGS_PATH = Path(__file__).resolve().parent.parent / "tujia_calendar_data_tags.json"
CALENDAR_PATH = Path(__file__).resolve().parent.parent / "tujia_calendar_data.json"


def parse_house_summary(summary):
    """解析: 整套·3居3床6人·121㎡"""
    result = {}

    if not summary:
        return result

    parts = summary.split("·")
    if parts:
        result["house_type"] = parts[0].strip()

    if len(parts) >= 2:
        match = re.search(r"(\d+)居(\d+)床(\d+)-?(\d+)?人", parts[1])
        if match:
            result["bedroom_count"] = int(match.group(1))
            result["bed_count"] = int(match.group(2))
            if match.group(4):
                min_cap = int(match.group(3))
                max_cap = int(match.group(4))
                result["capacity"] = (min_cap + max_cap) // 2
            else:
                result["capacity"] = int(match.group(3))

    if len(parts) >= 3:
        area_match = re.search(r"(\d+)㎡", parts[2])
        if area_match:
            result["area"] = int(area_match.group(1))

    return result


def main():
    parser = argparse.ArgumentParser(description="合并日历+tags 导入 listings（仅交集）")
    parser.add_argument("--tags", type=Path, default=TAGS_PATH)
    parser.add_argument("--calendar", type=Path, default=CALENDAR_PATH)
    parser.add_argument(
        "--legacy-price-json",
        type=Path,
        default=None,
        help="可选：额外价目/字段 JSON（houses 数组），按 unit_id 合并进映射",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("更新数据库 - 日历+tags 交集房源")
    print("=" * 60)

    print("\n1. 检查并添加新列...")
    new_columns = [
        ("capacity", "INTEGER"),
        ("house_type", "VARCHAR(50)"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"  添加列: {col_name}")
            except Exception as e:
                if "Duplicate column" in str(e) or "already exists" in str(e):
                    print(f"  列已存在: {col_name}")
                else:
                    print(f"  添加列失败 {col_name}: {e}")

    print("\n2. 流式加载日历 JSON，构建 unit_id 映射…")
    if not args.calendar.is_file():
        print(f"  日历文件不存在: {args.calendar}")
        sys.exit(1)
    maps = build_calendar_maps(args.calendar)
    calendar_ids = maps["calendar_ids"]
    print(f"  日历唯一 unit_id: {len(calendar_ids)}")

    if args.legacy_price_json and args.legacy_price_json.is_file():
        import json

        with open(args.legacy_price_json, "r", encoding="utf-8") as f:
            legacy = json.load(f)
        for h in legacy.get("houses", []):
            u = str(h.get("unit_id", "")).strip()
            if not u or u not in calendar_ids:
                continue
            p = float(h.get("final_price") or 0)
            if p > 0:
                maps["price_map"][u] = p
        print(f"  已合并 legacy 价目: {args.legacy_price_json}")

    if not args.tags.is_file():
        print(f"  tags 文件不存在: {args.tags}")
        sys.exit(1)

    print("\n3. 流式读取 tags，仅写交集 …")

    db = SessionLocal()
    updated = 0
    added = 0
    skipped_not_in_calendar = 0
    skipped_parse = 0

    try:
        with open(args.tags, "rb") as f:
            for unit_id, item in ijson.kvitems(f, "tags"):
                unit_id_str = str(unit_id).strip()
                if not unit_id_str:
                    continue
                if unit_id_str not in calendar_ids:
                    skipped_not_in_calendar += 1
                    continue

                try:
                    ch = item["data"]["currentHouse"]
                    summary = ch.get("houseSummary", "")
                    bed_room_count = ch.get("bedRoomCount")
                    top = item["data"]["mainPart"]["topModule"]
                    fav_count = top.get("favoriteCount", 0)
                    pos = item["data"]["mainPart"]["dynamicModule"].get("positionModule", {})
                    district = pos.get("areaName", maps["district_map"].get(unit_id_str, ""))
                    trade_area = pos.get("tradeArea", maps["trade_area_map"].get(unit_id_str, ""))
                except (KeyError, TypeError):
                    skipped_parse += 1
                    continue

                parsed = parse_house_summary(summary)

                price = maps["price_map"].get(unit_id_str) or 0.0
                if not price or price <= 0:
                    try:
                        price = float(ch.get("finalPrice", 0) or 0)
                    except (TypeError, ValueError):
                        skipped_parse += 1
                        continue
                    if price <= 0:
                        skipped_parse += 1
                        continue

                try:
                    title = ch.get("houseName", maps["title_map"].get(unit_id_str, ""))
                except Exception:
                    title = maps["title_map"].get(unit_id_str, "")

                hostel_keywords = ["青旅", "青年旅舍", "床位", "床铺", "多人间", "胶囊"]
                if any(kw in title for kw in hostel_keywords):
                    continue

                lat = maps["lat_map"].get(unit_id_str)
                lon = maps["lon_map"].get(unit_id_str)

                existing = db.query(Listing).filter(Listing.unit_id == unit_id_str).first()

                if existing:
                    existing.area = parsed.get("area") or existing.area
                    existing.bedroom_count = bed_room_count or parsed.get("bedroom_count") or existing.bedroom_count
                    existing.bed_count = parsed.get("bed_count") or existing.bed_count
                    existing.capacity = parsed.get("capacity")
                    existing.house_type = parsed.get("house_type")
                    existing.favorite_count = int(fav_count or 0) or maps["fav_map"].get(unit_id_str, 0)
                    existing.district = district or existing.district
                    existing.trade_area = trade_area or existing.trade_area
                    if lat is not None:
                        existing.latitude = lat
                    if lon is not None:
                        existing.longitude = lon
                    updated += 1
                else:
                    db.add(
                        Listing(
                            unit_id=unit_id_str,
                            title=title,
                            district=district,
                            trade_area=trade_area,
                            final_price=price,
                            rating=maps["rating_map"].get(unit_id_str, 0),
                            favorite_count=int(fav_count or 0) or maps["fav_map"].get(unit_id_str, 0),
                            bedroom_count=bed_room_count or parsed.get("bedroom_count", 1),
                            bed_count=parsed.get("bed_count", 1),
                            area=parsed.get("area", 50),
                            capacity=parsed.get("capacity"),
                            house_type=parsed.get("house_type"),
                            longitude=lon,
                            latitude=lat,
                            cover_image=maps["cover_map"].get(unit_id_str, "") or "",
                        )
                    )
                    added += 1

                if (updated + added) % 500 == 0:
                    db.commit()
                    print(f"  已处理 {updated + added} 条...")

        db.commit()
        print(f"\n完成! 更新: {updated} 条, 新增: {added} 条")
        print(f"跳过(tags 有、日历无 unit_id): {skipped_not_in_calendar}")
        print(f"跳过(解析/价格异常): {skipped_parse}")

    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        raise
    finally:
        db.close()

    print("\n4. 验证数据...")
    db = SessionLocal()
    try:
        total = db.query(Listing).count()
        if total <= 0:
            print("  总记录: 0")
            return
        with_area = db.query(Listing).filter(Listing.area.isnot(None)).count()
        with_bedroom = db.query(Listing).filter(Listing.bedroom_count.isnot(None)).count()
        with_capacity = db.query(Listing).filter(Listing.capacity.isnot(None)).count()
        with_type = db.query(Listing).filter(Listing.house_type.isnot(None)).count()

        print(f"  总记录: {total}")
        print(f"  有面积: {with_area} ({with_area/total*100:.1f}%)")
        print(f"  有卧室数: {with_bedroom} ({with_bedroom/total*100:.1f}%)")
        print(f"  有容量: {with_capacity} ({with_capacity/total*100:.1f}%)")
        print(f"  有房屋类型: {with_type} ({with_type/total*100:.1f}%)")
    finally:
        db.close()


if __name__ == "__main__":
    main()

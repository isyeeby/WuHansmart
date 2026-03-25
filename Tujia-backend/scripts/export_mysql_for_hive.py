"""
从 MySQL listings / price_calendars 导出 Hive ODS 用的无表头 TSV（制表符分隔、无字段内制表符）。
输出到 data/hive_import/listings_for_hive.tsv 与 price_calendar_for_hive.tsv，
供 sql/hive_load_data.hql 中 LOAD DATA LOCAL INPATH 使用。

用法（在 Tujia-backend 目录）:
  python scripts/export_mysql_for_hive.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def _cell(v, max_len: int = 12000) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, Decimal):
        v = float(v)
    s = str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")
    return s[:max_len] if len(s) > max_len else s


def _int(v, default: int = 0) -> int:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def export_listings(engine, out_path: str) -> int:
    q = text(
        """
        SELECT
            unit_id, title, district, trade_area, final_price, rating,
            house_tags, cover_image, house_pics, bedroom_count, bed_count, area, favorite_count,
            facility_module_json, comment_module_json, landlord_module_json
        FROM listings
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)

    rows = []
    now_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for _, r in df.iterrows():
        price = _float(r.get("final_price"), 0.0)
        tags = _cell(r.get("house_tags"), 12000)
        cover = _cell(r.get("cover_image"), 2000)
        pics = _cell(r.get("house_pics"), 4000)
        image_urls = cover if cover else (pics[:2000] if pics else "")
        row = [
            _cell(r.get("unit_id")),
            _cell(r.get("title"), 2000),
            _cell(r.get("district")),
            _cell(r.get("trade_area")),
            f"{price:.2f}" if price else "0",
            f"{_float(r.get('rating'), 0):.1f}",
            "0",
            tags,
            image_urls,
            "100",
            str(_int(r.get("bedroom_count"), 0)),
            "0",
            str(int(_float(r.get("area"), 0))) if _float(r.get("area"), 0) > 0 else "",
            str(_int(r.get("favorite_count"), 0)),
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            now_ts,
            _cell(r.get("facility_module_json"), 50000),
            _cell(r.get("comment_module_json"), 50000),
            _cell(r.get("landlord_module_json"), 50000),
        ]
        rows.append("\t".join(row))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows))
        if rows:
            f.write("\n")
    return len(rows)


def export_calendars(engine, out_path: str) -> int:
    q = text(
        """
        SELECT id, unit_id, `date`, price
        FROM price_calendars
        ORDER BY id
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)

    rows = []
    for _, r in df.iterrows():
        pid = _int(r.get("id"), 0)
        uid = _cell(r.get("unit_id"))
        d = _cell(r.get("date"))
        price = _float(r.get("price"), 0.0)
        rows.append("\t".join([str(pid), uid, d, f"{price:.2f}", ""]))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows))
        if rows:
            f.write("\n")
    return len(rows)


def main() -> None:
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hive_import")
    listings_tsv = os.path.join(out_dir, "listings_for_hive.tsv")
    cal_tsv = os.path.join(out_dir, "price_calendar_for_hive.tsv")

    engine = create_engine(settings.DATABASE_URL)
    n1 = export_listings(engine, listings_tsv)
    n2 = export_calendars(engine, cal_tsv)
    print(f"已写入 {listings_tsv} 行数: {n1}")
    print(f"已写入 {cal_tsv} 行数: {n2}")


if __name__ == "__main__":
    main()

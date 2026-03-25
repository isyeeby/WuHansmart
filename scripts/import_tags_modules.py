# -*- coding: utf-8 -*-
"""
将 tujia_calendar_data_tags.json 中 mainPart.dynamicModule 的
facilityModule / commentModule / landlordModule 截断后写入 MySQL listings 三列。

仅更新「日历 JSON 中存在的 unit_id」且 listings 表中已存在的记录（与交集策略一致）。
用法（在 Tujia-backend 目录）:
  python scripts/import_tags_modules.py
  python scripts/import_tags_modules.py --tags path/to/tags.json --calendar path/to/calendar.json
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ijson  # type: ignore

from app.db.database import Listing, SessionLocal
from scripts.listing_sources import build_calendar_maps

TAGS_PATH = Path(__file__).resolve().parent.parent / "tujia_calendar_data_tags.json"
CALENDAR_PATH = Path(__file__).resolve().parent.parent / "tujia_calendar_data.json"

MAX_CHARS_PER_COLUMN = 50000
MAX_COMMENT_LIST_ITEMS = 5


def _truncate_json(obj: Any, max_chars: int) -> str:
    """保证合法 JSON；过长时压缩 commentList 条数直至满足上限。"""
    if isinstance(obj, dict) and "commentList" in obj and isinstance(obj["commentList"], list):
        for n in range(MAX_COMMENT_LIST_ITEMS, -1, -1):
            o2 = deepcopy(obj)
            o2["commentList"] = o2["commentList"][:n]
            if n < len(obj.get("commentList") or []):
                o2["commentList_note"] = f"展示前{n}条"
            s = json.dumps(o2, ensure_ascii=False, default=str)
            if len(s) <= max_chars:
                return s
        o2 = {k: v for k, v in obj.items() if k != "commentList"}
        o2["_commentList_omitted"] = True
        s = json.dumps(o2, ensure_ascii=False, default=str)
        if len(s) <= max_chars:
            return s
    s = json.dumps(obj, ensure_ascii=False, default=str)
    if len(s) <= max_chars:
        return s
    return json.dumps(
        {"_truncated": True, "preview": s[: max_chars - 200]},
        ensure_ascii=False,
    )


def _prune_facility(mod: Any) -> Any:
    if not isinstance(mod, dict):
        return {}
    out = {k: mod[k] for k in ("topScroll", "houseSummary", "houseContent") if k in mod}
    if "houseFacility" in mod:
        out["houseFacility"] = mod["houseFacility"]
    if "bedRoomSummary" in mod:
        out["bedRoomSummary"] = mod["bedRoomSummary"]
    if "cHotelFacility" in mod:
        hf = mod["cHotelFacility"]
        out["cHotelFacility"] = hf if isinstance(hf, dict) else str(hf)[:2000]
    return out


def _prune_comment(mod: Any) -> Any:
    if not isinstance(mod, dict):
        return {}
    keys = (
        "overall",
        "scoreTitle",
        "scoreTitleV2",
        "totalCount",
        "totalCountStr",
        "subScores",
        "subScoresFocus",
        "commentTagVo",
        "commentTabType",
        "evaluationModule",
    )
    out: Dict[str, Any] = {k: mod[k] for k in keys if k in mod}
    cl = mod.get("commentList")
    if isinstance(cl, list) and cl:
        slim = []
        for item in cl[:MAX_COMMENT_LIST_ITEMS]:
            if isinstance(item, dict):
                # 途家正文在 commentDetail，不是 content
                keys = (
                    "commentDetail",
                    "commentDetailTranslation",
                    "content",
                    "overall",
                    "averageScore",
                    "score",
                    "userName",
                    "checkInDate",
                    "createdTime",
                    "userTags",
                    "orderTotalStayNight",
                    "houseName",
                )
                slim.append({kk: item.get(kk) for kk in keys if kk in item})
            else:
                slim.append(str(item)[:500])
        out["commentList"] = slim
        out["commentList_note"] = f"前{len(slim)}条，共{len(cl)}条"
    return out


def _prune_landlord(mod: Any) -> Any:
    if not isinstance(mod, dict):
        return {}
    keys = (
        "hotelId",
        "hotelName",
        "hotelTags",
        "landlordTag",
        "landlordLevel",
        "landlordLevelUrl",
        "isReplyTimeMoreThan5Min",
        "hotelSummary",
        "businessType",
        "topScroll",
    )
    return {k: mod[k] for k in keys if k in mod}


def _extract_modules(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        dm = item["data"]["mainPart"]["dynamicModule"]
    except (KeyError, TypeError):
        return None, None, None
    if not isinstance(dm, dict):
        return None, None, None

    fac = dm.get("facilityModule")
    com = dm.get("commentModule")
    ll = dm.get("landlordModule")

    fj = _truncate_json(_prune_facility(fac), MAX_CHARS_PER_COLUMN) if fac else None
    cj = _truncate_json(_prune_comment(com), MAX_CHARS_PER_COLUMN) if com else None
    lj = _truncate_json(_prune_landlord(ll), MAX_CHARS_PER_COLUMN) if ll else None
    return fj, cj, lj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", type=Path, default=TAGS_PATH)
    parser.add_argument("--calendar", type=Path, default=CALENDAR_PATH)
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = parser.parse_args()

    if not args.calendar.is_file():
        print(f"日历文件不存在: {args.calendar}")
        sys.exit(1)
    if not args.tags.is_file():
        print(f"tags 文件不存在: {args.tags}")
        sys.exit(1)

    maps = build_calendar_maps(args.calendar)
    calendar_ids = maps["calendar_ids"]
    print(f"日历 unit_id 数: {len(calendar_ids)}")

    db = SessionLocal()
    updated = 0
    skipped_no_listing = 0
    skipped_not_in_calendar = 0
    errors = 0

    try:
        with open(args.tags, "rb") as f:
            for unit_id, item in ijson.kvitems(f, "tags"):
                uid = str(unit_id).strip()
                if not uid:
                    continue
                if uid not in calendar_ids:
                    skipped_not_in_calendar += 1
                    continue
                if not isinstance(item, dict):
                    errors += 1
                    continue

                fj, cj, lj = _extract_modules(item)
                if fj is None and cj is None and lj is None:
                    continue

                row = db.query(Listing).filter(Listing.unit_id == uid).first()
                if not row:
                    skipped_no_listing += 1
                    continue

                if args.dry_run:
                    updated += 1
                    continue

                if fj:
                    row.facility_module_json = fj
                if cj:
                    row.comment_module_json = cj
                if lj:
                    row.landlord_module_json = lj
                updated += 1
                if updated % 200 == 0:
                    db.commit()
                    print(f"  已提交 {updated} 条…")

        if not args.dry_run:
            db.commit()
    finally:
        db.close()

    print(
        f"完成: 更新 {updated} 条; 跳过(无 listings 行) {skipped_no_listing}; "
        f"跳过(日历无此 id) {skipped_not_in_calendar}; 解析失败 {errors}"
    )


if __name__ == "__main__":
    main()

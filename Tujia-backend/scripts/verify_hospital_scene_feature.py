# -*- coding: utf-8 -*-
"""一次性验证：listings 列、距离/scene 覆盖率、医疗条件推荐与 nearest_hospital_km 回包。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, inspect

from app.db.database import Listing, SessionLocal, engine
from app.services.recommender import recommendation_service


def main() -> None:
    print("=== 1. 数据库表与列 ===")
    insp = inspect(engine)
    if not insp.has_table("listings"):
        print("FAIL: 无 listings 表")
        sys.exit(1)
    cols = {c["name"] for c in insp.get_columns("listings")}
    for c in (
        "scene_scores",
        "nearest_hospital_km",
        "nearest_hospital_name",
        "latitude",
        "longitude",
    ):
        print(f"  {c}: {'OK' if c in cols else 'MISSING'}")

    db = SessionLocal()
    try:
        n = db.query(func.count(Listing.unit_id)).scalar()
        n_km = (
            db.query(func.count(Listing.unit_id))
            .filter(Listing.nearest_hospital_km.isnot(None))
            .scalar()
        )
        n_lat = (
            db.query(func.count(Listing.unit_id))
            .filter(Listing.latitude.isnot(None), Listing.longitude.isnot(None))
            .scalar()
        )
        n_scene = (
            db.query(func.count(Listing.unit_id))
            .filter(Listing.scene_scores.isnot(None))
            .scalar()
        )
        n_hname = (
            db.query(func.count(Listing.unit_id))
            .filter(Listing.nearest_hospital_name.isnot(None))
            .filter(Listing.nearest_hospital_name != "")
            .scalar()
        )
        print("=== 2. 行数统计 ===")
        print(f"  listings 总数: {n}")
        print(f"  nearest_hospital_km 非空: {n_km}")
        print(f"  nearest_hospital_name 非空: {n_hname}")
        print(f"  有经纬度: {n_lat}")
        print(f"  scene_scores 非空: {n_scene}")

        row = db.query(Listing).filter(Listing.nearest_hospital_km.isnot(None)).first()
        if row:
            print("=== 3. 样例（有距离的房源）===")
            print(f"  unit_id: {row.unit_id} km: {float(row.nearest_hospital_km)}")
            print(f"  hospital: {getattr(row, 'nearest_hospital_name', None)!r}")
            ss = row.scene_scores
            if isinstance(ss, dict):
                print(f"  scene_scores.medical: {ss.get('medical')}")
        else:
            print("=== 3. 无 nearest_hospital_km 非空行：请运行 listing_scene_pipeline 回写 ===")
    finally:
        db.close()

    print("=== 4. 条件推荐 travel_purpose=medical top_k=5 ===")
    resp = recommendation_service.get_condition_based_recommendations(
        travel_purpose="medical",
        top_k=5,
    )
    for i, r in enumerate(resp.recommendations[:5], 1):
        reason = (r.reason or "")[:72]
        print(
            f"  {i}. unit_id={r.unit_id} match_score={r.match_score} "
            f"km={r.nearest_hospital_km!r} name={r.nearest_hospital_name!r}"
        )
        print(f"      reason: {reason}")

    print("=== 5. HTTP 自检（需本机 8000 已启动 uvicorn）===")
    try:
        import urllib.request

        url = "http://127.0.0.1:8000/api/recommend/?travel_purpose=medical&top_k=2"
        with urllib.request.urlopen(url, timeout=10) as f:
            data = json.loads(f.read().decode("utf-8"))
        for item in data.get("recommendations", [])[:2]:
            print(
                "  API",
                item.get("unit_id"),
                "km=",
                item.get("nearest_hospital_km"),
                "name=",
                item.get("nearest_hospital_name"),
                "match_score=",
                item.get("match_score"),
            )
    except Exception as e:
        print("  (跳过)", e)

    print("=== 完成 ===")


if __name__ == "__main__":
    main()

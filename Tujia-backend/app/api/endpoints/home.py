"""
首页数据接口 - 平台统计、热门商圈、推荐房源、热力图
"""
from typing import List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.database import get_db, get_user_by_username, Listing
from app.db.hive import execute_query_to_df
from app.core.security import get_optional_user
from app.core.recommend_travel import travel_purpose_for_condition_recommend
from app.services.kpi_helpers import occupancy_proxy, market_return_index
from app.services.recommender import recommendation_service

router = APIRouter()


# ============== Schemas ==============


class HomeStatsResponse(BaseModel):
    """平台统计数据响应"""
    district_count: int
    listing_count: int
    data_days: int
    avg_roi: float
    data_source: str = Field(
        default="live",
        description="hive=来自 Hive ODS 聚合；mysql=来自 MySQL listings；live=混合或未标注",
    )


class HotDistrictItem(BaseModel):
    name: str
    heat: int
    avg_price: float
    price_trend: float


class HotDistrictsResponse(BaseModel):
    districts: List[HotDistrictItem]
    data_source: str = Field(
        description="hive|mysql|demo_fallback|empty",
    )


class HomeRecommendationItem(BaseModel):
    unit_id: str
    title: str
    district: Optional[str] = None
    price: float
    rating: float
    tags: List[str]
    image_url: Optional[str]
    match_score: int


class HomeRecommendationsResponse(BaseModel):
    listings: List[HomeRecommendationItem]
    data_source: str = Field(description="mysql|hive|demo_fallback")


class HeatmapPoint(BaseModel):
    name: str
    x: int
    y: int
    value: int


class HeatmapResponse(BaseModel):
    points: List[HeatmapPoint]
    data_source: str = Field(description="hive|mysql|demo_fallback|empty")


def _demo_hot_districts(limit: int) -> List[dict]:
    base = [
        {"name": "江汉路", "heat": 95, "avg_price": 350.5, "price_trend": 5.2},
        {"name": "光谷", "heat": 88, "avg_price": 280.0, "price_trend": 3.1},
        {"name": "楚河汉街", "heat": 85, "avg_price": 420.0, "price_trend": 7.5},
        {"name": "黄鹤楼", "heat": 82, "avg_price": 310.0, "price_trend": -2.3},
        {"name": "武昌火车站", "heat": 78, "avg_price": 220.0, "price_trend": 1.8},
        {"name": "汉口火车站", "heat": 75, "avg_price": 240.0, "price_trend": 0.5},
        {"name": "昙华林", "heat": 70, "avg_price": 290.0, "price_trend": 4.2},
        {"name": "东西湖区", "heat": 65, "avg_price": 180.0, "price_trend": 8.1},
    ]
    return base[:limit]


def _hot_districts_from_mysql(db: Session, limit: int) -> List[dict]:
    q = (
        db.query(
            Listing.district,
            func.count(Listing.unit_id).label("cnt"),
            func.avg(Listing.final_price).label("avg_price"),
            func.avg(Listing.rating).label("avg_rating"),
        )
        .filter(Listing.district.isnot(None), Listing.district != "")
        .group_by(Listing.district)
        .order_by(desc("cnt"), desc("avg_rating"))
        .limit(limit)
        .all()
    )
    if not q:
        return []
    prices = [float(r.avg_price or 0) for r in q if r.avg_price]
    mean_price = sum(prices) / len(prices) if prices else 0.0
    max_count = max(int(r.cnt or 0) for r in q) or 1
    out: List[dict] = []
    for r in q:
        cnt = int(r.cnt or 0)
        ap = float(r.avg_price or 0)
        ar = float(r.avg_rating or 0)
        count_score = (cnt / max_count) * 60
        rating_score = (ar / 5.0) * 40 if ar else 0
        heat = int(min(100, count_score + rating_score))
        trend = round((ap - mean_price) / mean_price * 100, 1) if mean_price > 0 else 0.0
        out.append(
            {
                "name": r.district or "",
                "heat": heat,
                "avg_price": round(ap, 2),
                "price_trend": trend,
            }
        )
    return out


def _heatmap_from_mysql(db: Session, limit: int = 20) -> List[dict]:
    rows = (
        db.query(
            Listing.district,
            func.avg(Listing.final_price).label("avg_price"),
            func.count(Listing.unit_id).label("listing_count"),
            func.avg(Listing.longitude).label("avg_lng"),
            func.avg(Listing.latitude).label("avg_lat"),
        )
        .filter(
            Listing.district.isnot(None),
            Listing.longitude.isnot(None),
            Listing.latitude.isnot(None),
        )
        .group_by(Listing.district)
        .order_by(desc("listing_count"))
        .limit(limit)
        .all()
    )
    if not rows:
        return []
    max_count = max(int(r.listing_count or 0) for r in rows) or 1
    points: List[dict] = []
    for r in rows:
        lng = float(r.avg_lng or 114.3)
        lat = float(r.avg_lat or 30.6)
        x = int(((lng - 113.7) / (114.8 - 113.7)) * 100)
        y = int(((lat - 30.5) / (30.8 - 30.5)) * 100)
        value = int((int(r.listing_count or 0) / max_count) * 100) if max_count > 0 else 50
        points.append(
            {
                "name": r.district or "",
                "x": max(0, min(100, x)),
                "y": max(0, min(100, y)),
                "value": value,
            }
        )
    return points


def _demo_heatmap_points() -> List[dict]:
    return [
        {"name": "江汉路", "x": 45, "y": 60, "value": 95},
        {"name": "光谷", "x": 75, "y": 45, "value": 88},
        {"name": "楚河汉街", "x": 50, "y": 55, "value": 85},
        {"name": "黄鹤楼", "x": 48, "y": 50, "value": 82},
        {"name": "武昌火车站", "x": 52, "y": 48, "value": 78},
        {"name": "汉口火车站", "x": 42, "y": 65, "value": 75},
        {"name": "昙华林", "x": 51, "y": 52, "value": 70},
        {"name": "东西湖区", "x": 35, "y": 70, "value": 65},
        {"name": "洪山区", "x": 70, "y": 50, "value": 60},
        {"name": "蔡甸区", "x": 25, "y": 40, "value": 55},
    ]


# ============== API Endpoints ==============


@router.get("/stats", response_model=HomeStatsResponse)
def get_home_stats(db: Session = Depends(get_db)):
    """
    获取平台统计数据：优先 Hive ODS；失败或无行则用 MySQL listings。
    """
    district_count = 0
    listing_count = 0
    avg_rating = 0.0
    avg_price = 0.0
    data_source = "mysql"

    try:
        query = """
        SELECT
            COUNT(DISTINCT district) as district_count,
            COUNT(*) as listing_count,
            AVG(price) as avg_price,
            AVG(rating) as avg_rating
        FROM homestay_db.ods_listings
        """
        df = execute_query_to_df(query)
        if not df.empty:
            listing_count = int(df["listing_count"].iloc[0])
            if listing_count > 0:
                district_count = int(df["district_count"].iloc[0])
                avg_price = float(df["avg_price"].iloc[0] or 0)
                avg_rating = float(df["avg_rating"].iloc[0] or 0)
                data_source = "hive"
    except Exception:
        pass

    if listing_count == 0:
        district_count = db.query(func.count(func.distinct(Listing.district))).scalar() or 0
        listing_count = db.query(Listing).count()
        avg_price_r = db.query(func.avg(Listing.final_price)).scalar()
        avg_price = float(avg_price_r) if avg_price_r else 0.0
        avg_rating_r = db.query(func.avg(Listing.rating)).scalar()
        avg_rating = float(avg_rating_r) if avg_rating_r else 0.0
        data_source = "mysql"

    avg_fav_r = db.query(func.avg(Listing.favorite_count)).scalar()
    avg_favorites = float(avg_fav_r) if avg_fav_r else 0.0
    occ = occupancy_proxy(avg_rating, avg_favorites)
    avg_roi = market_return_index(avg_price, occ, avg_rating, avg_favorites, listing_count)

    return {
        "district_count": district_count,
        "listing_count": listing_count,
        "data_days": 30,
        "avg_roi": avg_roi,
        "data_source": data_source,
    }


@router.get("/hot-districts", response_model=HotDistrictsResponse)
def get_hot_districts(
    limit: int = Query(8, ge=1, le=20, description="返回数量"),
    db: Session = Depends(get_db),
):
    try:
        query = f"""
        SELECT
            district,
            COUNT(*) as listing_count,
            AVG(price) as avg_price,
            AVG(rating) as avg_rating,
            STDDEV(price) as price_std
        FROM homestay_db.ods_listings
        WHERE district IS NOT NULL
        GROUP BY district
        ORDER BY listing_count DESC, avg_rating DESC
        LIMIT {limit}
        """
        df = execute_query_to_df(query)
        districts: List[dict] = []
        if not df.empty:
            max_count = df["listing_count"].max()
            mean_price = float(df["avg_price"].mean()) if df["avg_price"].notna().any() else 0.0
            for _, row in df.iterrows():
                count_score = (row["listing_count"] / max_count) * 60 if max_count > 0 else 0
                rating_score = (row["avg_rating"] / 5.0) * 40 if row["avg_rating"] else 0
                heat = int(count_score + rating_score)
                ap = float(row["avg_price"] or 0)
                price_trend = (
                    round((ap - mean_price) / mean_price * 100, 1) if mean_price > 0 else 0.0
                )
                districts.append(
                    {
                        "name": row["district"],
                        "heat": min(100, heat),
                        "avg_price": round(row["avg_price"], 2) if row["avg_price"] else 0,
                        "price_trend": price_trend,
                    }
                )
            return {"districts": districts, "data_source": "hive"}
    except Exception:
        pass

    mysql_d = _hot_districts_from_mysql(db, limit)
    if mysql_d:
        return {"districts": mysql_d, "data_source": "mysql"}

    return {"districts": _demo_hot_districts(limit), "data_source": "demo_fallback"}


@router.get("/recommendations", response_model=HomeRecommendationsResponse)
def get_home_recommendations(
    limit: int = Query(6, ge=1, le=12, description="返回数量"),
    current_username: Optional[str] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    首页推荐：优先 MySQL listings；无数据时再尝试 Hive；最后演示兜底（见 data_source）。
    """
    import json

    user_prefs = {}
    user = None
    travel_api = None
    req_fac_keys: List[str] = []
    if current_username:
        user = get_user_by_username(db, username=current_username)
        if user:
            user_prefs = {
                "preferred_district": user.preferred_district,
                "price_min": user.preferred_price_min,
                "price_max": user.preferred_price_max,
            }
            if user.travel_purpose:
                travel_api = travel_purpose_for_condition_recommend(user.travel_purpose)
            if isinstance(user.required_facilities, list):
                req_fac_keys = recommendation_service.map_user_facilities_to_api_keys(
                    user.required_facilities
                )

    def _tags_from_house_tags(raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            out: List[str] = []
            for item in data[:5]:
                if isinstance(item, dict):
                    t = item.get("text") or (item.get("tagText") or {}).get("text")
                    if isinstance(t, str) and t:
                        out.append(t)
                elif isinstance(item, str):
                    out.append(item)
            return out[:3]
        except (json.JSONDecodeError, TypeError):
            return []

    q = db.query(Listing).filter(Listing.final_price.isnot(None), Listing.final_price > 0)
    if user_prefs.get("preferred_district"):
        q = q.filter(Listing.district == user_prefs["preferred_district"])
    pmn = user_prefs.get("price_min")
    pmx = user_prefs.get("price_max")
    if pmn is not None:
        q = q.filter(Listing.final_price >= pmn)
    if pmx is not None:
        q = q.filter(Listing.final_price <= pmx)

    rows = q.order_by(desc(Listing.rating), desc(Listing.favorite_count)).limit(max(limit * 3, 12)).all()

    def _home_sort_key(row: Listing) -> tuple:
        r = float(row.rating or 0)
        fc = int(row.favorite_count or 0)
        base = min(100, int(r / 5.0 * 55 + min(fc, 800) / 800.0 * 45))
        scene_extra = 0.0
        if travel_api:
            scene_extra = recommendation_service._scene_purpose_bonus(row, travel_api)
        tag_text = " ".join(_tags_from_house_tags(row.house_tags))
        fac_extra = 0
        for fk in req_fac_keys:
            kws = recommendation_service.FACILITY_MAP.get(fk, [fk])
            if any(kw in tag_text for kw in kws):
                fac_extra += 2
        sort_key = base + int(scene_extra * 100) + fac_extra
        return (-sort_key, str(row.unit_id))

    listings: List[dict] = []

    for row in sorted(rows, key=_home_sort_key)[:limit]:
        r = float(row.rating or 0)
        fc = int(row.favorite_count or 0)
        base = min(100, int(r / 5.0 * 55 + min(fc, 800) / 800.0 * 45))
        scene_extra = (
            recommendation_service._scene_purpose_bonus(row, travel_api) if travel_api else 0.0
        )
        tag_text = " ".join(_tags_from_house_tags(row.house_tags))
        fac_extra = sum(
            2
            for fk in req_fac_keys
            if any(kw in tag_text for kw in recommendation_service.FACILITY_MAP.get(fk, [fk]))
        )
        match_score = min(100, base + int(scene_extra * 100) + fac_extra)
        title = row.title or ""
        listings.append(
            {
                "unit_id": str(row.unit_id),
                "title": (title[:20] + "...") if len(title) > 20 else title,
                "price": float(row.final_price),
                "rating": r,
                "tags": _tags_from_house_tags(row.house_tags),
                "image_url": row.cover_image,
                "match_score": match_score,
            }
        )

    if listings:
        return {"listings": listings, "data_source": "mysql"}

    try:
        query = """
        SELECT
            unit_id,
            title,
            price,
            rating,
            tags,
            cover_image,
            district,
            comment_count
        FROM homestay_db.ods_listings
        ORDER BY rating DESC, comment_count DESC
        LIMIT {n}
        """.format(n=limit * 2)
        df = execute_query_to_df(query)
        if not df.empty:
            for _, row in df.head(limit).iterrows():
                tags = []
                if row.get("tags"):
                    try:
                        t = json.loads(row["tags"])
                        if isinstance(t, list):
                            tags = t[:3]
                    except (json.JSONDecodeError, TypeError):
                        tags = []
                r = float(row["rating"] or 0)
                cc = int(row.get("comment_count") or 0)
                match_score = min(100, int(r / 5.0 * 55 + min(cc, 200) / 200.0 * 45))
                t = str(row.get("title") or "")
                d = row.get("district")
                listings.append(
                    {
                        "unit_id": str(row["unit_id"]),
                        "title": (t[:20] + "...") if len(t) > 20 else t,
                        "district": str(d) if d is not None else None,
                        "price": float(row["price"] or 0),
                        "rating": r,
                        "tags": tags,
                        "image_url": row.get("cover_image"),
                        "match_score": match_score,
                    }
                )
            if listings:
                return {"listings": listings, "data_source": "hive"}
    except Exception:
        pass

    demo = [
        {
            "unit_id": "83382562",
            "title": "栖心·雅集｜新天地铁站·中法同济医院附近",
            "district": "汉阳区",
            "price": 191,
            "rating": 5.0,
            "tags": ["首单特惠", "实拍看房"],
            "image_url": "https://pic.tujia.com/upload/landlordunit/day_250830/thumb/202508302004465433_700_467.jpg",
            "match_score": 95,
        },
        {
            "unit_id": "80004148",
            "title": "【绮彩拾光居】复式loft／投影／精装修",
            "district": "武昌区",
            "price": 201,
            "rating": 4.9,
            "tags": ["今夜特价", "近地铁"],
            "image_url": "",
            "match_score": 88,
        },
        {
            "unit_id": "72914671",
            "title": "【A 梦民宿】『独白』Loft 丨两居室",
            "district": "江汉区",
            "price": 210,
            "rating": 5.0,
            "tags": ["天天特惠", "现代风"],
            "image_url": "",
            "match_score": 85,
        },
    ][:limit]
    return {"listings": demo, "data_source": "demo_fallback"}


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap_data(db: Session = Depends(get_db)):
    try:
        query = """
        SELECT
            district,
            AVG(price) as avg_price,
            COUNT(*) as listing_count,
            AVG(longitude) as avg_lng,
            AVG(latitude) as avg_lat
        FROM homestay_db.ods_listings
        WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        GROUP BY district
        ORDER BY listing_count DESC
        LIMIT 20
        """
        df = execute_query_to_df(query)
        points: List[dict] = []
        if not df.empty:
            max_count = df["listing_count"].max()
            for _, row in df.iterrows():
                lng = row["avg_lng"] if row["avg_lng"] else 114.3
                lat = row["avg_lat"] if row["avg_lat"] else 30.6
                x = int(((lng - 113.7) / (114.8 - 113.7)) * 100)
                y = int(((lat - 30.5) / (30.8 - 30.5)) * 100)
                value = int((row["listing_count"] / max_count) * 100) if max_count > 0 else 50
                points.append(
                    {
                        "name": row["district"],
                        "x": max(0, min(100, x)),
                        "y": max(0, min(100, y)),
                        "value": value,
                    }
                )
            return {"points": points, "data_source": "hive"}
    except Exception:
        pass

    mysql_pts = _heatmap_from_mysql(db, 20)
    if mysql_pts:
        return {"points": mysql_pts, "data_source": "mysql"}

    return {"points": _demo_heatmap_points(), "data_source": "demo_fallback"}

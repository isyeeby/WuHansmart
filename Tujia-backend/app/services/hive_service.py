"""
数仓查询适配层：分析类指标优先读 Hive（DWS/ADS），失败或未启用时回退 MySQL。
行级查询（单套房源、按区列表）始终走 MySQL，保证延迟与一致性。
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import func

from app.core.config import settings
from app.db.database import Listing, SessionLocal
from app.services.price_opportunity_filters import is_eligible_price_opportunity_listing

logger = logging.getLogger(__name__)


def _sql_escape(s: str) -> str:
    return (s or "").replace("'", "''")


def _hive_df_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        rec: Dict[str, Any] = {}
        for k, v in row.items():
            if v is None or (isinstance(v, float) and pd.isna(v)):
                rec[k] = None
            elif isinstance(v, Decimal):
                rec[k] = float(v)
            elif hasattr(v, "item"):
                try:
                    rec[k] = v.item()
                except Exception:
                    rec[k] = v
            else:
                rec[k] = v
        out.append(rec)
    return out


def _hive_analytics_query(sql: str) -> Optional[pd.DataFrame]:
    """优先 impyla/pyhive 直连 HS2，再尝试 Docker 内 hive CLI。"""
    from app.db.hive import execute_query_to_df

    try:
        df = execute_query_to_df(sql)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.debug("Hive JDBC 查询未返回数据: %s", e)

    try:
        from app.services.hive_docker_service import hive_docker_service

        if not hive_docker_service.check_connection():
            return None
        df2 = hive_docker_service.run_query_dataframe(sql)
        if df2 is not None and not df2.empty:
            return df2
    except Exception as e:
        logger.debug("Hive Docker 查询失败: %s", e)

    return None


class HiveDataService:
    """分析类：优先 Hive DWS/ADS；行级：MySQL。"""

    def __init__(self) -> None:
        self.database = "mysql"

    def _hive_enabled(self) -> bool:
        return bool(getattr(settings, "HIVE_ANALYTICS_PRIMARY", True))

    # ---------- 商圈统计 ----------
    def get_district_stats(self, limit: int = 50) -> List[Dict]:
        if self._hive_enabled():
            sql = f"""
            SELECT district, avg_price, median_price, total_listings, avg_rating, avg_heat_score
            FROM dws_district_stats
            WHERE dt = (SELECT MAX(dt) FROM dws_district_stats)
            ORDER BY avg_price DESC
            LIMIT {int(limit)}
            """
            df = _hive_analytics_query(sql)
            if df is not None and not df.empty:
                rows = _hive_df_to_records(df)
                norm: List[Dict] = []
                for r in rows:
                    med = r.get("median_price")
                    avg = r.get("avg_price") or 0
                    norm.append(
                        {
                            "district": r.get("district"),
                            "avg_price": round(float(avg), 2) if avg is not None else 0,
                            "median_price": round(float(med), 2)
                            if med is not None
                            else round(float(avg), 2),
                            "total_listings": int(r.get("total_listings") or 0),
                            "avg_rating": round(float(r.get("avg_rating") or 0), 2),
                            "avg_heat_score": round(float(r.get("avg_heat_score") or 0), 1),
                        }
                    )
                logger.info("get_district_stats: source=hive_dws rows=%s", len(norm))
                return norm

        return self._mysql_get_district_stats(limit)

    def _mysql_get_district_stats(self, limit: int) -> List[Dict]:
        db = SessionLocal()
        try:
            results = (
                db.query(
                    Listing.district,
                    func.avg(Listing.final_price).label("avg_price"),
                    func.count(Listing.unit_id).label("total_listings"),
                    func.avg(Listing.rating).label("avg_rating"),
                    func.avg(Listing.favorite_count).label("avg_heat_score"),
                )
                .filter(Listing.final_price.isnot(None))
                .group_by(Listing.district)
                .order_by(func.avg(Listing.final_price).desc())
                .limit(limit)
                .all()
            )
            logger.info("get_district_stats: source=mysql rows=%s", len(results))
            return [
                {
                    "district": r.district,
                    "avg_price": round(float(r.avg_price), 2) if r.avg_price else 0,
                    "median_price": round(float(r.avg_price), 2) if r.avg_price else 0,
                    "total_listings": int(r.total_listings),
                    "avg_rating": round(float(r.avg_rating), 2) if r.avg_rating else 0,
                    "avg_heat_score": round(float(r.avg_heat_score or 0), 1),
                }
                for r in results
            ]
        finally:
            db.close()

    # ---------- 设施溢价 ----------
    def get_facility_analysis(self) -> List[Dict]:
        if self._hive_enabled():
            sql = """
            SELECT facility_name, has_count, no_count, avg_price_with, avg_price_without,
                   price_premium, premium_rate
            FROM dws_facility_analysis
            WHERE dt = (SELECT MAX(dt) FROM dws_facility_analysis)
            ORDER BY price_premium DESC
            """
            df = _hive_analytics_query(sql)
            if df is not None and not df.empty:
                rows = _hive_df_to_records(df)
                logger.info("get_facility_analysis: source=hive_dws rows=%s", len(rows))
                return [
                    {
                        "facility_name": r.get("facility_name"),
                        "has_count": int(r.get("has_count") or 0),
                        "avg_price_with": round(float(r.get("avg_price_with") or 0), 2),
                        "avg_price_without": round(float(r.get("avg_price_without") or 0), 2),
                        "price_premium": round(float(r.get("price_premium") or 0), 2),
                        "premium_rate": round(float(r.get("premium_rate") or 0), 2),
                    }
                    for r in rows
                ]

        return self._mysql_get_facility_analysis()

    def _mysql_get_facility_analysis(self) -> List[Dict]:
        db = SessionLocal()
        try:
            listings = db.query(Listing).filter(Listing.final_price.isnot(None)).all()
            if not listings:
                return []
            facilities = ["投影", "浴缸", "智能锁", "洗衣机", "厨房"]
            results = []
            for facility in facilities:
                with_facility = [
                    l for l in listings if l.house_tags and facility in (l.house_tags or "")
                ]
                without_facility = [
                    l for l in listings if not l.house_tags or facility not in l.house_tags
                ]
                if with_facility and without_facility:
                    avg_with = sum(float(l.final_price) for l in with_facility) / len(
                        with_facility
                    )
                    avg_without = sum(float(l.final_price) for l in without_facility) / len(
                        without_facility
                    )
                    premium = avg_with - avg_without
                    premium_rate = (premium / avg_without * 100) if avg_without > 0 else 0
                    results.append(
                        {
                            "facility_name": facility,
                            "has_count": len(with_facility),
                            "avg_price_with": round(avg_with, 2),
                            "avg_price_without": round(avg_without, 2),
                            "price_premium": round(premium, 2),
                            "premium_rate": round(premium_rate, 2),
                        }
                    )
            logger.info("get_facility_analysis: source=mysql rows=%s", len(results))
            return sorted(results, key=lambda x: x["price_premium"], reverse=True)
        finally:
            db.close()

    # ---------- 价格洼地（ADS，商圈均价作预测）----------
    def get_price_opportunities(
        self, min_gap_rate: float = 20.0, limit: int = 20
    ) -> List[Dict]:
        if self._hive_enabled():
            sql = f"""
            SELECT unit_id, district, current_price, predicted_price, price_gap, gap_rate,
                   rating, tags, reason
            FROM ads_price_opportunities
            WHERE dt = (SELECT MAX(dt) FROM ads_price_opportunities)
            ORDER BY gap_rate DESC
            LIMIT {int(max(limit, 50))}
            """
            df = _hive_analytics_query(sql)
            if df is not None and not df.empty:
                rows = _hive_df_to_records(df)
                out: List[Dict] = []
                for r in rows:
                    gr = float(r.get("gap_rate") or 0)
                    if gr < float(min_gap_rate):
                        continue
                    cp = float(r.get("current_price") or 0)
                    pp = float(r.get("predicted_price") or 0)
                    pg = float(r.get("price_gap") or 0)
                    out.append(
                        {
                            "unit_id": str(r.get("unit_id")),
                            "district": r.get("district"),
                            "current_price": round(cp, 2),
                            "predicted_price": round(pp, 2),
                            "price_gap": round(pg, 2),
                            "gap_rate": round(gr, 2),
                            "rating": round(float(r.get("rating") or 0), 1),
                            "reason": r.get("reason") or "",
                            "tags": r.get("tags"),
                            "data_source_note": "hive_ads_district_avg",
                        }
                    )
                    if len(out) >= limit:
                        break
                if out:
                    out = self._enrich_listing_titles(out)
                    logger.info(
                        "get_price_opportunities: source=hive_ads rows=%s", len(out)
                    )
                    return out

        return self._mysql_get_price_opportunities(min_gap_rate, limit)

    def _enrich_listing_titles(self, rows: List[Dict]) -> List[Dict]:
        uids = [r["unit_id"] for r in rows if r.get("unit_id")]
        if not uids:
            return rows
        db = SessionLocal()
        try:
            q = db.query(Listing.unit_id, Listing.title).filter(Listing.unit_id.in_(uids))
            title_map = {x.unit_id: x.title for x in q.all()}
            for r in rows:
                uid = r.get("unit_id")
                t = title_map.get(uid)
                r["title"] = t or f"房源{str(uid)[-4:]}"
            return rows
        finally:
            db.close()

    def _mysql_get_price_opportunities(
        self, min_gap_rate: float, limit: int
    ) -> List[Dict]:
        from statistics import median

        db = SessionLocal()
        try:
            listings_for_stats = (
                db.query(Listing.final_price, Listing.district)
                .filter(
                    Listing.final_price.isnot(None),
                    Listing.final_price >= 80,
                    Listing.final_price <= 500,
                )
                .all()
            )
            district_prices: Dict = {}
            for l in listings_for_stats:
                district_prices.setdefault(l.district, []).append(float(l.final_price))
            median_map = {
                d: median(prices)
                for d, prices in district_prices.items()
                if len(prices) >= 3
            }
            listings = (
                db.query(Listing)
                .filter(
                    Listing.final_price.isnot(None),
                    Listing.final_price >= 80,
                    Listing.final_price <= 500,
                    Listing.rating.isnot(None),
                )
                .order_by(Listing.final_price)
                .limit(500)
                .all()
            )
            opportunities = []
            for l in listings:
                if not is_eligible_price_opportunity_listing(l):
                    continue
                title = l.title or ""
                district = l.district
                current_price = float(l.final_price)
                predicted_price = median_map.get(district, current_price)
                if predicted_price > current_price and predicted_price <= 350:
                    gap = predicted_price - current_price
                    gap_rate = (gap / current_price * 100) if current_price > 0 else 0
                    if gap_rate >= min_gap_rate:
                        potential_monthly_gain = gap * 20
                        estimated_annual_roi = (
                            (potential_monthly_gain * 12)
                            / (current_price * 20 * 12 + 1)
                            * 100
                            if current_price > 0
                            else 0
                        )
                        investment_score = min(100, max(0, int(50 + gap_rate)))
                        opportunities.append(
                            {
                                "unit_id": l.unit_id,
                                "title": title or f"房源{l.unit_id[-4:]}",
                                "district": district,
                                "current_price": round(current_price, 2),
                                "predicted_price": round(predicted_price, 2),
                                "price_gap": round(gap, 2),
                                "gap_rate": round(gap_rate, 2),
                                "rating": round(float(l.rating or 0), 1),
                                "estimated_annual_roi": round(estimated_annual_roi, 2),
                                "investment_score": investment_score,
                                "reason": f"低于商圈中位价{round(gap, 0)}元",
                                "data_source_note": "mysql_district_median",
                            }
                        )
            logger.info(
                "get_price_opportunities: source=mysql rows=%s", len(opportunities)
            )
            return sorted(opportunities, key=lambda x: x["gap_rate"], reverse=True)[
                :limit
            ]
        finally:
            db.close()

    # ---------- ROI 排行（ADS）----------
    def get_roi_ranking(self, limit: int = 50) -> List[Dict]:
        if self._hive_enabled():
            sql = f"""
            SELECT district, avg_price, estimated_monthly_revenue, estimated_occupancy,
                   estimated_roi, investment_score, risk_level, recommendation
            FROM ads_roi_ranking
            WHERE dt = (SELECT MAX(dt) FROM ads_roi_ranking)
            ORDER BY estimated_roi DESC
            LIMIT {int(limit)}
            """
            df = _hive_analytics_query(sql)
            if df is not None and not df.empty:
                rows = _hive_df_to_records(df)
                rankings = []
                for r in rows:
                    er = float(r.get("estimated_roi") or 0)
                    inv = int(r.get("investment_score") or 0)
                    occ = float(r.get("estimated_occupancy") or 0)
                    rankings.append(
                        {
                            "district": r.get("district"),
                            "roi_score": inv,
                            "avg_price": round(float(r.get("avg_price") or 0), 2),
                            "occupancy_rate": round(occ, 1),
                            "recommendation": r.get("recommendation") or "",
                            "estimated_monthly_revenue": round(
                                float(r.get("estimated_monthly_revenue") or 0), 2
                            ),
                            "estimated_roi": round(er, 1),
                            "investment_score": inv,
                            "risk_level": r.get("risk_level") or "",
                            "data_source_note": "hive_ads_roi",
                        }
                    )
                logger.info("get_roi_ranking: source=hive_ads rows=%s", len(rankings))
                return rankings

        return self._mysql_get_roi_ranking(limit)

    def _mysql_get_roi_ranking(self, limit: int) -> List[Dict]:
        from app.services.district_ranking_service import build_mysql_district_roi_rankings

        db = SessionLocal()
        try:
            rankings = build_mysql_district_roi_rankings(db, limit=limit)
            logger.info("get_roi_ranking: source=mysql rows=%s", len(rankings))
            return rankings
        finally:
            db.close()

    # ---------- 价格分布（DWS）----------
    def get_price_distribution(self, district: Optional[str] = None) -> List[Dict]:
        if self._hive_enabled():
            dfilter = ""
            if district:
                dfilter = f" AND district = '{_sql_escape(district)}' "
            sql = f"""
            SELECT district, price_range, listing_count, percentage
            FROM dws_price_distribution
            WHERE dt = (SELECT MAX(dt) FROM dws_price_distribution)
            {dfilter}
            ORDER BY price_range
            """
            df = _hive_analytics_query(sql)
            if df is not None and not df.empty:
                rows = _hive_df_to_records(df)
                out = [
                    {
                        "price_range": r.get("price_range"),
                        "district": r.get("district"),
                        "listing_count": int(r.get("listing_count") or 0),
                        "percentage": round(float(r.get("percentage") or 0), 2),
                    }
                    for r in rows
                ]
                logger.info(
                    "get_price_distribution: source=hive_dws rows=%s district=%s",
                    len(out),
                    district,
                )
                return out

        return self._mysql_get_price_distribution(district)

    def _mysql_get_price_distribution(self, district: Optional[str]) -> List[Dict]:
        db = SessionLocal()
        try:
            query = db.query(Listing).filter(Listing.final_price.isnot(None))
            if district:
                query = query.filter(Listing.district == district)
            listings = query.all()
            ranges = [
                (0, 100, "0-100元"),
                (100, 200, "100-200元"),
                (200, 300, "200-300元"),
                (300, 500, "300-500元"),
                (500, 1000, "500-1000元"),
                (1000, float("inf"), "1000元以上"),
            ]
            distribution = []
            total = len(listings)
            for low, high, label in ranges:
                count = sum(
                    1 for l in listings if low <= float(l.final_price or 0) < high
                )
                distribution.append(
                    {
                        "price_range": label,
                        "listing_count": count,
                        "percentage": round(count / total * 100, 2) if total > 0 else 0,
                    }
                )
            logger.info(
                "get_price_distribution: source=mysql rows=%s", len(distribution)
            )
            return distribution
        finally:
            db.close()

    # ---------- 行级：仅 MySQL ----------
    def get_listings_by_district(self, district: str, limit: int = 100) -> List[Dict]:
        db = SessionLocal()
        try:
            listings = (
                db.query(Listing)
                .filter(Listing.district == district)
                .order_by(Listing.favorite_count.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "unit_id": l.unit_id,
                    "title": l.title or f"房源{l.unit_id[-4:]}",
                    "district": l.district,
                    "trade_area": l.trade_area or "",
                    "price": float(l.final_price or 0),
                    "rating": float(l.rating or 0),
                    "comment_count": int(l.comment_brief.count("，") + 1)
                    if l.comment_brief
                    else 0,
                    "bedroom_count": l.bedroom_count or 1,
                    "area_sqm": l.area or 50,
                    "heat_score": int(l.favorite_count or 0),
                    "facility_count": len((l.house_tags or "").split(","))
                    if l.house_tags
                    else 0,
                    "house_tags": l.house_tags or "",
                }
                for l in listings
            ]
        finally:
            db.close()

    def get_listing_detail(self, unit_id: str) -> Optional[Dict]:
        db = SessionLocal()
        try:
            l = db.query(Listing).filter(Listing.unit_id == unit_id).first()
            if not l:
                return None
            _nh_name_raw = getattr(l, "nearest_hospital_name", None)
            _nh_name = (
                str(_nh_name_raw).strip() if _nh_name_raw is not None else ""
            )
            return {
                "unit_id": l.unit_id,
                "title": l.title or f"房源{unit_id[-4:]}",
                "district": l.district,
                "price": float(l.final_price or 0),
                "rating": float(l.rating or 0),
                "comment_count": int(l.comment_brief.count("，") + 1)
                if l.comment_brief
                else 0,
                "bedroom_count": l.bedroom_count or 1,
                "bathroom_count": 1,
                "area_sqm": l.area or 50,
                "heat_score": int(l.favorite_count or 0),
                "facility_count": len((l.house_tags or "").split(","))
                if l.house_tags
                else 0,
                "has_projector": 1 if l.house_tags and "投影" in l.house_tags else 0,
                "has_kitchen": 1 if l.house_tags and "厨房" in l.house_tags else 0,
                "has_bathtub": 1 if l.house_tags and "浴缸" in l.house_tags else 0,
                "cover_image": l.cover_image,
                "nearest_hospital_km": float(l.nearest_hospital_km)
                if getattr(l, "nearest_hospital_km", None) is not None
                else None,
                "nearest_hospital_name": _nh_name or None,
            }
        finally:
            db.close()

    def get_similar_listings(self, unit_id: str, limit: int = 5) -> List[Dict]:
        db = SessionLocal()
        try:
            target = db.query(Listing).filter(Listing.unit_id == unit_id).first()
            if not target:
                return []
            similar = (
                db.query(Listing)
                .filter(
                    Listing.district == target.district, Listing.unit_id != unit_id
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "unit_id": l.unit_id,
                    "district": l.district,
                    "price": float(l.final_price or 0),
                    "rating": float(l.rating or 0),
                    "bedroom_count": l.bedroom_count or 1,
                    "area_sqm": l.area or 50,
                }
                for l in similar
            ]
        finally:
            db.close()


hive_service = HiveDataService()

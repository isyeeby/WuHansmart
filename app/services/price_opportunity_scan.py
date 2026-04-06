"""
价格洼地扫描：日级 XGBoost 参考价 + 行政区中位数兜底。

供 /api/analysis/price-opportunities 与 /api/investment/opportunities 共用，避免双口径。
"""
from __future__ import annotations

import logging
from statistics import median
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.api.endpoints.predict import _daily_base_price_optional
from app.services.listing_price_bridge import listing_to_prediction_request
from app.services.price_opportunity_filters import is_eligible_price_opportunity_listing

logger = logging.getLogger(__name__)

MAX_PRICE_OPPORTUNITY_MODEL_CALLS = 120


def price_opportunities_methodology() -> Dict[str, Any]:
    return {
        "gap_formula": "(参考估算价 − 当前挂牌价) ÷ 当前挂牌价 × 100%",
        "reference_price": (
            "优先日级 XGBoost 锚定价（与智能定价同源）；失败时为同行政区 eligible 房源"
            "挂牌价中位数（每区样本≥3）。"
        ),
        "model_call_cap": MAX_PRICE_OPPORTUNITY_MODEL_CALLS,
        "eligibility_note": (
            "排除规则见 is_eligible_price_opportunity_listing（共享住宿/床位等关键词及可比价格带）。"
        ),
    }


def compute_price_opportunities(
    db: Session,
    min_gap_rate: float,
    limit: int,
) -> List[Dict[str, Any]]:
    from app.db.database import Listing

    listings_raw = (
        db.query(Listing)
        .filter(Listing.final_price > 0, Listing.rating > 0)
        .all()
    )

    listings = [row for row in listings_raw if is_eligible_price_opportunity_listing(row)]

    if not listings:
        return []

    by_district: Dict[str, List[float]] = {}
    for row in listings:
        d = row.district
        if not d:
            continue
        by_district.setdefault(d, []).append(float(row.final_price))

    district_median: Dict[str, float] = {}
    for d, prices in by_district.items():
        if len(prices) >= 3:
            district_median[d] = float(median(prices))

    scored = []
    for row in listings:
        cp = float(row.final_price or 0)
        d = row.district
        med = district_median.get(d)
        if med and med > 0 and cp < med:
            scored.append((row, (med - cp) / med))
    scored.sort(key=lambda x: x[1], reverse=True)
    candidates = [x[0] for x in scored[:MAX_PRICE_OPPORTUNITY_MODEL_CALLS]]
    if len(candidates) < MAX_PRICE_OPPORTUNITY_MODEL_CALLS // 2:
        seen = {id(x) for x in candidates}
        rest = sorted(
            [l for l in listings if id(l) not in seen],
            key=lambda l: (-float(l.rating or 0), float(l.final_price or 0)),
        )
        for row in rest:
            candidates.append(row)
            if len(candidates) >= MAX_PRICE_OPPORTUNITY_MODEL_CALLS:
                break

    opportunities: List[Dict[str, Any]] = []
    for listing in candidates:
        current_price = float(listing.final_price or 0)
        district = listing.district
        rating = float(listing.rating or 0)

        prediction_source = "district_median"
        predicted_price = None
        try:
            pred_req = listing_to_prediction_request(listing)
            dp = _daily_base_price_optional(pred_req)
            if dp is not None and dp > 0:
                predicted_price = dp
                prediction_source = "xgboost_daily"
        except Exception as e:
            logger.warning(
                "price-opportunities predict failed for %s: %s", listing.unit_id, e
            )
            predicted_price = None

        if predicted_price is None or predicted_price <= 0:
            med = district_median.get(district)
            if not med or med <= 0:
                continue
            predicted_price = float(med)
            prediction_source = "district_median"

        gap_rate = (
            (predicted_price - current_price) / current_price * 100
            if current_price > 0
            else 0.0
        )
        if gap_rate >= min_gap_rate:
            price_gap = round(float(predicted_price) - current_price, 2)
            opportunities.append(
                {
                    "unit_id": listing.unit_id,
                    "title": listing.title,
                    "district": district,
                    "current_price": current_price,
                    "predicted_price": round(float(predicted_price), 2),
                    "price_gap": price_gap,
                    "gap_rate": round(gap_rate, 1),
                    "rating": rating,
                    "prediction_source": prediction_source,
                }
            )

    opportunities.sort(key=lambda x: x["gap_rate"], reverse=True)
    return opportunities[:limit]

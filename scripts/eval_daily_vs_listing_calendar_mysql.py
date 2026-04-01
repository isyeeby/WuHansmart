# -*- coding: utf-8 -*-
"""
离线对比：日级 XGB（14 天曲线） vs 真实 price_calendars；
         房源级 XGB（单点） vs listings.final_price。

输入特征与智能定价一致：由 listing 字段 + 标签解析构造 PredictionRequest，
不传 unit_id、不把房价当模型输入（final_price 仅作真值对照）。

用法（在 Tujia-backend 目录）:
  python scripts/eval_daily_vs_listing_calendar_mysql.py
  python scripts/eval_daily_vs_listing_calendar_mysql.py --limit 200 --max-units 60
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Listing, PriceCalendar, SessionLocal
from app.services.daily_price_service import daily_forecast_service
from app.services.listing_price_bridge import listing_to_prediction_request
from app.services.price_predictor import model_service


def _parse_cal_date(s: str) -> Optional[date]:
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def load_calendar_by_unit(limit_listings: int) -> Tuple[Dict[str, Dict[str, float]], List[Listing]]:
    db = SessionLocal()
    try:
        q = (
            db.query(Listing)
            .filter(
                Listing.final_price.isnot(None),
                Listing.final_price > 0,
                Listing.rating.isnot(None),
                Listing.area.isnot(None),
                Listing.district.isnot(None),
            )
        )
        if limit_listings > 0:
            q = q.limit(limit_listings)
        listings = q.all()
        uids = [l.unit_id for l in listings if l.unit_id]
        cal_map: Dict[str, Dict[str, float]] = defaultdict(dict)
        chunk = 400
        for i in range(0, len(uids), chunk):
            batch = uids[i : i + chunk]
            rows = db.query(PriceCalendar).filter(PriceCalendar.unit_id.in_(batch)).all()
            for r in rows:
                if r.price is None:
                    continue
                p = float(r.price)
                if p < 50 or p > 5000:
                    continue
                cal_map[str(r.unit_id)][str(r.date)] = p
        return dict(cal_map), listings
    finally:
        db.close()


def find_anchor_14(pdates: Set[date]) -> Optional[date]:
    for d in sorted(pdates):
        if all((d + timedelta(days=k)) in pdates for k in range(14)):
            return d
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400, help="从 listings 取样的最大条数（0=不限）")
    ap.add_argument("--max-units", type=int, default=80, help="最多评估多少套有连续14日历天的房源")
    args = ap.parse_args()

    cal_map, listings = load_calendar_by_unit(args.limit)
    print("=" * 60)
    print("日级 vs 日历真值 & 房源级 vs final_price（MySQL）")
    print("=" * 60)
    print(f"候选房源数: {len(listings)} | 有日历记录的 unit 数: {len(cal_map)}")

    daily_ok = daily_forecast_service.available()
    if not daily_ok:
        print("警告: 日级模型不可用（缺 xgboost_price_daily_model.pkl 或 feature_names_daily.json），跳过日级对比。")

    listing_preds: List[float] = []
    listing_actuals: List[float] = []
    daily_pairs: List[Tuple[float, float]] = []
    per_horizon: Dict[int, List[Tuple[float, float]]] = defaultdict(list)
    samples_shown = 0
    used = 0

    for listing in listings:
        if used >= args.max_units:
            break
        uid = str(listing.unit_id)
        cmap = cal_map.get(uid)
        if not cmap:
            continue
        dset: Set[date] = set()
        for ds, pv in cmap.items():
            dd = _parse_cal_date(ds)
            if dd is not None:
                dset.add(dd)
        anchor_d = find_anchor_14(dset)
        if anchor_d is None:
            continue

        try:
            req = listing_to_prediction_request(listing)
        except Exception as e:
            print(f"跳过 unit {uid}: 构造请求失败 {e}")
            continue

        actual_fp = float(listing.final_price)
        if actual_fp < 50 or actual_fp > 5000:
            continue

        try:
            lp = float(model_service.predict(req))
        except Exception as e:
            print(f"跳过 unit {uid}: 房源级预测失败 {e}")
            continue
        listing_preds.append(lp)
        listing_actuals.append(actual_fp)

        if daily_ok:
            anchor_dt = datetime(anchor_d.year, anchor_d.month, anchor_d.day)
            out = daily_forecast_service.predict_forecast_14(req, n_days=14, anchor=anchor_dt)
            if out and out.get("forecasts"):
                for f in out["forecasts"]:
                    ds = f["date"]
                    act = cmap.get(ds)
                    if act is None:
                        continue
                    pred = float(f["predicted_price"])
                    daily_pairs.append((pred, act))
                    per_horizon[int(f.get("horizon_day", 0))].append((pred, act))

        used += 1
        if samples_shown < 5:
            print(
                f"\n样例 {samples_shown + 1} | unit={uid[:8]}… | 区={req.district} | "
                f"anchor={anchor_d} | final_price={actual_fp:.0f} | 房源级预测={lp:.0f}"
            )
            if daily_ok and daily_pairs:
                last_pairs = daily_pairs[-14:] if len(daily_pairs) >= 14 else daily_pairs
                if len(last_pairs) >= 3:
                    print("  日级(最近若干天): 预测->真实 ", end="")
                    print(
                        ", ".join(f"{p:.0f}->{a:.0f}" for p, a in last_pairs[-5:]),
                    )
            samples_shown += 1

    def _mae_mape(y_t: np.ndarray, y_p: np.ndarray) -> Tuple[float, float]:
        mae = float(np.mean(np.abs(y_p - y_t)))
        mape = float(np.mean(np.abs(y_p - y_t) / np.clip(y_t, 1e-6, None)) * 100)
        return mae, mape

    print("\n" + "=" * 60)
    print(f"有效样本: {used} 套房源（每套含连续 14 天日历价，用于日级对齐）")
    print("=" * 60)

    if listing_preds:
        yt = np.array(listing_actuals, dtype=float)
        yp = np.array(listing_preds, dtype=float)
        mae, mape = _mae_mape(yt, yp)
        ss_res = float(np.sum((yt - yp) ** 2))
        ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        print("\n【房源级 XGB】预测 vs final_price（挂牌/成交价，单点）")
        print(f"  MAE:  {mae:.2f} 元")
        print(f"  MAPE: {mape:.1f}%")
        print(f"  R²:   {r2:.4f}")
    else:
        print("\n【房源级】无有效样本")

    if daily_ok and daily_pairs:
        yt = np.array([a for _, a in daily_pairs], dtype=float)
        yp = np.array([p for p, _ in daily_pairs], dtype=float)
        mae, mape = _mae_mape(yt, yp)
        print("\n【日级 XGB】14 天内每日预测 vs 当日 price_calendars 真实价（行级）")
        print(f"  对齐行数: {len(daily_pairs)}（最多 {used * 14}）")
        print(f"  MAE:  {mae:.2f} 元")
        print(f"  MAPE: {mape:.1f}%")
        print("  按 horizon_day 分桶 MAE（元）:")
        for h in sorted(per_horizon.keys()):
            pairs = per_horizon[h]
            if not pairs:
                continue
            t = np.array([a for _, a in pairs])
            p = np.array([x for x, _ in pairs])
            mh = float(np.mean(np.abs(p - t)))
            print(f"    day+{h}: n={len(pairs):4d}  MAE={mh:.2f}")
    elif daily_ok:
        print("\n【日级】无对齐样本（检查日历是否覆盖 anchor..anchor+13）")
    else:
        print("\n【日级】未加载模型，未评估")

    print(
        "\n说明: 日级评估的是「历史某连续14天的日历挂牌价」与模型曲线；"
        "房源级评估的是「final_price」单点。二者真值定义不同，MAE 不宜直接比大小。"
    )


if __name__ == "__main__":
    main()

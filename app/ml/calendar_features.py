# -*- coding: utf-8 -*-
"""
价格日历聚合特征（离线训练 / 批量造表用）。

从 price_calendars 表按 unit_id 聚合，刻画动态定价水平、波动与周末溢价等，
与 listings.final_price 互补。定价 HTTP 接口不查库；线上日历维由
calendar_feature_defaults.json 填充，与训练主评估口径一致。
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db.database import PriceCalendar

# 与训练脚本、model_manager、feature_names_latest 保持列名一致
CALENDAR_FEATURE_NAMES: List[str] = [
    "cal_n_days",
    "cal_mean",
    "cal_std",
    "cal_min",
    "cal_max",
    "cal_median",
    "cal_cv",
    "cal_range_ratio",
    "cal_bookable_ratio",
    "cal_weekend_premium",
]


def _calendar_rows_to_dataframe(rows: List[PriceCalendar]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["unit_id", "date", "price", "can_booking"]
        )
    data = [
        (
            r.unit_id,
            r.date,
            float(r.price),
            float(r.can_booking if r.can_booking is not None else 1),
        )
        for r in rows
    ]
    return pd.DataFrame(data, columns=["unit_id", "date", "price", "can_booking"])


def aggregate_calendar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    将日频日历表聚合为每个 unit_id 一行特征。
    要求列：unit_id, date, price, can_booking（与 ORM 导出一致）。
    周末定义：周六、周日（dayofweek 5、6）。
    """
    if df.empty:
        return pd.DataFrame(columns=["unit_id"] + CALENDAR_FEATURE_NAMES)

    work = df.copy()
    work["unit_id"] = work["unit_id"].astype(str)
    work["dt"] = pd.to_datetime(work["date"], errors="coerce")
    work["is_weekend"] = work["dt"].dt.dayofweek.isin([5, 6])

    g = work.groupby("unit_id", sort=False)
    base = g.agg(
        cal_n_days=("price", "count"),
        cal_mean=("price", "mean"),
        cal_std=("price", "std"),
        cal_min=("price", "min"),
        cal_max=("price", "max"),
        cal_median=("price", "median"),
        cal_bookable_ratio=("can_booking", "mean"),
    ).reset_index()

    base["cal_std"] = base["cal_std"].fillna(0.0)

    eps = 1e-6
    base["cal_cv"] = base["cal_std"] / (base["cal_mean"].abs() + eps)
    base["cal_range_ratio"] = (base["cal_max"] - base["cal_min"]) / (
        base["cal_mean"].abs() + eps
    )

    w_end = work[work["is_weekend"]].groupby("unit_id")["price"].mean()
    w_day = work[~work["is_weekend"]].groupby("unit_id")["price"].mean()
    merged = pd.DataFrame({"unit_id": base["unit_id"]})
    merged = merged.merge(
        w_end.rename("we"), left_on="unit_id", right_index=True, how="left"
    )
    merged = merged.merge(
        w_day.rename("wd"), left_on="unit_id", right_index=True, how="left"
    )
    base["cal_weekend_premium"] = (
        (merged["we"] / (merged["wd"] + eps) - 1.0).fillna(0.0).astype(float).values
    )

    for c in CALENDAR_FEATURE_NAMES:
        if c not in base.columns:
            base[c] = 0.0
    return base[["unit_id"] + CALENDAR_FEATURE_NAMES]


def filter_out_all_zero_price_calendar_units(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    剔除「有日历行但所有日价格均为 0（或非正）」的房源，避免 cal_n_days>0 却无有效价污染训练。

    条件：cal_n_days > 0 且 cal_max 有效且 cal_max <= 0。
    无日历（cal_n_days 为 0/NaN）或未合并日历列的样本保留不动。
    """
    if df.empty or "cal_n_days" not in df.columns or "cal_max" not in df.columns:
        return df, 0
    nd = pd.to_numeric(df["cal_n_days"], errors="coerce").fillna(0)
    cm = pd.to_numeric(df["cal_max"], errors="coerce")
    bad = (nd > 0) & cm.notna() & (cm <= 0)
    n = int(bad.sum())
    if n == 0:
        return df, 0
    return df.loc[~bad].reset_index(drop=True), n


def aggregate_calendar_by_units_from_rows(
    rows: List[PriceCalendar],
) -> pd.DataFrame:
    """
    将 ORM 行聚合为每个 unit_id 一行日历特征。
    周末定义：周六、周日（pandas dayofweek 5、6）。
    """
    df = _calendar_rows_to_dataframe(rows)
    return aggregate_calendar_dataframe(df)


def load_calendar_aggregates_for_unit_ids(
    db: Session, unit_ids: Sequence[str], chunk_size: int = 800
) -> pd.DataFrame:
    """批量查询 unit_id 列表对应的全部日历行并聚合（避免 IN 过长）。"""
    ids = [str(u) for u in unit_ids if u]
    if not ids:
        return pd.DataFrame(columns=["unit_id"] + CALENDAR_FEATURE_NAMES)

    all_rows: List[PriceCalendar] = []
    for i in range(0, len(ids), chunk_size):
        batch = ids[i : i + chunk_size]
        q = db.query(PriceCalendar).filter(PriceCalendar.unit_id.in_(batch))
        all_rows.extend(q.all())

    return aggregate_calendar_by_units_from_rows(all_rows)


def calendar_feature_dict_for_unit(
    db: Session, unit_id: str
) -> Dict[str, float]:
    """
    从数据库拉单套日历并返回特征字典（键与 CALENDAR_FEATURE_NAMES 一致）。
    仅供离线脚本或分析使用；XGBoost 定价 API 路径不应调用。
    """
    rows = db.query(PriceCalendar).filter(PriceCalendar.unit_id == unit_id).all()
    agg = aggregate_calendar_by_units_from_rows(rows)
    if agg.empty:
        return {k: 0.0 for k in CALENDAR_FEATURE_NAMES}
    row = agg.iloc[0]
    return {k: float(row[k]) for k in CALENDAR_FEATURE_NAMES}


def train_median_defaults(
    train_df: pd.DataFrame, cal_cols: List[str]
) -> Dict[str, float]:
    """
    仅用训练集、且 cal_n_days>0 的样本估计日历特征中位数，供无日历样本与线上默认填充。
    """
    sub = train_df[train_df["cal_n_days"] > 0]
    out: Dict[str, float] = {}
    if sub.empty:
        for c in cal_cols:
            out[c] = 0.0
        return out
    for c in cal_cols:
        m = sub[c].median()
        out[c] = float(0.0 if pd.isna(m) else m)
    return out


def impute_calendar_train_test(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    """
    划分之后：对无日历房源用「训练集中有日历样本」的中位数填充除 cal_n_days 外的日历列；
    cal_n_days 保持 0。返回 api_defaults：线上无 unit_id 时采用 cal_n_days=0 + 其余为中位数。
    """
    names = CALENDAR_FEATURE_NAMES
    tr = train_df.copy()
    te = test_df.copy()
    for n in names:
        if n not in tr.columns:
            tr[n] = np.nan
        if n not in te.columns:
            te[n] = np.nan
    tr["cal_n_days"] = tr["cal_n_days"].fillna(0)
    te["cal_n_days"] = te["cal_n_days"].fillna(0)

    med = train_median_defaults(tr, names)
    for n in names:
        if n == "cal_n_days":
            continue
        mval = med[n]
        tr.loc[tr["cal_n_days"] <= 0, n] = tr.loc[tr["cal_n_days"] <= 0, n].fillna(mval)
        te.loc[te["cal_n_days"] <= 0, n] = te.loc[te["cal_n_days"] <= 0, n].fillna(mval)

    sub = tr[tr["cal_n_days"] > 0]
    if len(sub) > 0:
        for n in names:
            if n == "cal_n_days":
                continue
            col_med = sub[n].median()
            if pd.notna(col_med):
                fv = float(col_med)
                tr.loc[tr["cal_n_days"] > 0, n] = tr.loc[tr["cal_n_days"] > 0, n].fillna(fv)
                te.loc[te["cal_n_days"] > 0, n] = te.loc[te["cal_n_days"] > 0, n].fillna(fv)

    api_defaults = {**med}
    api_defaults["cal_n_days"] = 0.0
    return tr, te, api_defaults

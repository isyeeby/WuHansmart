# -*- coding: utf-8 -*-
"""
日级定价：日期与中国节假日相关特征（与「静态 + 日期 -> 日价」任务对齐）。

- cal_offset_days：该房源在**当前库内日历**中相对首日的偏移天数，与线上「从锚点起未来第 k 天」一致（锚点=首日时 k=offset）。
- cal_days_before_holiday / cal_days_after_holiday：距下一次/上一次法定节假日（含周末调休假）的天数，上限 cap 外记为 cap+1。

依赖：建议安装 chinesecalendar；未安装时节假日距离为哨兵值，is_holiday/is_workday 等退化。
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd

try:
    import chinesecalendar as _cn_cal  # type: ignore
except ImportError:
    _cn_cal = None

# 与训练脚本 feature_cols 对齐（前缀 cal_）
DATE_FEATURE_COLUMNS: List[str] = [
    "cal_year",
    "cal_month",
    "cal_day",
    "cal_dow",
    "cal_is_weekend",
    "cal_week_of_year",
    "cal_day_of_month",
    "cal_season",
    "cal_is_holiday",
    "cal_is_workday",
    "cal_is_makeup_workday",
    "cal_offset_days",
    "cal_days_before_holiday",
    "cal_days_after_holiday",
]

LAG_FEATURE_COLUMNS = ["lag1_price", "roll7_prior_mean"]


def _cn_flags_for_date(d: date) -> Tuple[int, int, int]:
    """返回 (is_holiday, is_workday, is_makeup_workday)。"""
    if _cn_cal is None:
        wd = d.weekday()
        is_wd = 1 if wd < 5 else 0
        return 0, is_wd, 0
    try:
        is_h = 1 if _cn_cal.is_holiday(d) else 0
        is_wk = 1 if _cn_cal.is_workday(d) else 0
        is_makeup = 1 if (is_wk == 1 and d.weekday() >= 5) else 0
        return is_h, is_wk, is_makeup
    except Exception:
        wd = d.weekday()
        return 0, (1 if wd < 5 else 0), 0


def _collect_sorted_holidays(d0: date, d1: date) -> List[date]:
    if _cn_cal is None:
        return []
    out: List[date] = []
    d = d0
    while d <= d1:
        try:
            if _cn_cal.is_holiday(d):
                out.append(d)
        except Exception:
            pass
        d += timedelta(days=1)
    return sorted(set(out))


def add_unit_calendar_offset(
    df: pd.DataFrame, unit_col: str = "unit_id", date_col: str = "calendar_date"
) -> pd.DataFrame:
    """每个 unit 以库内最早日历日为 0，与「从首日起第 k 天」推理口径一致。"""
    out = df.copy()
    dt = pd.to_datetime(out[date_col], errors="coerce")
    grp_min = dt.groupby(out[unit_col]).transform("min")
    out["cal_offset_days"] = (dt - grp_min).dt.total_seconds() / 86400.0
    return out


def add_holiday_proximity_features(
    df: pd.DataFrame,
    date_col: str = "calendar_date",
    max_span: int = 60,
) -> pd.DataFrame:
    """
    距下一法定节假日天数 / 距上一法定节假日天数；无节假日库时两列均为 max_span+1。
    对 date_col 去重后查表再映射，避免对几十万行逐行扫节假。
    """
    out = df.copy()
    dt = pd.to_datetime(out[date_col], errors="coerce")
    dmin = dt.min()
    dmax = dt.max()
    if pd.isna(dmin) or pd.isna(dmax):
        out["cal_days_before_holiday"] = float(max_span + 1)
        out["cal_days_after_holiday"] = float(max_span + 1)
        return out

    d0 = dmin.date() - timedelta(days=max_span)
    d1 = dmax.date() + timedelta(days=max_span)
    hol_sorted = _collect_sorted_holidays(d0, d1)
    sentinel = float(max_span + 1)

    def before_next(d: date) -> float:
        if not hol_sorted:
            return sentinel
        i = bisect_left(hol_sorted, d)
        if i < len(hol_sorted):
            gap = (hol_sorted[i] - d).days
            return float(min(gap, max_span + 1))
        return sentinel

    def after_prev(d: date) -> float:
        if not hol_sorted:
            return sentinel
        i = bisect_right(hol_sorted, d) - 1
        if i >= 0:
            gap = (d - hol_sorted[i]).days
            return float(min(gap, max_span + 1))
        return sentinel

    uniq_dates = pd.Series(dt.dt.date.unique()).dropna()
    b_map = {d: before_next(d) for d in uniq_dates}
    a_map = {d: after_prev(d) for d in uniq_dates}
    day_series = dt.dt.date
    out["cal_days_before_holiday"] = (
        day_series.map(lambda x: b_map.get(x, sentinel) if pd.notna(x) else sentinel).astype(float)
    )
    out["cal_days_after_holiday"] = (
        day_series.map(lambda x: a_map.get(x, sentinel) if pd.notna(x) else sentinel).astype(float)
    )
    return out


def add_daily_date_features(df: pd.DataFrame, date_col: str = "calendar_date") -> pd.DataFrame:
    """年/月/日/周/季节/中国节假日与工作态等（不含 offset 与节前节后距离，由另函数添加）。"""
    out = df.copy()
    dt = pd.to_datetime(out[date_col], errors="coerce")
    out["cal_year"] = dt.dt.year.astype(float)
    out["cal_month"] = dt.dt.month.astype(float)
    out["cal_day"] = dt.dt.day.astype(float)
    out["cal_dow"] = dt.dt.dayofweek.astype(float)
    out["cal_is_weekend"] = dt.dt.dayofweek.isin([5, 6]).astype(int)
    iso = dt.dt.isocalendar()
    out["cal_week_of_year"] = iso["week"].astype(float)
    out["cal_day_of_month"] = out["cal_day"]
    m = dt.dt.month.astype(float)
    out["cal_season"] = np.where(m.isna(), np.nan, ((m - 1) // 3 + 1).clip(1, 4))

    n = len(out)
    hol = np.zeros(n, dtype=np.int8)
    wk = np.zeros(n, dtype=np.int8)
    mk = np.zeros(n, dtype=np.int8)
    valid = dt.notna()
    idxs = np.where(valid.to_numpy())[0]
    for i in idxs:
        d = dt.iloc[i].date()
        h, w, m_ = _cn_flags_for_date(d)
        hol[i], wk[i], mk[i] = h, w, m_
    out["cal_is_holiday"] = hol
    out["cal_is_workday"] = wk
    out["cal_is_makeup_workday"] = mk
    return out


def add_prior_price_lags(
    df: pd.DataFrame,
    unit_col: str = "unit_id",
    date_col: str = "calendar_date",
    price_col: str = "price",
) -> pd.DataFrame:
    """可选：前一日价、前 7 日（不含当日）均价；仅用于与主任务对比，非默认。"""
    out = df.copy()
    out = out.sort_values([unit_col, date_col], kind="mergesort")
    g = out.groupby(unit_col, sort=False)[price_col]
    out["lag1_price"] = g.shift(1)
    out["roll7_prior_mean"] = g.transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).mean()
    )
    return out

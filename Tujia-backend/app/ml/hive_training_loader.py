# -*- coding: utf-8 -*-
"""
训练用 Hive 数据加载（ODS 层）。

设计目标：
- 数仓规范下业务数据主存 Hive（ODS: ods_listings / ods_price_calendar）；
- 当 Hive 不可用（连接失败、表空）时，由 train_model_mysql 回退 MySQL。
- 支持两种连接：① impyla + execute_query_to_df；② Docker 内 hive CLI（HiveDockerService）。

说明：Hive 侧若仅做聚合而未按周末切分，cal_weekend_premium 置 0，与 MySQL 全量日历路径略有差异，
论文中可表述为「离线仓聚合口径」与「OLTP 明细口径」之区别。
"""
from __future__ import annotations

import logging
from typing import Tuple

import numpy as np
import pandas as pd

from app.ml.calendar_features import CALENDAR_FEATURE_NAMES

logger = logging.getLogger(__name__)

# ODS 房源（与 sql/hive_load_data.hql 中 ods_listings 对齐，列不足时在 Python 中补全）
HIVE_LISTINGS_SQL = """
SELECT
  unit_id,
  CAST(price AS DOUBLE) AS price,
  district,
  CAST(COALESCE(area_sqm, 50) AS DOUBLE) AS area,
  CAST(COALESCE(bedroom_count, 1) AS INT) AS bedroom_count,
  CAST(COALESCE(rating, 0) AS DOUBLE) AS rating,
  CAST(COALESCE(comment_count, 0) AS INT) AS comment_count,
  CAST(COALESCE(heat_score, 0) AS DOUBLE) AS heat_score,
  tags
FROM ods_listings
WHERE price IS NOT NULL
  AND CAST(price AS DOUBLE) > 0
"""

# 价格日历聚合（与训练特征 cal_* 对齐；周末溢价在仓内未算时由 Python 置 0）
HIVE_CALENDAR_AGG_SQL = """
SELECT
  unit_id,
  COUNT(1) AS cal_n_days,
  AVG(CAST(price AS DOUBLE)) AS cal_mean,
  stddev_pop(CAST(price AS DOUBLE)) AS cal_std,
  MIN(CAST(price AS DOUBLE)) AS cal_min,
  MAX(CAST(price AS DOUBLE)) AS cal_max,
  percentile_approx(CAST(price AS DOUBLE), 0.5) AS cal_median
FROM ods_price_calendar
GROUP BY unit_id
"""

# 部分 Hive 版本不支持 percentile_approx 时用均值代替中位数
HIVE_CALENDAR_AGG_SQL_FALLBACK = """
SELECT
  unit_id,
  COUNT(1) AS cal_n_days,
  AVG(CAST(price AS DOUBLE)) AS cal_mean,
  stddev_pop(CAST(price AS DOUBLE)) AS cal_std,
  MIN(CAST(price AS DOUBLE)) AS cal_min,
  MAX(CAST(price AS DOUBLE)) AS cal_max,
  AVG(CAST(price AS DOUBLE)) AS cal_median
FROM ods_price_calendar
GROUP BY unit_id
"""


def _finalize_calendar_agg(cal: pd.DataFrame) -> pd.DataFrame:
    if cal.empty:
        return cal
    cal = cal.copy()
    for c in ["cal_mean", "cal_std", "cal_min", "cal_max", "cal_median", "cal_n_days"]:
        if c not in cal.columns:
            cal[c] = np.nan
    cal["cal_n_days"] = pd.to_numeric(cal["cal_n_days"], errors="coerce").fillna(0)
    cal["cal_mean"] = pd.to_numeric(cal["cal_mean"], errors="coerce")
    cal["cal_std"] = pd.to_numeric(cal["cal_std"], errors="coerce").fillna(0)
    cal["cal_min"] = pd.to_numeric(cal["cal_min"], errors="coerce")
    cal["cal_max"] = pd.to_numeric(cal["cal_max"], errors="coerce")
    cal["cal_median"] = pd.to_numeric(cal["cal_median"], errors="coerce")
    cal["cal_median"] = cal["cal_median"].fillna(cal["cal_mean"])
    eps = 1e-6
    cal["cal_cv"] = cal["cal_std"] / (cal["cal_mean"].abs() + eps)
    cal["cal_range_ratio"] = (cal["cal_max"] - cal["cal_min"]) / (cal["cal_mean"].abs() + eps)
    cal["cal_bookable_ratio"] = 1.0
    cal["cal_weekend_premium"] = 0.0
    return cal[["unit_id"] + CALENDAR_FEATURE_NAMES]


def _try_impyla(sql: str) -> pd.DataFrame:
    try:
        from app.db.hive import IMPYLA_AVAILABLE, execute_query_to_df

        if not IMPYLA_AVAILABLE:
            return pd.DataFrame()
        df = execute_query_to_df(sql)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.warning("Hive impyla 查询失败: %s", e)
        return pd.DataFrame()


def _try_docker(sql: str) -> pd.DataFrame:
    try:
        from app.services.hive_docker_service import hive_docker_service

        if not hive_docker_service.check_connection():
            return pd.DataFrame()
        df = hive_docker_service.run_query_dataframe(sql)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.warning("Hive Docker 查询失败: %s", e)
        return pd.DataFrame()


def fetch_hive_sql(sql: str) -> pd.DataFrame:
    """先 impyla，再 Docker。"""
    df = _try_impyla(sql)
    if not df.empty:
        return df
    return _try_docker(sql)


def fetch_hive_sql_tracked(sql: str) -> Tuple[pd.DataFrame, str]:
    """返回 (DataFrame, 'hive_impyla'|'hive_docker'|'none')。"""
    df = _try_impyla(sql)
    if not df.empty:
        return df, "hive_impyla"
    df = _try_docker(sql)
    if not df.empty:
        return df, "hive_docker"
    return pd.DataFrame(), "none"


def load_hive_listings_base() -> Tuple[pd.DataFrame, str]:
    """返回 (宽表, 连接方式)；宽表列与 MySQL 展开前语义一致。"""
    df, src = fetch_hive_sql_tracked(HIVE_LISTINGS_SQL)
    if df.empty:
        return df, src
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    if "unit_id" not in df.columns or "price" not in df.columns:
        logger.warning("Hive ods_listings 列不符合预期: %s", df.columns.tolist())
        return pd.DataFrame(), src
    out = pd.DataFrame(
        {
            "unit_id": df["unit_id"].astype(str),
            "price": pd.to_numeric(df["price"], errors="coerce"),
            "district": df["district"].fillna("").astype(str),
            "trade_area": df["district"].fillna("").astype(str),
            "rating": pd.to_numeric(df.get("rating", 0), errors="coerce").fillna(0),
            "area": pd.to_numeric(df.get("area", 50), errors="coerce").fillna(50),
            "bedroom_count": pd.to_numeric(df.get("bedroom_count", 1), errors="coerce").fillna(1).astype(int),
            "bed_count": pd.to_numeric(df.get("bedroom_count", 1), errors="coerce").fillna(1).astype(int),
            "capacity": (pd.to_numeric(df.get("bedroom_count", 1), errors="coerce").fillna(1) * 2)
            .astype(int)
            .clip(lower=1, upper=20),
            "favorite_count": pd.to_numeric(df.get("heat_score", 0), errors="coerce")
            .fillna(0)
            .astype(int),
            "house_type": "整套",
            "latitude": 0.0,
            "longitude": 0.0,
            "house_tags": df.get("tags", "").fillna("").astype(str),
        }
    )
    out = out.dropna(subset=["price"])
    out = out[out["price"] > 0]
    return out, src


def load_hive_calendar_agg(fetch_fn) -> pd.DataFrame:
    """
    fetch_fn: (sql: str) -> pd.DataFrame，与房源查询使用同一通道（impyla 或 Docker）。
    """
    for sql in (HIVE_CALENDAR_AGG_SQL, HIVE_CALENDAR_AGG_SQL_FALLBACK):
        df = fetch_fn(sql)
        if not df.empty:
            break
    if df.empty:
        return df
    df.columns = [str(c).lower().strip() for c in df.columns]
    if "unit_id" not in df.columns:
        return pd.DataFrame()
    df["unit_id"] = df["unit_id"].astype(str)
    return _finalize_calendar_agg(df)


def try_load_training_frame_from_hive(
    min_rows: int = 50,
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    从 Hive 拉取并合并日历聚合，返回与 train_model_mysql 中 MySQL 路径兼容的「展开前」基础表。
    调用方需再经 parse_house_tags + 设施列展开（与 MySQL 共用逻辑）。

    Returns:
        (df_base, note)  df_base 列为 unit_id, price, district, trade_area, rating, area,
        bedroom_count, bed_count, capacity, favorite_count, house_type, latitude, longitude, house_tags
        note: 'hive_impyla' | 'hive_docker' | 'hive_empty' | 'hive_small'
    """
    base, src = load_hive_listings_base()
    if base.empty or len(base) < min_rows:
        return None, "hive_empty" if base.empty else "hive_small"

    if src == "hive_impyla":
        fetch_fn = _try_impyla
    elif src == "hive_docker":
        fetch_fn = _try_docker
    else:
        fetch_fn = fetch_hive_sql

    cal = load_hive_calendar_agg(fetch_fn)

    if not cal.empty:
        base = base.merge(cal, on="unit_id", how="left")
    else:
        for c in CALENDAR_FEATURE_NAMES:
            base[c] = np.nan

    return base, src

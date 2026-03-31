# -*- coding: utf-8 -*-
"""
评论—入住转化率校正（实验性）

用于在「成交/入住量不可得」时，用评论数与分档转化率粗估「需求强度」类代理变量。

注意：
- 默认转化率字典仅为文献/行业常见区间的占位示意，未经本数据集实证标定；
- 标定前应通过问卷、小样本访谈或平台内可验证指标估计分层转化率后再写入 rates；
- 输出不宜在论文或产品中表述为「真实入住量」，应称为 estimated_visits / 校正后需求代理等。
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

import numpy as np
import pandas as pd

Tier = str  # "budget" | "standard" | "premium"

DEFAULT_CONVERSION_RATES: Dict[Tier, float] = {
    "budget": 0.15,
    "standard": 0.22,
    "premium": 0.10,
}


def estimate_real_visits(
    comment_count: float | int,
    *,
    listing_tier: Tier = "standard",
    rates: Optional[Mapping[Tier, float]] = None,
) -> float:
    """
    单条记录：用评论数与分档转化率估算「需求代理」尺度（非真实入住量）。

    comment_count <= 0 时返回 0，避免除零。
    """
    table = dict(rates) if rates is not None else dict(DEFAULT_CONVERSION_RATES)
    rate = float(table.get(listing_tier, table.get("standard", 0.2)))
    if rate <= 0:
        rate = 0.2
    cc = float(comment_count or 0)
    if cc <= 0:
        return 0.0
    return cc / rate


def assign_price_tier(prices: pd.Series) -> pd.Series:
    """
    按训练集价格 33%/66% 分位分三档，用于差异化转化率（与单价连续特征互补）。
    样本过少或分位失败时退化为全 standard。
    """
    s = pd.to_numeric(prices, errors="coerce")
    valid = s.dropna()
    if len(valid) < 3:
        return pd.Series("standard", index=s.index, dtype=object)

    q1 = float(valid.quantile(0.33))
    q2 = float(valid.quantile(0.66))

    def tier(p: float) -> str:
        if pd.isna(p):
            return "standard"
        if p <= q1:
            return "budget"
        if p >= q2:
            return "premium"
        return "standard"

    return s.map(tier)


def compute_estimated_visits_column(
    comment_count: pd.Series,
    final_price: pd.Series,
    *,
    rates: Optional[Mapping[Tier, float]] = None,
) -> pd.Series:
    """
    向量化计算 estimated_visits，与训练脚本 DataFrame 对齐。
    """
    table = dict(rates) if rates is not None else dict(DEFAULT_CONVERSION_RATES)
    default_r = float(table.get("standard", 0.22))
    tier = assign_price_tier(final_price)
    rate_s = tier.map(lambda t: float(table.get(str(t), default_r))).clip(lower=1e-6)
    cc = pd.to_numeric(comment_count, errors="coerce").fillna(0).clip(lower=0)
    out = np.where(cc.values <= 0, 0.0, cc.values / rate_s.values)
    return pd.Series(out, index=comment_count.index, dtype=float)

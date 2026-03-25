"""
根据 user_role、persona_answers 与偏好列生成用户画像摘要（规则模板，非 LLM）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _join_list(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return "、".join(str(x) for x in val if x)
    return str(val)


def _price_band_text(
    price_min: Optional[float],
    price_max: Optional[float],
) -> str:
    if price_min is None and price_max is None:
        return "不限"
    if price_min is not None and price_max is not None:
        return f"{int(price_min)}～{int(price_max)} 元/晚"
    if price_min is not None:
        return f"{int(price_min)} 元/晚以上"
    return f"约 {int(price_max)} 元/晚及以下"


def build_persona_summary(
    user_role: Optional[str],
    persona_answers: Optional[Dict[str, Any]],
    travel_purpose: Optional[str] = None,
    preferred_district: Optional[str] = None,
    preferred_price_min: Optional[float] = None,
    preferred_price_max: Optional[float] = None,
    required_facilities: Optional[List[str]] = None,
) -> str:
    answers = persona_answers or {}
    role = (user_role or "").strip().lower()

    if role == "operator":
        exp = answers.get("experience_level") or "未填写"
        scale = answers.get("listing_scale") or "未填写"
        focus = _join_list(answers.get("operator_focus")) or "未填写"
        city = answers.get("primary_city") or ""
        parts = [
            f"{exp}经验，当前运营规模：{scale}。",
            f"优先关注：{focus}。",
        ]
        if city:
            parts.append(f"房源主要区域：{city}。")
        channel = answers.get("acquisition_channel")
        if channel:
            parts.append(f"了解渠道：{channel}。")
        interests = _join_list(answers.get("content_interests"))
        if interests:
            parts.append(f"希望接收：{interests}。")
        return "".join(parts)

    if role == "investor":
        stage = answers.get("investment_stage") or "未填写"
        budget = answers.get("budget_tier") or "未填写"
        priorities = _join_list(answers.get("investor_priorities")) or "未填写"
        horizon = answers.get("hold_horizon") or "未填写"
        parts = [
            f"投资阶段：{stage}；预算区间：{budget}。",
            f"侧重：{priorities}；持有意向：{horizon}。",
        ]
        channel = answers.get("acquisition_channel")
        if channel:
            parts.append(f"了解渠道：{channel}。")
        interests = _join_list(answers.get("content_interests"))
        if interests:
            parts.append(f"希望接收：{interests}。")
        return "".join(parts)

    if role == "guest":
        purpose = travel_purpose or answers.get("travel_purpose") or "未填写"
        district = preferred_district or answers.get("primary_city") or "未填写"
        band = _price_band_text(
            float(preferred_price_min) if preferred_price_min is not None else None,
            float(preferred_price_max) if preferred_price_max is not None else None,
        )
        fac = required_facilities or answers.get("required_facilities") or []
        fac_str = _join_list(fac) if fac else "无特别要求"
        parts = [
            f"浏览参考时偏好「{purpose}」类房源场景，常参考价格带 {band}，关注区域 {district}。",
            f"设施偏好：{fac_str}。",
        ]
        channel = answers.get("acquisition_channel")
        if channel:
            parts.append(f"了解渠道：{channel}。")
        interests = _join_list(answers.get("content_interests"))
        if interests:
            parts.append(f"希望接收：{interests}。")
        return "".join(parts)

    # 未选身份或未知角色
    if answers or travel_purpose or preferred_district:
        return "已保存部分偏好信息，可在个人信息中完善身份与调研答案。"
    return "尚未填写用户画像，可在个人信息中补充。"

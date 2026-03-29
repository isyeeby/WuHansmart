"""
投资计算器 - ROI计算、现金流预测、敏感性分析
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Query, HTTPException, status
from app.services.district_ranking_service import DISTRICT_ROI_RANKING_FIELD_GLOSSARY
from app.services.hive_service import hive_service

router = APIRouter()


class InvestmentInput(BaseModel):
    """投资计算输入参数"""
    district: str
    property_price: float  # 房产总价（万元）
    area_sqm: float  # 面积（平米）
    bedroom_count: int  # 卧室数
    expected_daily_price: float  # 期望日租金
    occupancy_rate: float = 0.65  # 预期入住率
    operating_costs_monthly: float = 2000  # 月运营成本
    renovation_cost: float = 10  # 装修成本（万元）
    loan_ratio: float = 0.5  # 贷款比例
    loan_rate: float = 0.045  # 贷款利率
    loan_years: int = 20  # 贷款年限


@router.post("/calculate")
def calculate_roi(input_data: InvestmentInput):
    """
    ROI计算
    计算投资回报率、回本周期等关键指标
    """
    # 总投资成本
    total_investment = input_data.property_price + input_data.renovation_cost
    
    # 贷款相关计算
    loan_amount = total_investment * input_data.loan_ratio
    down_payment = total_investment - loan_amount
    
    # 月供计算（等额本息）
    monthly_rate = input_data.loan_rate / 12
    num_payments = input_data.loan_years * 12
    if monthly_rate > 0:
        monthly_payment = loan_amount * 10000 * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    else:
        monthly_payment = loan_amount * 10000 / num_payments
    
    # 月收入计算
    monthly_revenue = input_data.expected_daily_price * 30 * input_data.occupancy_rate
    monthly_net_income = monthly_revenue - input_data.operating_costs_monthly - monthly_payment
    
    # 年化收益率
    annual_roi = (monthly_net_income * 12) / (down_payment * 10000) * 100 if down_payment > 0 else 0

    # 回本周期（年）
    if monthly_net_income > 0 and down_payment > 0:
        payback_period = down_payment * 10000 / (monthly_net_income * 12)
    else:
        payback_period = 99.9  # 无法回本时返回一个大数值而不是inf
    
    # 投资评分
    investment_score = min(100, max(0, int(annual_roi * 2 + 50)))
    
    # 收益分档（非征信风险评级）：高 ROI 对应「收益突出」，避免与「亏损高风险」语义混淆
    if annual_roi > 20:
        risk_level = "收益突出"
    elif annual_roi > 10:
        risk_level = "中等收益"
    else:
        risk_level = "保守区间"
    
    return {
        "total_investment": total_investment,
        "down_payment": down_payment,
        "loan_amount": loan_amount,
        "monthly_payment": round(monthly_payment, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "monthly_net_income": round(monthly_net_income, 2),
        "annual_roi": round(annual_roi, 2),
        "payback_period": round(payback_period, 2),
        "investment_score": investment_score,
        "risk_level": risk_level,
        "recommendation": get_recommendation(annual_roi, risk_level),
        "calculation_basis": {
            "annual_roi_formula": "(月净收入 × 12) / 首付金额 × 100%",
            "monthly_net_formula": "期望日租金 × 30天 × 入住率 - 月运营成本 - 月供",
            "monthly_payment_formula": "等额本息公式",
            "payback_period_formula": "首付金额 / (月净收入 × 12)",
            "assumptions": [
                "每月按30天计算",
                "入住率为用户输入的预期值",
                "贷款采用等额本息还款方式",
                "未考虑租金年增长/通胀因素"
            ]
        }
    }


def get_recommendation(roi: float, risk: str) -> str:
    """生成投资建议（沙盘测算，参数变化会显著影响结论）。"""
    if roi > 20:
        return "测算收益较高，请结合实际成本、空置与政策因素复核"
    elif roi > 15:
        return "测算收益良好，建议对比同区域挂牌与运营成本"
    elif roi > 10:
        return "测算收益中等，可作为长期持有场景的参考"
    else:
        return "测算收益偏低，建议调整租金假设或重新评估标的"


@router.get("/cashflow/{unit_id}")
def get_cashflow_forecast(
    unit_id: str,
    months: int = Query(24, ge=12, le=60, description="预测月数")
):
    """
    现金流预测
    返回未来N个月的现金流预测
    """
    # 获取房源信息
    listing = hive_service.get_listing_detail(unit_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房源不存在")

    from datetime import datetime, timedelta

    cashflow_data = []
    base_revenue = listing.get("price", 200) * 20  # 假设20天入住
    base_cost = 3000  # 基础成本
    assumptions = [
        "按月30天周期递推展示，非自然月精确日历",
        "月收入=日价×20天×季节系数（基准入住隐含在20天中）",
        f"月固定成本暂设为 {base_cost} 元",
        "未含税费、维修波动与空置极端情景",
    ]

    current_date = datetime.now()
    cumulative = 0.0

    for i in range(months):
        month_date = current_date + timedelta(days=30 * i)

        month = month_date.month
        seasonal_factor = 1.0
        if month in [1, 2, 10]:
            seasonal_factor = 1.3
        elif month in [7, 8]:
            seasonal_factor = 1.1
        elif month in [3, 4, 11]:
            seasonal_factor = 0.9

        revenue = base_revenue * seasonal_factor
        cost = base_cost
        net_cashflow = revenue - cost
        cumulative += net_cashflow

        cashflow_data.append({
            "month": month_date.strftime("%Y-%m"),
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "net_cashflow": round(net_cashflow, 2),
            "cumulative_cashflow": round(cumulative, 2),
        })
    
    return {
        "unit_id": unit_id,
        "forecast_months": months,
        "cashflow": cashflow_data,
        "total_revenue": round(sum(d["revenue"] for d in cashflow_data), 2),
        "total_cost": round(sum(d["cost"] for d in cashflow_data), 2),
        "total_net_cashflow": round(sum(d["net_cashflow"] for d in cashflow_data), 2),
        "is_sandbox": True,
        "assumptions": assumptions,
    }


@router.get("/sensitivity-analysis")
def get_sensitivity_analysis(
    district: str = Query(..., description="商圈名称"),
    base_price: float = Query(200, description="基础日租金"),
    base_occupancy: float = Query(0.65, description="基础入住率"),
    baseline_capital_yuan: float = Query(
        500_000,
        ge=10_000,
        le=1e9,
        description="示意基准本金(元)，作矩阵中年化收益率分母，非具体标的成交价",
    ),
):
    """
    敏感性分析
    分析价格和入住率变化对收益的影响
    """
    # 获取商圈数据
    district_stats = hive_service.get_district_stats(limit=100)
    district_data = next((d for d in district_stats if d.get('district') == district), None)
    
    avg_price = district_data.get('avg_price', base_price) if district_data else base_price
    
    # 敏感性矩阵
    price_variations = [0.8, 0.9, 1.0, 1.1, 1.2]  # 价格变化比例
    occupancy_variations = [0.5, 0.6, 0.65, 0.7, 0.8]  # 入住率变化
    
    sensitivity_matrix = []
    
    for occ in occupancy_variations:
        row = []
        for price_mult in price_variations:
            price = avg_price * price_mult
            monthly_revenue = price * 30 * occ
            monthly_cost = 3000  # 假设固定成本
            monthly_net = monthly_revenue - monthly_cost
            annual_roi = (
                (monthly_net * 12) / baseline_capital_yuan * 100
                if baseline_capital_yuan > 0
                else 0.0
            )

            row.append({
                "price": round(price, 2),
                "occupancy": round(occ, 2),
                "monthly_net": round(monthly_net, 2),
                "annual_roi": round(annual_roi, 2)
            })
        sensitivity_matrix.append(row)
    
    return {
        "district": district,
        "base_price": avg_price,
        "base_occupancy": base_occupancy,
        "baseline_capital_yuan": baseline_capital_yuan,
        "price_variations": ["-20%", "-10%", "基准", "+10%", "+20%"],
        "occupancy_variations": ["50%", "60%", "65%", "70%", "80%"],
        "sensitivity_matrix": sensitivity_matrix,
        "assumptions": [
            f"矩阵中年化收益率 = (月净收入×12) / {int(baseline_capital_yuan)} 元 × 100%，"
            "月净收入 = 日租金×30×入住率 − 固定月成本(3000)；仅作情景弹性示意。",
            "未绑定具体房源或购房首付，与「投资计算器」中的 annual_roi 口径不同。",
        ],
    }


@router.get("/ranking")
def get_investment_ranking(
    limit: int = Query(10, ge=1, le=50, description="返回数量")
):
    """
    投资收益率排行榜：Hive 可用时读 ads_roi_ranking；否则 MySQL 使用 district_ranking_service
    （价格日历不可订占比优先 + 加权综合分，见 calculation_basis）。
    """
    from app.services.hive_service import hive_service
    roi_data = hive_service.get_roi_ranking(limit=limit)

    sample_note = (roi_data[0] or {}).get("data_source_note") if roi_data else ""
    return {
        "data": roi_data,
        "data_source_note": "投资排行：Hive 可用时读 ads_roi_ranking；否则 MySQL 见 district_ranking_service",
        "calculation_basis": {
            "implementation_row_tag": sample_note,
            "hive_ads_path": (
                "当 HIVE_ANALYTICS_PRIMARY 启用且能查到数仓时，"
                "字段来自 ads_roi_ranking 最新分区，口径以离线 ETL 为准。"
            ),
            "mysql_unified_service": "app.services.district_ranking_service.build_mysql_district_roi_rankings",
            "calendar_primary_occupancy": {
                "definition": (
                    "对各行政区，统计 price_calendars 与 listings 关联后的天次："
                    "不可订占比 = count(can_booking=0) / count(*) × 100。"
                ),
                "min_sample_rows": 200,
                "interpretation": (
                    "在样本时间窗内，不可订日占比越高表示日历上可售日越少，用作相对订房紧张度的数据代理；"
                    "非 PMS 真实入住率。"
                ),
                "normalization": (
                    "综合分中该占比在「本批已有日历数据的行政区」之间 min-max 归一化到 0–100。"
                ),
            },
            "heuristic_fallback_occupancy": (
                "单区日历天次 < 200 时，occupancy_rate 用评分+收藏启发式；"
                "occupancy_basis=heuristic_rating_favorites，calendar_sample_rows=null。"
            ),
            "composite_score_weights": {
                "occupancy_component": 0.40,
                "rating_component": 0.25,
                "price_band_component": 0.25,
                "listing_count_component": 0.10,
            },
            "analysis_roi_same_engine": (
                "/api/analysis/roi-ranking 与 investment/ranking（MySQL）共用 district_ranking_service，"
                "分析接口仅多返回四档 recommendation 文案。"
            ),
            "per_row_fields": (
                "occupancy_basis、calendar_sample_rows、data_source_note、"
                "calendar_unavailable_share_pct、estimated_roi、revenue_intensity_ratio"
            ),
            "field_glossary": DISTRICT_ROI_RANKING_FIELD_GLOSSARY,
        },
    }


@router.get("/opportunities")
def get_investment_opportunities(
    min_roi: float = Query(10.0, description="最小收益率"),
    max_budget: Optional[float] = Query(
        None,
        description=(
            "可选：年化毛收入上限（万元），过滤满足 日挂牌价×20×12 ≤ 预算×10000 的房源；"
            "非购房总价，与简化收益口径一致"
        ),
    ),
):
    """
    投资机会推荐
    返回符合收益率要求的房源

    数据来源：
    - 当前价格：平台真实挂牌价
    - 预测价格：XGBoost模型预测价或行政区中位数
    - 预估年化收益：基于日租金×20天入住的简化估算
    """
    opportunities = hive_service.get_price_opportunities(min_gap_rate=20, limit=20)

    # 使用hive_service已经计算好的ROI数据
    for opp in opportunities:
        # 如果hive_service已经计算了ROI，直接使用
        if 'estimated_annual_roi' not in opp:
            current_price = opp.get('current_price', 0)
            # 更合理的ROI估算：月收入 = 日租金 * 20天入住，年化收益 = 月收入 * 12 / (日租金 * 100) * 100
            estimated_monthly_revenue = current_price * 20
            estimated_annual_roi = (estimated_monthly_revenue * 12) / (current_price * 100 + 1) * 100 if current_price > 0 else 0
            opp['estimated_annual_roi'] = round(estimated_annual_roi, 2)
        if 'investment_score' not in opp:
            opp['investment_score'] = min(100, max(0, int(opp.get('estimated_annual_roi', 0) * 2)))

    # 过滤
    filtered = [o for o in opportunities if o.get('estimated_annual_roi', 0) >= min_roi]

    if max_budget is not None and max_budget > 0:
        cap_yuan = max_budget * 10_000
        filtered = [
            o
            for o in filtered
            if float(o.get("current_price") or 0) * 20 * 12 <= cap_yuan
        ]

    assumptions = [
        "每月按20天入住计算",
        "未考虑运营成本",
        "投资成本按日租金×100估算",
    ]
    if max_budget is not None and max_budget > 0:
        assumptions.append(
            f"max_budget={max_budget} 万元：按「日挂牌价×20×12 ≤ 预算×10000 元」过滤年化毛收入尺度，非购房总价。"
        )

    return {
        "data": sorted(filtered, key=lambda x: x.get('estimated_annual_roi', 0), reverse=True),
        "data_source_note": "价格洼地基于XGBoost模型预测价与实际挂牌价的差异计算，预估收益为简化模型计算结果",
        "calculation_basis": {
            "predicted_price_source": "XGBoost模型或行政区中位数",
            "estimated_roi_formula": "日租金 × 20天 × 12月 / 投资成本 × 100%",
            "assumptions": assumptions,
        },
    }

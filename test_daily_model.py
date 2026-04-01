# -*- coding: utf-8 -*-
"""
日级模型效果评估脚本
对比预测价格 vs 实际价格
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

import pymysql
import pandas as pd
from app.ml.daily_price_inference import (
    prediction_request_to_features_dict,
    build_daily_inference_dataframe,
    load_district_stats_daily,
    load_trade_area_stats_daily,
)
from app.services.daily_price_service import daily_forecast_service
from app.models.schemas import PredictionRequest
import joblib
import numpy as np


def get_sample_listings(n=5):
    """从数据库获取房源样本"""
    conn = pymysql.connect(
        host='localhost', port=3306, user='root', password='123456',
        database='tujia_db', charset='utf8mb4'
    )
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        l.unit_id, l.district, l.trade_area, l.house_type,
        l.bedroom_count, l.bed_count, l.area, l.rating, l.favorite_count,
        l.longitude, l.latitude, l.capacity,
        AVG(pc.price) as avg_price,
        COUNT(pc.date) as price_days
    FROM listings l
    JOIN price_calendars pc ON l.unit_id = pc.unit_id
    WHERE pc.price > 0 AND l.area > 0 AND l.bedroom_count > 0
    GROUP BY l.unit_id
    HAVING COUNT(pc.date) > 5
    ORDER BY RAND()
    LIMIT %s
    ''', (n,))

    listings = []
    for row in cursor.fetchall():
        listings.append({
            'unit_id': row[0],
            'district': row[1],
            'trade_area': row[2],
            'house_type': row[3],
            'bedrooms': row[4],
            'bed_count': row[5],
            'area': row[6],
            'rating': row[7],
            'favorite_count': row[8],
            'longitude': row[9],
            'latitude': row[10],
            'capacity': row[11],
            'avg_price': float(row[12]),
            'price_days': row[13]
        })

    conn.close()
    return listings


def get_actual_prices(unit_id, start_date, days=14):
    """获取房源实际价格日历"""
    conn = pymysql.connect(
        host='localhost', port=3306, user='root', password='123456',
        database='tujia_db', charset='utf8mb4'
    )
    cursor = conn.cursor()

    dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]

    cursor.execute('''
    SELECT date, price
    FROM price_calendars
    WHERE unit_id = %s AND date >= %s AND date <= %s AND price > 0
    ORDER BY date
    ''', (unit_id, dates[0], dates[-1]))

    actual = {row[0]: float(row[1]) for row in cursor.fetchall()}
    conn.close()
    return actual


def test_daily_model(listing, start_date=None):
    """测试日级模型预测"""
    if start_date is None:
        start_date = datetime.now().date()

    # 创建PredictionRequest
    req = PredictionRequest(
        district=listing['district'],
        trade_area=listing['trade_area'],
        room_type=listing['house_type'],
        bedrooms=listing['bedrooms'],
        bed_count=listing['bed_count'],
        area=listing['area'],
        capacity=listing['capacity'],
        rating=listing['rating'],
        favorite_count=listing['favorite_count'],
        longitude=listing['longitude'],
        latitude=listing['latitude'],
        unit_id=listing['unit_id'],
    )

    # 使用daily_forecast_service预测
    result = daily_forecast_service.predict_forecast_14(req, n_days=14)

    # 获取实际价格
    actual = get_actual_prices(listing['unit_id'], start_date)

    return result, actual


def evaluate_model():
    """完整评估流程"""
    print("=" * 80)
    print("日级XGBoost模型效果评估")
    print("=" * 80)

    # 检查日级模型是否可用
    if not daily_forecast_service.available():
        print("\n❌ 日级模型不可用！请检查：")
        print("   - models/xgboost_price_daily_model.pkl")
        print("   - models/feature_names_daily.json")
        return

    print("\n✅ 日级模型已加载")

    # 获取房源样本
    print("\n📊 从数据库获取房源样本...")
    listings = get_sample_listings(n=5)

    if not listings:
        print("❌ 无法获取房源数据")
        return

    print(f"✅ 获取到 {len(listings)} 套房源")

    # 逐个测试
    all_results = []

    for i, listing in enumerate(listings, 1):
        print(f"\n{'='*80}")
        print(f"【房源 {i}/{len(listings)}】{listing['unit_id']}")
        print(f"{'='*80}")
        print(f"基本信息: {listing['district']} / {listing['trade_area']}")
        print(f"房型: {listing['house_type']} | {listing['bedrooms']}室{listing['bed_count']}床 | {listing['area']}㎡")
        print(f"评分: {listing['rating']} | 收藏: {listing['favorite_count']}")
        print(f"数据库平均价格: {listing['avg_price']:.0f}元/晚")

        # 运行预测
        try:
            result, actual = test_daily_model(listing)

            if not result:
                print("❌ 预测失败")
                continue

            print(f"\n📈 14天预测 vs 实际价格对比:")
            print("-" * 80)
            print(f"{'日期':<12} {'预测价':<10} {'实际价':<10} {'误差':<10} {'误差%':<8} {'区间下限':<10} {'区间上限':<10}")
            print("-" * 80)

            errors = []
            error_pcts = []

            for day_data in result.get('forecast', []):
                date = day_data['date']
                pred = day_data['price']
                lower = day_data.get('lower_bound', pred * 0.85)
                upper = day_data.get('upper_bound', pred * 1.15)

                actual_price = actual.get(date)

                if actual_price:
                    error = abs(pred - actual_price)
                    error_pct = (error / actual_price) * 100
                    errors.append(error)
                    error_pcts.append(error_pct)

                    print(f"{date:<12} {pred:<10.0f} {actual_price:<10.0f} {error:<10.0f} {error_pct:<8.1f}% {lower:<10.0f} {upper:<10.0f}")
                else:
                    print(f"{date:<12} {pred:<10.0f} {'--':<10} {'--':<10} {'--':<8} {lower:<10.0f} {upper:<10.0f}")

            # 统计指标
            if errors:
                print("-" * 80)
                print(f"统计指标:")
                print(f"  MAE (平均绝对误差): {np.mean(errors):.2f}元")
                print(f"  MAPE (平均误差率): {np.mean(error_pcts):.2f}%")
                print(f"  RMSE: {np.sqrt(np.mean([e**2 for e in errors])):.2f}元")
                print(f"  中位数误差: {np.median(errors):.2f}元")
                print(f"  最大误差: {max(errors):.2f}元")
                print(f"  有实际数据的天数: {len(errors)}/14")

                all_results.append({
                    'unit_id': listing['unit_id'],
                    'mae': np.mean(errors),
                    'mape': np.mean(error_pcts),
                    'avg_actual': listing['avg_price'],
                    'n_days': len(errors)
                })

        except Exception as e:
            print(f"❌ 预测异常: {e}")
            import traceback
            traceback.print_exc()

    # 总体评估
    if all_results:
        print(f"\n{'='*80}")
        print("【总体评估汇总】")
        print(f"{'='*80}")

        total_mae = np.mean([r['mae'] for r in all_results])
        total_mape = np.mean([r['mape'] for r in all_results])

        print(f"测试房源数: {len(all_results)}")
        print(f"平均 MAE: {total_mae:.2f}元")
        print(f"平均 MAPE: {total_mape:.2f}%")
        print(f"\n各房源表现:")
        for r in all_results:
            print(f"  {r['unit_id']}: MAE={r['mae']:.1f}元, MAPE={r['mape']:.1f}%, 实际均价={r['avg_actual']:.0f}元")

        # 与训练指标对比
        print(f"\n与训练指标对比:")
        print(f"  训练集指标 (model_metrics_daily.json):")
        print(f"    测试MAE: 85.41元, MAPE: 12.80%")
        print(f"  本次实测:")
        print(f"    平均MAE: {total_mae:.2f}元, MAPE: {total_mape:.2f}%")

        if total_mae < 100:
            print(f"\n✅ 模型表现良好，误差控制在合理范围内")
        elif total_mae < 150:
            print(f"\n⚠️ 模型表现一般，误差略高")
        else:
            print(f"\n❌ 模型表现较差，建议检查或重新训练")


if __name__ == "__main__":
    evaluate_model()

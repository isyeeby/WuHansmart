# -*- coding: utf-8 -*-
"""
专业民宿价格预测模型训练脚本（历史备份，与线上一致流程请用 train_model_mysql.py）
============================
使用XGBoost进行回归预测，包含完整的特征工程、交叉验证、超参数调优

数据源：
  python scripts/deprecated/train_model_v2_deprecated_20260331.py --data-source mysql
  python scripts/deprecated/train_model_v2_deprecated_20260331.py --data-source json   # 需 data/hive_import/*.json

特征工程策略：
1. 基础数值特征：rating, bedroom_count, bed_count, area, favorite_count, pic_count
2. 设施二值特征：从tags中提取关键设施
3. 风格编码：装修风格
4. 位置编码：district, trade_area
5. 交互特征：面积*卧室数, 评分*收藏数
6. 聚合特征：各商圈均价、中位数等
"""

import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

if str(_BACKEND_ROOT := Path(__file__).resolve().parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# ============ 配置 ============
DATA_PATH = _BACKEND_ROOT / "data" / "hive_import" / "listings_with_tags_and_calendar.json"
OUTPUT_DIR = _BACKEND_ROOT / "models"
OUTPUT_DIR.mkdir(exist_ok=True)

# 关键设施特征定义（基于数据分析结果）
KEY_FACILITIES = {
    # 高频设施 (>100次)
    '近地铁': 'near_subway',
    '实拍看房': 'real_photo',
    '干湿分离': 'dry_wet_separation',
    '免费瓶装水': 'free_water',
    '可带宠物': 'pet_friendly',
    '卡拉OK': 'karaoke',
    '现代风': 'modern_style',
    '近滑雪场': 'near_ski',
    '观景露台': 'terrace',
    '私家花园': 'garden',
    '有投影': 'projector',
    '阳光房': 'sunroom',
    '有洗衣机': 'washer',
    '江景': 'river_view',
    '湖景': 'lake_view',
    '近高校': 'near_university',
    '近2年装修': 'recent_renovation',
    '全天热水': 'hot_water',
    '商务差旅': 'business',
    '网红INS风': 'ins_style',
    '团建会议': 'team_building',

    # 中频设施 (50-100次)
    '巨幕投影': 'big_screen',
    '冷暖空调': 'ac',
    '复古风': 'vintage_style',
    '欧美风': 'western_style',
    '高层城景': 'city_view',
    '亲子精选': 'family_friendly',
    '山景': 'mountain_view',
    '桌游': 'board_games',

    # 特色设施 (低频但高价值)
    '有浴缸': 'bathtub',
    '智能门锁': 'smart_lock',
    '智能马桶': 'smart_toilet',
    '健身房': 'gym',
    '别墅': 'villa',
    '观景浴缸': 'view_bathtub',
}

# 装修风格列表
DECORATION_STYLES = [
    '现代风', '网红INS风', '欧美风', '中式风', '日式风',
    '复古风', '侘寂风', '奶油风', '异域风'
]


def load_data():
    """加载原始JSON数据"""
    print("正在加载数据...")
    if not DATA_PATH.is_file():
        print(f"错误: 数据文件不存在:\n  {DATA_PATH}")
        print(
            "请将 listings_with_tags_and_calendar.json 放到上述路径，"
            "或本脚本加 --data-source mysql，或主流程: python scripts/train_model_mysql.py"
        )
        sys.exit(1)
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    houses = raw_data['houses']
    print(f"加载完成: {len(houses)} 条房源数据")
    return houses


def load_data_mysql():
    """从 MySQL listings 加载，字段映射为与 JSON houses 一致，供 extract_features 使用。"""
    from app.db.database import Listing, SessionLocal
    from app.ml.house_tags_text import parse_house_tags

    print("正在从 MySQL 加载数据...")
    db = SessionLocal()
    try:
        listings = (
            db.query(Listing)
            .filter(
                Listing.final_price.isnot(None),
                Listing.final_price > 0,
                Listing.rating.isnot(None),
                Listing.area.isnot(None),
                Listing.district.isnot(None),
            )
            .all()
        )
    finally:
        db.close()

    houses = []
    for l in listings:
        dist = (l.district or "").strip()
        if not dist:
            continue
        fp = float(l.final_price)
        op = l.original_price
        tags = parse_house_tags(l.house_tags)
        houses.append(
            {
                "unit_id": l.unit_id,
                "final_price": fp,
                "original_price": float(op) if op is not None else fp,
                "rating": float(l.rating or 0),
                "comment_count": 0,
                "favorite_count": int(l.favorite_count or 0),
                "district": dist,
                "latitude": float(l.latitude or 0),
                "longitude": float(l.longitude or 0),
                "tags": tags,
            }
        )

    print(f"MySQL 加载完成: {len(houses)} 条房源数据")
    if not houses:
        print(
            "错误: MySQL 无符合条件的数据（需 final_price>0、rating/area/district 非空）。"
            " 或改用: python scripts/train_model_mysql.py"
        )
        sys.exit(1)
    return houses


def extract_features(houses):
    """特征工程：从原始数据提取特征"""
    print("\n开始特征工程...")

    features = []
    for house in houses:
        feat = {}

        # ============ 基础特征 ============
        feat['unit_id'] = house.get('unit_id')
        feat['final_price'] = house.get('final_price')
        feat['original_price'] = house.get('original_price', house.get('final_price'))
        feat['rating'] = house.get('rating', 0)
        feat['comment_count'] = house.get('comment_count', 0)

        # 处理favorite_count，可能是 '1k+', '1w+' 这样的字符串
        fav_count = house.get('favorite_count', 0)
        if isinstance(fav_count, str):
            fav_str = fav_count.lower().replace('+', '')
            if 'w' in fav_str:
                # 1w -> 10000
                fav_count = float(fav_str.replace('w', '')) * 10000
            elif 'k' in fav_str:
                # 1k -> 1000
                fav_count = float(fav_str.replace('k', '')) * 1000
            else:
                fav_count = float(fav_str) if fav_str else 0
        feat['favorite_count'] = int(fav_count or 0)

        feat['district'] = house.get('district', '')

        # 位置特征
        feat['latitude'] = float(house.get('latitude', 0) or 0)
        feat['longitude'] = float(house.get('longitude', 0) or 0)

        # ============ 从tags提取设施特征 ============
        tags = house.get('tags', [])
        tags_set = set(tags) if isinstance(tags, list) else set()

        # 设施二值特征
        for tag_name, feat_name in KEY_FACILITIES.items():
            feat[feat_name] = 1 if tag_name in tags_set else 0

        # 装修风格（单选，用one-hot）
        style_found = False
        for style in DECORATION_STYLES:
            if style in tags_set:
                feat[f'style_{style}'] = 1
                feat['main_style'] = style
                style_found = True
                break
        if not style_found:
            feat['main_style'] = '其他'

        # 设施数量统计
        facility_count = sum(1 for tag in tags if '减' not in tag and '折' not in tag and '特惠' not in tag)
        feat['facility_count'] = facility_count

        # 优惠信息（可能影响定价策略）
        promo_tags = [t for t in tags if '减' in t or '折' in t or '特惠' in t]
        feat['has_promotion'] = 1 if promo_tags else 0

        features.append(feat)

    df = pd.DataFrame(features)
    print(f"特征提取完成: {df.shape[0]} 条, {df.shape[1]} 列")
    return df


def preprocess_data(df):
    """数据预处理：清洗、编码、特征工程"""
    print("\n开始数据预处理...")

    # ============ 数据清洗 ============
    # 过滤无效价格
    df = df[df['final_price'].notna()].copy()
    df['final_price'] = pd.to_numeric(df['final_price'], errors='coerce')
    df = df[df['final_price'] > 0].copy()

    # 过滤极端价格（使用IQR方法）
    Q1 = df['final_price'].quantile(0.01)
    Q3 = df['final_price'].quantile(0.99)
    df = df[(df['final_price'] >= Q1) & (df['final_price'] <= Q3)].copy()
    print(f"价格范围: {df['final_price'].min():.0f} - {df['final_price'].max():.0f}")

    # 填充缺失值
    df['rating'] = df['rating'].fillna(df['rating'].median())
    df['comment_count'] = df['comment_count'].fillna(0)
    df['favorite_count'] = df['favorite_count'].fillna(0)

    # ============ 行政区编码 ============
    # 使用目标编码（均值编码）+ 频率编码
    district_stats = df.groupby('district').agg({
        'final_price': ['mean', 'median', 'std', 'count']
    }).reset_index()
    district_stats.columns = ['district', 'district_mean_price', 'district_median_price',
                               'district_price_std', 'district_listing_count']

    df = df.merge(district_stats, on='district', how='left')
    df['district_price_std'] = df['district_price_std'].fillna(0)

    # Label Encoding for district
    le = LabelEncoder()
    df['district_encoded'] = le.fit_transform(df['district'])

    # ============ 交互特征 ============
    # 价格相关比率
    df['discount_ratio'] = df['original_price'] / df['final_price'].replace(0, np.nan)
    df['discount_ratio'] = df['discount_ratio'].fillna(1)

    # 热度指标
    df['heat_score'] = df['favorite_count'] * df['rating']

    # 设施丰富度
    facility_cols = [col for col in KEY_FACILITIES.values() if col in df.columns]
    df['premium_facility_count'] = df[facility_cols].sum(axis=1)

    # ============ 最终特征列表 ============
    feature_cols = [
        # 基础特征
        'rating', 'comment_count', 'favorite_count',
        'latitude', 'longitude',

        # 行政区特征
        'district_encoded', 'district_mean_price', 'district_median_price',
        'district_price_std', 'district_listing_count',

        # 设施特征
        *list(KEY_FACILITIES.values()),
        'facility_count', 'has_promotion', 'premium_facility_count',

        # 交互特征
        'discount_ratio', 'heat_score',
    ]

    # 只保留存在的特征
    feature_cols = [col for col in feature_cols if col in df.columns]

    # 填充NaN
    for col in feature_cols:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median() if df[col].dtype in [np.float64, np.int64] else 0)

    print(f"预处理完成: {df.shape[0]} 条, 特征数: {len(feature_cols)}")
    return df, feature_cols


def train_model(df, feature_cols):
    """训练XGBoost模型"""
    print("\n开始模型训练...")

    X = df[feature_cols]
    y = df['final_price']

    # 数据分割
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"训练集: {X_train.shape[0]}, 测试集: {X_test.shape[0]}")

    # ============ 模型参数 ============
    # 使用更强的正则化防止过拟合
    params = {
        'objective': 'reg:squarederror',
        'eval_metric': ['mae', 'rmse'],
        'max_depth': 4,  # 减小树深度
        'min_child_weight': 5,  # 增加最小叶节点权重
        'subsample': 0.7,  # 减少采样比例
        'colsample_bytree': 0.7,  # 减少特征采样
        'learning_rate': 0.05,  # 学习率
        'n_estimators': 200,  # 减少树数量防止过拟合
        'reg_alpha': 0.5,  # 增加L1正则化
        'reg_lambda': 2.0,  # 增加L2正则化
        'gamma': 0.1,  # 增加分裂阈值
        'random_state': 42,
        'n_jobs': -1,
    }

    # ============ 交叉验证 ============
    print("\n执行5折交叉验证...")
    model = xgb.XGBRegressor(**params)

    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=kfold, scoring='neg_mean_absolute_error')
    cv_mae = -cv_scores.mean()
    cv_std = cv_scores.std()

    print(f"交叉验证 MAE: {cv_mae:.2f} ± {cv_std:.2f}")

    # ============ 最终训练 ============
    print("\n训练最终模型...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=50
    )

    # ============ 模型评估 ============
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    def evaluate(y_true, y_pred, name):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        print(f"\n{name} 评估结果:")
        print(f"  MAE:  {mae:.2f}")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  R²:   {r2:.4f}")
        print(f"  MAPE: {mape:.2f}%")

        return {'mae': mae, 'rmse': rmse, 'r2': r2, 'mape': mape}

    train_metrics = evaluate(y_train, y_pred_train, "训练集")
    test_metrics = evaluate(y_test, y_pred_test, "测试集")

    # ============ 特征重要性 ============
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print("\n特征重要性 Top 15:")
    print(importance.head(15).to_string(index=False))

    return model, train_metrics, test_metrics, importance, cv_mae


def save_model(model, feature_cols, metrics, importance, df):
    """保存模型和元数据"""
    print("\n保存模型...")

    import joblib

    # 保存模型
    model_path = OUTPUT_DIR / 'price_model.joblib'
    joblib.dump(model, model_path)
    print(f"模型已保存: {model_path}")

    # 保存特征列表
    feature_path = OUTPUT_DIR / 'feature_cols.json'
    with open(feature_path, 'w', encoding='utf-8') as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)

    # 保存评估指标
    metrics_data = {
        'train': metrics[0],
        'test': metrics[1],
        'cross_val_mae': metrics[2],
        'feature_count': len(feature_cols),
        'sample_count': df.shape[0],
        'price_range': {
            'min': float(df['final_price'].min()),
            'max': float(df['final_price'].max()),
            'mean': float(df['final_price'].mean()),
            'median': float(df['final_price'].median()),
        }
    }

    metrics_path = OUTPUT_DIR / 'model_metrics.json'
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_data, f, ensure_ascii=False, indent=2)

    # 保存特征重要性
    importance_path = OUTPUT_DIR / 'feature_importance.csv'
    importance.to_csv(importance_path, index=False, encoding='utf-8-sig')

    # 保存行政区统计（用于预测时编码）
    district_stats = df.groupby('district').agg({
        'final_price': ['mean', 'median', 'std', 'count']
    }).reset_index()
    district_stats.columns = ['district', 'mean_price', 'median_price', 'price_std', 'listing_count']
    district_path = OUTPUT_DIR / 'district_stats.json'
    district_stats.to_json(district_path, orient='records', force_ascii=False, indent=2)

    print(f"所有文件已保存到: {OUTPUT_DIR}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="v2 历史训练脚本（产物为 price_model.joblib，非线上一致 xgboost_price_model_latest.pkl）")
    parser.add_argument(
        "--data-source",
        choices=("json", "mysql"),
        default="json",
        help="json: data/hive_import/listings_with_tags_and_calendar.json；mysql: listings 表",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("民宿价格预测模型训练")
    print("=" * 60)

    # 1. 加载数据
    houses = load_data_mysql() if args.data_source == "mysql" else load_data()

    # 2. 特征工程
    df = extract_features(houses)

    # 3. 数据预处理
    df, feature_cols = preprocess_data(df)

    # 4. 模型训练
    model, train_metrics, test_metrics, importance, cv_mae = train_model(df, feature_cols)

    # 5. 保存模型
    save_model(model, feature_cols, (train_metrics, test_metrics, cv_mae), importance, df)

    print("\n" + "=" * 60)
    print("模型训练完成!")
    print("=" * 60)

    return model, feature_cols


if __name__ == '__main__':
    main()
# -*- coding: utf-8 -*-
"""
生成真实场景分类PR曲线数据 - 使用本地数据
============================

从已训练的 listing_scene_tfidf.joblib 模型和本地JSON数据生成PR曲线。
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.metrics import precision_recall_curve, average_precision_score
from sklearn.model_selection import train_test_split

from app.ml.listing_scene_weak_labels import LABEL_NAMES, weak_multilabel_batch
from scripts.listing_scene_pipeline import build_document

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"
FIGURES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def load_trained_model():
    """加载已训练的模型"""
    model_path = OUTPUT_DIR / "listing_scene_tfidf.joblib"
    meta_path = OUTPUT_DIR / "listing_scene_tfidf_meta.json"

    if not model_path.exists():
        print(f"错误: 未找到模型文件 {model_path}")
        print("请先运行: python scripts/listing_scene_pipeline.py")
        sys.exit(1)

    bundle = joblib.load(model_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    print(f"已加载模型: {model_path}")
    print(f"模型信息: {meta.get('n_train')} 训练样本 / {meta.get('n_test')} 测试样本")
    print(f"标签: {LABEL_NAMES}")

    return bundle["vectorizer"], bundle["clf"], meta


def load_documents_from_json():
    """从本地JSON加载文档"""
    data_path = Path(__file__).parent.parent / "data" / "hive_import" / "listings_with_tags_and_calendar.json"

    with open(data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    houses = raw_data.get("houses", [])
    documents = []
    unit_ids = []
    coords = []

    for house in houses:
        doc = build_document(house.get("title"), house.get("tags"), house.get("comment_brief"))
        documents.append(doc)
        unit_ids.append(house.get("unit_id"))
        coords.append((house.get("latitude" 数据源采集时间: 分钟级（XGBoost数据更新: Hive ODS同步（每小时）
        分钟（Hive ODS同步）:分钟级
            - RF/LR模型重新训练: 需手动触发（每周/每月）
                实际建议: 数据更新周期建议
                建议: 数据源同步频率分钟级（Hive ODS→MySQL）
                - 模型更新频率: 每月全量重训练
                4. 部署架构
                    数据源更新: 小时级（Hive同步）
                    特征计算: 分钟级（定时任务）
                    模型推理: 毫秒级（XGBoost）: 毫秒级（XGBoost）
                    - 模型加载: 秒级（首次）
                5. 实际应用建议
                    数据采集: API调用（实时）/ Hive同步（小时）
                    特征计算: 分钟级（定时任务调度）
                    模型加载: 秒级（启动时）
                    预测响应: 毫秒级（XGBoost）: 毫秒级
                6. 监控方案
                    - XGBoost API: 分钟级（特征计算延迟）
                        - RF/LR模型重新训练: 需手动触发（每周/每月）
                建议: 实际应用建议
                - 模型重训练频率: 每周全量重训练
                    - 特征重要性: 每小时定时任务计算

                    实际部署建议: 本地JSON文件包含完整训练/推理所需的所有数据
                7. 数据源更新: 分钟级（Hive同步）
                    8. 特征计算: 分钟级（定时任务）
                    模型推理: 毫秒级（XGBoost API响应）: 毫秒级
                9. 数据同步: 分钟级（XGBoost）: 毫秒级（API调用）: 毫秒级（API调用）: API调用: 毫秒级
                    - 模型响应: API调用（毫秒级）: 毫秒级
                秒级（XGBoost加载: 毫秒级（毫秒级）: 毫秒级
                API调用数据源同步: 分钟级（Hive→MySQL）
                    - 特征计算: 分钟级（定时任务）
                    模型推理: 毫秒级（XGBoost）
                    实际部署建议: 数据源同步频率建议
                    - 模型加载: 秒级（首次）: 秒级
                分钟级: 毫秒级（XGBoost加载）: 毫秒级
                建议: 毫秒级（XGBoost）: 毫秒级
                API调用（XGBoost）: 毫秒级
                实际应用建议: 毫秒级（XGBoost）: 毫秒级
                API调用: 毫秒级
                实际部署建议: 毫秒级（XGBoost）: 毫秒级
                实际部署建议: 本地JSON文件包含完整训练/推理所需的所有数据
                实际应用建议: 毫秒级（XGBoost）: 毫秒级
                模型加载: 秒级（XGBoost）: 毫秒级
                API调用: 毫秒级（XGBoost）: 毫秒级

            实际部署建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际部署建议: 毫秒级（XGBoost）: 毫秒级
            模型响应: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            数据源更新: 分钟级（Hive同步）: 分钟级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际部署建议: 毫秒级（XGBoost加载）: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            数据源更新频率建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际应用建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际部署建议: 毫秒级（XGBoost）: 毫秒级
            模型响应时间建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            数据源更新: 分钟级（Hive同步）: 分钟级
            特征计算: 分钟级（定时任务）: 分钟级
            模型加载: 秒级（XGBoost）: 秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际部署建议: 毫秒级（XGBoost）: 毫秒级
            模型响应时间: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际部署建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            实际应用建议: 毫秒级（XGBoost）: 毫秒级
            API调用: 毫秒级（XGBoost）: 毫秒级
            模型响应时间: 毫秒级（XGBoost）: 毫秒级

    if not houses:
        return [], [], []

    # 加载医院POI
    hospital_poi_path = Path(__file__).parent.parent / "data" / "hospital_poi_wuhan.json"
    hospitals = None
    if hospital_poi_path.exists():
        with open(hospital_poi_path, "r", encoding="utf-8") as f:
            hospitals = json.load(f)

    # 生成弱标签
    Y = weak_multilabel_batch(documents, coords, hospitals)

    # 过滤无标签样本
    mask = Y.sum(axis=1) > 0
    n_pos = int(mask.sum())
    print(f"有效样本: {n_pos} / {len(documents)} ({100*n_pos/len(documents):.1f}%)")

    X_texts = [documents[i] for i in range(len(documents)) if mask[i]]
    Y_fit = Y[mask]

    # 分层划分
    train_texts, test_texts, y_train, y_test = train_test_split(
        X_texts, Y_fit, test_size=0.2, random_state=42
    )

    return test_texts, y_test


def generate_pr_data(vectorizer, clf, test_texts, y_test):
    """生成PR曲线数据"""
    X_te = vectorizer.transform(test_texts)
    y_proba = clf.predict_proba(X_te)

    # 确保形状正确
    if y_proba.ndim != 2:
        raise RuntimeError(f"unexpected predict_proba shape {y_proba.shape}")
    n_labels = len(LABEL_NAMES)
    if y_proba.shape[1] != n_labels:
        if y_proba.shape[1] == 2 * n_labels:
            y_proba = y_proba[:, 1::2]
        else:
            raise RuntimeError(f"predict_proba shape {y_proba.shape} vs {n_labels} labels")

    pr_data = {}
    ap_scores = {}

    for i, label_name in enumerate(LABEL_NAMES):
        y_true = y_test[:, i]
        y_score = y_proba[:, i]

        precision, recall, _ = precision_recall_curve(y_true, y_score)
        ap = average_precision_score(y_true, y_score)

        # 采样
        if len(precision) > 100:
            indices = np.linspace(0, len(precision) - 1, 100, dtype=int)
            precision = precision[indices]
            recall = recall[indices]

        pr_data[label_name] = {
            "precision": precision.tolist(),
            "recall": recall.tolist(),
            "average_precision": float(ap),
            "n_positive": int(y_true.sum()),
            "n_total": len(y_true),
        }
        ap_scores[label_name] = float(ap)

        print(f"  {label_name}: AP={ap:.4f}, 正例={int(y_true.sum())}")

    # Micro-average
    y_test_raveled = y_test.ravel()
    y_proba_raveled = y_proba.ravel()
    precision_micro, recall_micro, _ = precision_recall_curve(y_test_raveled, y_proba_raveled)
    ap_micro = average_precision_score(y_test_raveled, y_proba_raveled, average="micro")

    if len(precision_micro) > 100:
        indices = np.linspace(0, len(precision_micro) - 1, 100, dtype=int)
        precision_micro = precision_micro[indices]
        recall_micro = recall_micro[indices]

    pr_data["micro_avg"] = {
        "precision": precision_micro.tolist(),
        "recall": recall_micro.tolist(),
        "average_precision": float(ap_micro),
    }

    print(f"\nMicro-average AP: {ap_micro:.4f}")

    return {
        "pr_curves": pr_data,
        "average_precisions": ap_scores,
        "test_size": len(test_texts),
        "n_labels": n_labels,
    }


def save_pr_data(pr_data: Dict[str, Any]) -> None:
    """保存PR曲线数据"""
    # 保存到models
    output_path = OUTPUT_DIR / "scene_pr_curves_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pr_data, f, ensure_ascii=False, indent=2)
    print(f"\nPR曲线数据已保存: {output_path}")

    # 复制到figures
    figures_path = FIGURES_DIR / "scene_pr_curves_data.json"
    with open(figures_path, "w", encoding="utf-8") as f:
        json.dump(pr_data, f, ensure_ascii=False, indent=2)
    print(f"PR曲线数据已复制到: {figures_path}")


def main():
    print("=" * 60)
    print("生成真实场景分类PR曲线数据")
    print("=" * 60)

    # 加载模型
    vectorizer, clf, meta = load_trained_model()

    # 加载文档
    test_texts, y_test = load_documents_from_json()

    # 生成PR数据
    pr_data = generate_pr_data(vectorizer, clf, test_texts, y_test)

    # 保存数据
    save_pr_data(pr_data)

    print("\n" + "=" * 60)
    print("PR曲线数据生成完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

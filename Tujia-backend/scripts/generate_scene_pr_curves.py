# -*- coding: utf-8 -*-
"""
生成真实场景分类PR曲线数据
=========================

从已训练的 listing_scene_tfidf.joblib 模型提取测试集预测概率，
计算真实的Precision-Recall曲线数据，替换图5-5的示意数据。

运行：在 Tujia-backend 目录下
    python scripts/generate_scene_pr_curves.py
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
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.metrics import precision_recall_curve, average_precision_score
from sklearn.model_selection import train_test_split

from app.db.database import SessionLocal
from app.ml.listing_scene_weak_labels import LABEL_NAMES, weak_multilabel_batch
from app.ml.house_tags_text import parse_house_tags
from scripts.listing_scene_pipeline import build_document, make_vectorizer

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


def load_all_documents():
    """从数据库加载所有房源文本数据"""
    from app.db.database import Listing

    db = SessionLocal()
    try:
        rows = db.query(
            Listing.unit_id,
            Listing.title,
            Listing.house_tags,
            Listing.comment_brief,
            Listing.latitude,
            Listing.longitude,
        ).all()

        documents = []
        unit_ids = []
        for r in rows:
            doc = build_document(r.title, r.house_tags, r.comment_brief)
            documents.append(doc)
            unit_ids.append(r.unit_id)

        print(f"\n从数据库加载 {len(documents)} 条房源数据")
        return documents, unit_ids
    finally:
        db.close()


def generate_weak_labels(documents: List[str], unit_ids: List[str]) -> np.ndarray:
    """生成弱监督标签"""
    # 加载医院POI数据（如果存在）
    hospital_poi_path = (
        Path(__file__).resolve().parent.parent / "data" / "hospital_poi_wuhan.json"
    )
    hospitals = None
    if hospital_poi_path.exists():
        import json as _json

        with open(hospital_poi_path, "r", encoding="utf-8") as f:
            hospitals = _json.load(f)
        print(f"已加载医院POI数据: {len(hospitals)} 家医院")

    # 获取所有房源的坐标
    db = SessionLocal()
    try:
        from app.db.database import Listing

        rows = db.query(Listing.unit_id, Listing.latitude, Listing.longitude).filter(
            Listing.unit_id.in_(unit_ids)
        ).all()
        coord_map = {r.unit_id: (r.latitude, r.longitude) for r in rows}
    finally:
        db.close()

    coords = [coord_map.get(uid, (None, None)) for uid in unit_ids]
    Y = weak_multilabel_batch(documents, coords, hospitals)
    print(f"弱标签生成完成: {Y.shape}")
    return Y


def generate_pr_curve_data(
    vectorizer, clf, documents: List[str], Y: np.ndarray
) -> Dict[str, Any]:
    """生成PR曲线数据"""
    # 过滤掉无标签的样本（与训练时一致）
    mask = Y.sum(axis=1) > 0
    n_pos = int(mask.sum())
    n_all = len(documents)
    print(f"\n有效样本: {n_pos} / {n_all} (至少有一个弱标签)")

    X_texts = [documents[i] for i in range(n_all) if mask[i]]
    Y_fit = Y[mask]

    # 使用相同的划分（random_state=42）
    X_train, X_test, y_train, y_test = train_test_split(
        X_texts, Y_fit, test_size=0.2, random_state=42
    )

    print(f"测试集大小: {len(X_test)}")

    # 转换测试集
    X_te = vectorizer.transform(X_test)

    # 获取预测概率
    y_proba = clf.predict_proba(X_te)

    # 确保概率矩阵形状正确
    if y_proba.ndim != 2:
        raise RuntimeError(f"unexpected predict_proba shape {y_proba.shape}")
    n_labels = len(LABEL_NAMES)
    if y_proba.shape[1] != n_labels:
        if y_proba.shape[1] == 2 * n_labels:
            y_proba = y_proba[:, 1::2]
        else:
            raise RuntimeError(
                f"predict_proba shape {y_proba.shape} vs {n_labels} labels"
            )

    # 为每个标签计算PR曲线
    pr_data = {}
    ap_scores = {}

    for i, label_name in enumerate(LABEL_NAMES):
        y_true = y_test[:, i]
        y_score = y_proba[:, i]

        # 计算PR曲线
        precision, recall, thresholds = precision_recall_curve(y_true, y_score)

        # 计算平均精度
        ap = average_precision_score(y_true, y_score)
        ap_scores[label_name] = float(ap)

        # 采样以减少数据点数量（保留100个点）
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

        print(f"  {label_name}: AP={ap:.4f}, 正例={int(y_true.sum())}")

    # 计算Micro-average PR曲线
    y_test_raveled = y_test.ravel()
    y_proba_raveled = y_proba.ravel()
    precision_micro, recall_micro, _ = precision_recall_curve(
        y_test_raveled, y_proba_raveled
    )
    ap_micro = average_precision_score(y_test_raveled, y_proba_raveled, average="micro")

    # 采样
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
        "test_size": len(X_test),
        "n_labels": n_labels,
    }


def save_pr_data(pr_data: Dict[str, Any]) -> None:
    """保存PR曲线数据"""
    output_path = OUTPUT_DIR / "scene_pr_curves_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pr_data, f, ensure_ascii=False, indent=2)
    print(f"\nPR曲线数据已保存: {output_path}")

    # 同时保存到figures目录供图表生成使用
    figures_path = FIGURES_DIR / "scene_pr_curves_data.json"
    with open(figures_path, "w", encoding="utf-8") as f:
        json.dump(pr_data, f, ensure_ascii=False, indent=2)
    print(f"PR曲线数据已复制到: {figures_path}")

    # 生成CSV格式便于查看
    csv_path = OUTPUT_DIR / "scene_average_precisions.csv"
    ap_data = pr_data["average_precisions"]
    df = pd.DataFrame(
        [(k, v) for k, v in ap_data.items()],
        columns=["scene", "average_precision"],
    )
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Average Precision CSV: {csv_path}")


def main():
    print("=" * 60)
    print("生成真实场景分类PR曲线数据")
    print("=" * 60)

    # 加载模型
    vectorizer, clf, meta = load_trained_model()

    # 加载文档
    documents, unit_ids = load_all_documents()

    # 生成弱标签
    Y = generate_weak_labels(documents, unit_ids)

    # 生成PR曲线数据
    pr_data = generate_pr_curve_data(vectorizer, clf, documents, Y)

    # 保存数据
    save_pr_data(pr_data)

    print("\n" + "=" * 60)
    print("PR曲线数据生成完成")
    print("=" * 60)
    print("\n你可以使用此数据更新图5-5的PR曲线图")


if __name__ == "__main__":
    main()

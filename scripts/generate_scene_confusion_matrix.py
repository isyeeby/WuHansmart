# -*- coding: utf-8 -*-
"""
生成真实场景分类混淆矩阵数据
=============================

从已训练的 listing_scene_tfidf.joblib 模型提取测试集预测结果，
生成真实的混淆矩阵数据，替换图5-6的示意数据。

注意：多标签分类的混淆矩阵处理方式：
- 将概率最高的类别作为预测类别（单标签化）
- 对于多标签样本，每个正标签都计入对应类别的正例

运行：在 Tujia-backend 目录下
    python scripts/generate_scene_confusion_matrix.py
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from app.db.database import SessionLocal
from app.ml.listing_scene_weak_labels import LABEL_NAMES, weak_multilabel_batch
from app.ml.house_tags_text import parse_house_tags
from scripts.listing_scene_pipeline import build_document

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"
FIGURES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 中文标签映射（用于论文图表）
LABEL_NAMES_CN = {
    "couple": "情侣出游",
    "family": "家庭亲子",
    "business": "商务差旅",
    "exam": "学生考研",
    "team_party": "团建聚会",
    "medical": "医疗陪护",
    "pet_friendly": "宠物友好",
    "long_stay": "长租",
}


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
        with open(hospital_poi_path, "r", encoding="utf-8") as f:
            hospitals = json.load(f)
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


def generate_confusion_matrix(
    vectorizer, clf, documents: List[str], Y: np.ndarray
) -> Dict[str, Any]:
    """生成混淆矩阵数据"""
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

    # 为每个类别生成分类结果（单标签化处理）
    # 对于多标签样本，我们统计每个标签的预测情况
    per_label_results = {}

    for i, label_name in enumerate(LABEL_NAMES):
        y_true_binary = y_test[:, i]
        y_score = y_proba[:, i]
        y_pred_binary = (y_score >= 0.5).astype(int)  # 阈值0.5

        # 计算TP, FP, TN, FN
        tp = int((y_true_binary * y_pred_binary).sum())
        fp = int(((1 - y_true_binary) * y_pred_binary).sum())
        tn = int(((1 - y_true_binary) * (1 - y_pred_binary)).sum())
        fn = int((y_true_binary * (1 - y_pred_binary)).sum())

        # 计算指标
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        per_label_results[label_name] = {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "n_positive": int(y_true_binary.sum()),
            "n_predicted_positive": int(y_pred_binary.sum()),
        }

        print(f"  {LABEL_NAMES_CN[label_name]}: P={precision:.3f}, R={recall:.3f}, F1={f1:.3f}")

    # 生成"单标签化"的混淆矩阵
    # 对于每个样本，取概率最高的类别作为预测类别
    # 对于真实标签，取第一个正标签（如果有多标签）

    y_pred_argmax = np.argmax(y_proba, axis=1)

    # 对于真实标签，我们需要处理多标签情况
    # 方法：对于多标签样本，在每个正标签类别中都计数

    # 构建混淆矩阵（8x8）
    cm = np.zeros((n_labels, n_labels), dtype=int)

    for sample_idx in range(len(y_test)):
        true_labels = np.where(y_test[sample_idx] == 1)[0]
        pred_label = y_pred_argmax[sample_idx]

        if len(true_labels) == 0:
            continue

        # 对于每个真实标签，都记录预测结果
        for true_label in true_labels:
            cm[true_label, pred_label] += 1

    print(f"\n混淆矩阵总和: {cm.sum()} (多标签计数，可能大于样本数)")
    print(f"样本数: {len(y_test)}")

    # 转换为列表格式保存
    cm_list = cm.tolist()

    # 计算每个类别的分类准确率
    per_class_accuracy = {}
    for i, label_name in enumerate(LABEL_NAMES):
        class_total = cm[i, :].sum()
        class_correct = cm[i, i]
        accuracy = class_correct / class_total if class_total > 0 else 0
        per_class_accuracy[label_name] = {
            "accuracy": float(accuracy),
            "correct": int(class_correct),
            "total": int(class_total),
        }

    return {
        "confusion_matrix": cm_list,
        "label_names": LABEL_NAMES,
        "label_names_cn": [LABEL_NAMES_CN[name] for name in LABEL_NAMES],
        "per_label_results": per_label_results,
        "per_class_accuracy": per_class_accuracy,
        "test_size": len(y_test),
        "total_counted": int(cm.sum()),
    }


def save_confusion_data(cm_data: Dict[str, Any]) -> None:
    """保存混淆矩阵数据"""
    output_path = OUTPUT_DIR / "scene_confusion_matrix_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cm_data, f, ensure_ascii=False, indent=2)
    print(f"\n混淆矩阵数据已保存: {output_path}")

    # 同时保存到figures目录
    figures_path = FIGURES_DIR / "scene_confusion_matrix_data.json"
    with open(figures_path, "w", encoding="utf-8") as f:
        json.dump(cm_data, f, ensure_ascii=False, indent=2)
    print(f"混淆矩阵数据已复制到: {figures_path}")

    # 生成CSV格式的混淆矩阵
    csv_path = FIGURES_DIR / "scene_confusion_matrix.csv"
    cm = np.array(cm_data["confusion_matrix"])
    df = pd.DataFrame(
        cm,
        index=[f"真实_{LABEL_NAMES_CN[name]}" for name in LABEL_NAMES],
        columns=[f"预测_{LABEL_NAMES_CN[name]}" for name in LABEL_NAMES],
    )
    df.to_csv(csv_path, encoding="utf-8-sig")
    print(f"混淆矩阵CSV: {csv_path}")

    # 打印摘要表格
    print("\n" + "=" * 60)
    print("各类别分类性能汇总")
    print("=" * 60)
    print(f"{'类别':<12} {'P':<8} {'R':<8} {'F1':<8} {'支持度':<8}")
    print("-" * 60)
    for name in LABEL_NAMES:
        cn_name = LABEL_NAMES_CN[name]
        r = cm_data["per_label_results"][name]
        print(
            f"{cn_name:<12} {r['precision']:<8.3f} {r['recall']:<8.3f} "
            f"{r['f1_score']:<8.3f} {r['n_positive']:<8}"
        )

    # 打印混淆矩阵
    print("\n" + "=" * 60)
    print("混淆矩阵（对角线为正确预测）")
    print("=" * 60)
    print(f"{'真实\\预测':<10}", end="")
    for name in LABEL_NAMES:
        print(f"{LABEL_NAMES_CN[name][:4]:<8}", end="")
    print()
    print("-" * 70)
    for i, name in enumerate(LABEL_NAMES):
        print(f"{LABEL_NAMES_CN[name][:4]:<10}", end="")
        for j in range(len(LABEL_NAMES)):
            print(f"{cm[i, j]:<8}", end="")
        print()


def main():
    print("=" * 60)
    print("生成真实场景分类混淆矩阵数据")
    print("=" * 60)

    # 加载模型
    vectorizer, clf, meta = load_trained_model()

    # 加载文档
    documents, unit_ids = load_all_documents()

    # 生成弱标签
    Y = generate_weak_labels(documents, unit_ids)

    # 生成混淆矩阵
    cm_data = generate_confusion_matrix(vectorizer, clf, documents, Y)

    # 保存数据
    save_confusion_data(cm_data)

    print("\n" + "=" * 60)
    print("混淆矩阵数据生成完成")
    print("=" * 60)
    print("\n你可以使用此数据更新图5-6的混淆矩阵图")


if __name__ == "__main__":
    main()

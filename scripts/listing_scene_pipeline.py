# -*- coding: utf-8 -*-
"""
房源场景多标签：弱监督 + 分词 TF-IDF + OneVsRest 逻辑回归，一键训练并回写 listings.scene_scores。

默认：训练 → 保存 models/listing_scene_tfidf.joblib → 全量预测写库。

需要写库时若缺列会自动 ALTER；亦可手动执行 sql/add_listing_scene_scores.sql、
sql/add_listing_nearest_hospital_km.sql、sql/add_listing_nearest_hospital_name.sql。回写时会根据 data/hospital_poi_wuhan.json
计算并写入 listings.nearest_hospital_km、nearest_hospital_name，并在弱标签中与医疗关键词 OR 叠加（≤2km → medical）。

用法（在 Tujia-backend 目录）:
    python scripts/listing_scene_pipeline.py
    python scripts/listing_scene_pipeline.py --dry-run
    python scripts/listing_scene_pipeline.py --skip-apply
    python scripts/listing_scene_pipeline.py --skip-train
    python scripts/listing_scene_pipeline.py --mode char
    python scripts/listing_scene_pipeline.py --ensure-column   # 仅加列后退出
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np

warnings.filterwarnings("ignore")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app.db.database import Listing, SessionLocal, engine
from app.ml.house_tags_text import parse_house_tags
from app.ml.listing_scene_text import jieba_analyzer
from app.ml.hospital_poi import batch_nearest_hospital_km_and_name, load_hospital_pois
from app.ml.listing_scene_weak_labels import LABEL_NAMES, WEAK_RULE_VERSION, weak_multilabel_batch

HOSPITAL_POI_PATH = Path(__file__).resolve().parent.parent / "data" / "hospital_poi_wuhan.json"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_BASENAME = "listing_scene_tfidf"
MODEL_PATH = OUTPUT_DIR / f"{MODEL_BASENAME}.joblib"
META_PATH = OUTPUT_DIR / f"{MODEL_BASENAME}_meta.json"
BATCH_COMMIT = 200


def ensure_listings_table_and_column(require_scene_column: bool) -> None:
    insp = inspect(engine)
    if not insp.has_table("listings"):
        print("错误: 数据库中不存在表 listings，请先导入房源数据。")
        sys.exit(1)
    cols = {c["name"] for c in insp.get_columns("listings")}
    if require_scene_column and "scene_scores" not in cols:
        print(
            "错误: 表 listings 缺少列 scene_scores。\n"
            "请执行: sql/add_listing_scene_scores.sql\n"
            "或运行: python scripts/listing_scene_pipeline.py --ensure-column （仅加列，可再跑默认命令）"
        )
        sys.exit(1)


def migrate_scene_scores_column_if_missing() -> None:
    """无 scene_scores 时执行 ALTER（MySQL / SQLite）。"""
    insp = inspect(engine)
    if not insp.has_table("listings"):
        return
    cols = {c["name"] for c in insp.get_columns("listings")}
    if "scene_scores" in cols:
        return
    d = engine.dialect.name
    with engine.begin() as conn:
        if d == "mysql":
            conn.execute(
                text(
                    "ALTER TABLE listings ADD COLUMN scene_scores TEXT NULL "
                    "COMMENT 'scene labels JSON'"
                )
            )
        else:
            conn.execute(text("ALTER TABLE listings ADD COLUMN scene_scores TEXT"))
    print("已自动添加列 scene_scores")


def migrate_nearest_hospital_km_column_if_missing() -> None:
    """无 nearest_hospital_km 时执行 ALTER（MySQL / SQLite）。"""
    insp = inspect(engine)
    if not insp.has_table("listings"):
        return
    cols = {c["name"] for c in insp.get_columns("listings")}
    if "nearest_hospital_km" in cols:
        return
    d = engine.dialect.name
    with engine.begin() as conn:
        if d == "mysql":
            conn.execute(
                text(
                    "ALTER TABLE listings ADD COLUMN nearest_hospital_km DECIMAL(9,3) NULL "
                    "COMMENT '至最近POI医院直线距离km'"
                )
            )
        else:
            conn.execute(text("ALTER TABLE listings ADD COLUMN nearest_hospital_km REAL"))
    print("已自动添加列 nearest_hospital_km")


def migrate_nearest_hospital_name_column_if_missing() -> None:
    """无 nearest_hospital_name 时执行 ALTER（MySQL / SQLite）。"""
    insp = inspect(engine)
    if not insp.has_table("listings"):
        return
    cols = {c["name"] for c in insp.get_columns("listings")}
    if "nearest_hospital_name" in cols:
        return
    d = engine.dialect.name
    with engine.begin() as conn:
        if d == "mysql":
            conn.execute(
                text(
                    "ALTER TABLE listings ADD COLUMN nearest_hospital_name VARCHAR(200) NULL "
                    "COMMENT '最近POI医院名称'"
                )
            )
        else:
            conn.execute(text("ALTER TABLE listings ADD COLUMN nearest_hospital_name VARCHAR(200)"))
    print("已自动添加列 nearest_hospital_name")


def build_document(title: Any, house_tags: Any, comment_brief: Any) -> str:
    parts: List[str] = []
    if title:
        parts.append(str(title).strip())
    tag_texts = parse_house_tags(house_tags)
    if tag_texts:
        parts.append(" ".join(tag_texts))
    if comment_brief:
        parts.append(str(comment_brief).strip())
    return " ".join(parts)


def make_vectorizer(mode: str):
    from sklearn.feature_extraction.text import TfidfVectorizer

    # min_df=1 避免小样本语料 vocabulary 为空；大库上噪声略增可接受
    if mode == "char":
        return TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            min_df=1,
            max_df=0.98,
            max_features=80000,
            sublinear_tf=True,
        )

    return TfidfVectorizer(
        analyzer=jieba_analyzer,
        min_df=1,
        max_df=0.98,
        max_features=100000,
        sublinear_tf=True,
    )


def train_model(
    documents: List[str],
    Y: np.ndarray,
    mode: str,
) -> Tuple[Any, Any, Dict[str, Any], Dict[str, Any]]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, hamming_loss
    from sklearn.model_selection import train_test_split
    from sklearn.multiclass import OneVsRestClassifier

    mask = Y.sum(axis=1) > 0
    n_pos = int(mask.sum())
    n_all = len(documents)
    print(f"弱标签: 至少命中一类的样本 {n_pos} / {n_all} ({100 * n_pos / max(n_all, 1):.1f}%)")
    if n_pos < 20:
        print("错误: 弱标签正样本过少，请扩充 app/ml/listing_scene_weak_labels.py 中的关键词。")
        sys.exit(1)

    X_texts = [documents[i] for i in range(n_all) if mask[i]]
    Y_fit = Y[mask]

    X_train, X_test, y_train, y_test = train_test_split(
        X_texts, Y_fit, test_size=0.2, random_state=42
    )

    vectorizer = make_vectorizer(mode)
    X_tr = vectorizer.fit_transform(X_train)
    X_te = vectorizer.transform(X_test)

    # Windows + 非 ASCII 用户目录下 joblib/loky 并行易触发 UnicodeEncodeError，故 OvR 串行
    clf = OneVsRestClassifier(
        LogisticRegression(
            class_weight="balanced",
            max_iter=500,
            solver="saga",
            n_jobs=1,
            random_state=42,
        ),
        n_jobs=1,
    )
    clf.fit(X_tr, y_train)

    y_pred = clf.predict(X_te)
    metrics = {
        "hamming_loss": float(hamming_loss(y_test, y_pred)),
        "f1_micro": float(f1_score(y_test, y_pred, average="micro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "mode": mode,
    }
    print("验证集指标:", json.dumps(metrics, ensure_ascii=False, indent=2))

    bundle = {
        "vectorizer": vectorizer,
        "clf": clf,
        "label_names": LABEL_NAMES,
        "weak_rule_version": WEAK_RULE_VERSION,
        "feature_mode": mode,
    }
    return vectorizer, clf, metrics, bundle


def predict_proba_dicts(
    clf: Any,
    vectorizer: Any,
    documents: List[str],
    label_names: List[str],
) -> List[Dict[str, float]]:
    X = vectorizer.transform(documents)
    P = clf.predict_proba(X)
    # (n_samples, n_labels) 正类概率
    if P.ndim != 2:
        raise RuntimeError(f"unexpected predict_proba shape {P.shape}")
    n_labels = len(label_names)
    if P.shape[1] != n_labels:
        # 极少数 sklearn 版本返回 (n, 2*n_labels)
        if P.shape[1] == 2 * n_labels:
            P = P[:, 1::2]
        else:
            raise RuntimeError(f"predict_proba shape {P.shape} vs {n_labels} labels")

    out: List[Dict[str, float]] = []
    for i in range(P.shape[0]):
        out.append({label_names[j]: round(float(P[i, j]), 4) for j in range(n_labels)})
    return out


def save_artifacts(bundle: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    meta = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(MODEL_PATH),
        "weak_rule_version": WEAK_RULE_VERSION,
        "label_names": LABEL_NAMES,
        **metrics,
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存模型: {MODEL_PATH}")
    print(f"已保存元数据: {META_PATH}")


def apply_to_db(
    vectorizer: Any,
    clf: Any,
    all_docs: List[str],
    all_uids: List[str],
    dry_run: bool,
    label_names: List[str],
    nearest_km_list: List[Optional[float]],
    nearest_hospital_name_list: List[Optional[str]],
) -> None:
    db = SessionLocal()
    updated = 0
    try:
        for start in range(0, len(all_uids), BATCH_COMMIT):
            batch_uids = all_uids[start : start + BATCH_COMMIT]
            batch_docs = all_docs[start : start + BATCH_COMMIT]
            scores_list = predict_proba_dicts(clf, vectorizer, batch_docs, label_names)
            if dry_run:
                updated += len(batch_uids)
                continue
            for j, (uid, scores) in enumerate(zip(batch_uids, scores_list)):
                row = db.query(Listing).filter(Listing.unit_id == uid).first()
                if row:
                    row.scene_scores = scores
                    gi = start + j
                    if gi < len(nearest_km_list):
                        row.nearest_hospital_km = nearest_km_list[gi]
                    if gi < len(nearest_hospital_name_list):
                        row.nearest_hospital_name = nearest_hospital_name_list[gi]
                    updated += 1
            db.commit()
            print(f"  已写库 {min(start + BATCH_COMMIT, len(all_uids))} / {len(all_uids)}")
    finally:
        db.close()
    print(f"回写完成: {updated} 条" + (" (dry-run 未提交)" if dry_run else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="房源场景 TF-IDF + LR 流水线")
    parser.add_argument("--dry-run", action="store_true", help="训练后不回写数据库")
    parser.add_argument("--skip-apply", action="store_true", help="仅训练与保存模型")
    parser.add_argument("--skip-train", action="store_true", help="加载已有模型并回写")
    parser.add_argument(
        "--mode",
        choices=("word", "char"),
        default="word",
        help="word=jieba 分词；char=字 n-gram（无 jieba）",
    )
    parser.add_argument(
        "--ensure-column",
        action="store_true",
        help="仅检查/添加 scene_scores、nearest_hospital_km、nearest_hospital_name 列后退出",
    )
    args = parser.parse_args()

    ensure_listings_table_and_column(require_scene_column=False)
    if args.ensure_column:
        migrate_scene_scores_column_if_missing()
        migrate_nearest_hospital_km_column_if_missing()
        migrate_nearest_hospital_name_column_if_missing()
        print("加列检查完成。")
        sys.exit(0)

    need_column = not args.dry_run and not args.skip_apply
    if need_column:
        migrate_scene_scores_column_if_missing()
        migrate_nearest_hospital_km_column_if_missing()
        migrate_nearest_hospital_name_column_if_missing()
    ensure_listings_table_and_column(require_scene_column=need_column)

    # 全表文档（与训练用同一套 build_document；回写覆盖所有有文本行）
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
    finally:
        db.close()

    if not rows:
        print("错误: listings 表无数据。")
        sys.exit(1)

    hospitals = load_hospital_pois(HOSPITAL_POI_PATH)
    if hospitals:
        print(f"已加载医院 POI: {len(hospitals)} 条 ({HOSPITAL_POI_PATH.name})")
    else:
        print(f"未加载医院 POI（缺少或无效 {HOSPITAL_POI_PATH}），仅使用文本弱标签；距离列将写 NULL。")

    all_uids: List[str] = []
    all_docs: List[str] = []
    all_lats: List[Any] = []
    all_lons: List[Any] = []
    for unit_id, title, house_tags, comment_brief, latitude, longitude in rows:
        doc = build_document(title, house_tags, comment_brief)
        if not doc:
            doc = str(title or "").strip() or " "
        all_uids.append(str(unit_id).strip())
        all_docs.append(doc)
        all_lats.append(latitude)
        all_lons.append(longitude)

    nearest_km_list, nearest_hospital_name_list = batch_nearest_hospital_km_and_name(
        all_lats, all_lons, hospitals
    )

    bundle: Dict[str, Any]
    if args.skip_train:
        if not MODEL_PATH.is_file():
            print(f"错误: 未找到模型文件 {MODEL_PATH}，无法 --skip-train")
            sys.exit(1)
        bundle = joblib.load(MODEL_PATH)
        vectorizer = bundle["vectorizer"]
        clf = bundle["clf"]
        print("已加载模型，跳过训练。")
    else:
        Y_all = weak_multilabel_batch(all_docs, all_lats, all_lons, hospitals)
        vectorizer, clf, metrics, bundle = train_model(all_docs, Y_all, args.mode)
        save_artifacts(bundle, metrics)

    label_names = list(bundle.get("label_names") or LABEL_NAMES)

    if not args.skip_apply:
        apply_to_db(
            vectorizer,
            clf,
            all_docs,
            all_uids,
            dry_run=args.dry_run,
            label_names=label_names,
            nearest_km_list=nearest_km_list,
            nearest_hospital_name_list=nearest_hospital_name_list,
        )
    else:
        print("已跳过回写 (--skip-apply)")


if __name__ == "__main__":
    main()

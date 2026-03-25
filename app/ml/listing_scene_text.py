# -*- coding: utf-8 -*-
"""房源场景 TF-IDF：分词 analyzer 须在此模块顶层定义，便于 joblib 反序列化。"""
from __future__ import annotations

from typing import List


def jieba_analyzer(doc: str) -> List[str]:
    import jieba

    return list(jieba.cut(doc))

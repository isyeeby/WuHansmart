# -*- coding: utf-8 -*-
"""从 listings.house_tags JSON 解析可读标签文本（训练脚本与流水线共用）。"""
from __future__ import annotations

import json
from typing import Any, List


def parse_house_tags(house_tags: Any) -> List[str]:
    """解析 house_tags（JSON 或列表），返回标签文本列表。"""
    if not house_tags:
        return []
    try:
        tags_list = json.loads(house_tags) if isinstance(house_tags, str) else house_tags
        if not isinstance(tags_list, list):
            return []
        result: List[str] = []
        for tag in tags_list:
            if isinstance(tag, dict) and "tagText" in tag:
                tag_text = tag["tagText"]
                if isinstance(tag_text, dict) and "text" in tag_text:
                    result.append(str(tag_text["text"]))
                elif isinstance(tag_text, str):
                    result.append(tag_text)
            elif isinstance(tag, str):
                result.append(tag)
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return []

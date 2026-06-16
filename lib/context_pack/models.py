"""Context Pack 数据模型。

Project Context Pack 是从 project.json + scripts/episode_1.json 中
确定性提取的"剧本理解包"，供多个 agent（编导/导演/资产/分镜/视频提示词/预检/审片）
共享同一份剧本理解。

所有字段均由 builder 确定性提取，不做 AI 总结。
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1


def empty_context_pack(content_mode: str = "ad") -> dict[str, Any]:
    """返回空 context pack 骨架（非 ad 模式或数据缺失时使用）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "content_mode": content_mode,
        "source_script": "",
        "logline": "",
        "theme": "",
        "style_bible": {
            "aspect_ratio": "9:16",
            "style": "",
            "style_description": "",
            "visual_rules": [],
            "forbidden_changes": [],
        },
        "characters_with_aliases": [],
        "scenes": [],
        "props": [],
        "products": [],
        "shot_intent_map": [],
        "asset_reference_state": {
            "missing_assets": [],
            "assets_without_sheet": [],
            "shots_without_references": [],
        },
    }

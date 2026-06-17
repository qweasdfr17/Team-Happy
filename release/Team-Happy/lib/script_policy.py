"""剧本处理策略（Script Policy）。

控制剧本原文是否允许被 AI 改写。策略存储在 project.json 顶层 ``script_policy`` 字段。

模式：
- ``preserve``（默认）：严禁改原始剧本文字；只能切分、提取、生成结构化字段和提示词
- ``suggest_rewrite``：只生成改稿建议（写入 proposals/），不写回正式剧本
- ``rewrite_approved``：用户确认后才允许改写（后续实现）
"""

from __future__ import annotations

from typing import Literal

ScriptPolicyMode = Literal["preserve", "suggest_rewrite", "rewrite_approved"]

DEFAULT_SCRIPT_POLICY: dict = {
    "mode": "preserve",
}

VALID_MODES: frozenset[str] = frozenset({"preserve", "suggest_rewrite", "rewrite_approved"})


def resolve_script_policy(project: dict) -> dict:
    """从 project.json 读取 script_policy，缺失时返回默认 preserve。"""
    policy = project.get("script_policy")
    if not isinstance(policy, dict):
        return dict(DEFAULT_SCRIPT_POLICY)
    mode = policy.get("mode", "preserve")
    if mode not in VALID_MODES:
        mode = "preserve"
    return {"mode": mode}


def is_preserve_mode(project: dict) -> bool:
    """是否处于 preserve（原文保护）模式。"""
    return resolve_script_policy(project)["mode"] == "preserve"


def is_suggest_mode(project: dict) -> bool:
    """是否处于 suggest_rewrite（仅建议）模式。"""
    return resolve_script_policy(project)["mode"] == "suggest_rewrite"


def validate_script_policy(policy: object) -> dict:
    """校验并规范化 script_policy dict，非法值回退 preserve。"""
    if not isinstance(policy, dict):
        return dict(DEFAULT_SCRIPT_POLICY)
    mode = policy.get("mode", "preserve")
    return {"mode": mode if mode in VALID_MODES else "preserve"}


# ── prompt 注入 ──────────────────────────────────────────────────────────

PRESERVE_PROMPT_TAIL = """\
剧本保护策略（preserve 模式）：
- 原始剧本文字**不得润色、不得补写、不得删改**。
- 你只能做：切分集/镜边界、提取角色/场景/道具名称、生成 image_prompt 和 video_prompt。
- story_beats / hook / title 可以基于原文归纳，但不能编造原文不存在的情节。
- 如果某段原文不适合切镜，宁可保持原文完整，也不要改写后切镜。"""

SUGGEST_REWRITE_PROMPT_TAIL = """\
剧本建议模式（suggest_rewrite）：
- 你可以生成改稿建议，但**不得直接写回正式剧本**。
- 改稿建议写入 proposals/ 路径。
- 原始剧本保持原样。"""

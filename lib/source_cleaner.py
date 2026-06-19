"""Source text cleaner — strip embedded video/image prompt blocks from source text.

This is a **fallback** layer.  The primary defence is SkipJsonSchema (LLM never sees
the prompt fields).  This cleaner handles edge cases:

- User-uploaded screenplays that contain AI-generated prompt sections
- Copy-pasted text that includes old prompt templates
- Any text that gets into the normalize / planning pipeline before other guards

Only block-level prompt patterns are stripped — individual words like "action" or
"prompt" that appear in normal dialogue are left alone.
"""

from __future__ import annotations

import re

# ── Block-level prompt patterns (match whole sections, not single words) ──

# 【图片引用声明】 ... until next 【section】 or double-newline paragraph break
_IMAGE_DECL_BLOCK = re.compile(
    r"【图片引用声明】[^\n]*\n(?:.*\n)*?(?=【|$)",
    re.MULTILINE,
)

# 【分镜X | 时长 Xs】... until next --- or 【分镜 or end
_FENJING_BLOCK = re.compile(
    r"【分镜\d+ \| 时长 \d+s】.*?(?=---\n【分镜|\n【分镜|$)",
    re.MULTILINE | re.DOTALL,
)

# Section headers that mark the start of prompt template blocks
_PROMPT_SECTION_PATTERNS = [
    # Chinese prompt section headers followed by their content blocks
    re.compile(r"^视频提示词[：:][^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^AI视频提示词[：:][^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^运镜提示词[：:][^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^镜头提示词[：:][^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^image_prompt[：:\s]*\n(?:\s+-.*\n?)*", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^video_prompt[：:\s]*\n(?:\s+-.*\n?)*", re.MULTILINE | re.IGNORECASE),
    # ai-video-prompt template sections
    re.compile(r"^【基础设定】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^【画风】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^【场景光影基调】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^【负面约束】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^【全局视频要求】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    re.compile(r"^【目标情绪】[^\n]*(?:\n(?!\n).*)*", re.MULTILINE),
    # YAML-style structured prompt headings
    re.compile(r"^action\s*:\s*[^\n]*\n(?:^\s+.*\n?)*", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^camera_motion\s*:\s*[^\n]*\n(?:^\s+.*\n?)*", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^ambiance_audio\s*:\s*[^\n]*\n(?:^\s+.*\n?)*", re.MULTILINE | re.IGNORECASE),
    # Reference video shot headers
    re.compile(r"^Shot \d+\s*\(\d+s\)\s*:[^\n]*", re.MULTILINE),
]


def strip_video_prompts(text: str) -> str:
    """Remove embedded video/image prompt blocks from source text.

    Returns cleaned text.  Only block-level patterns are removed;
    ordinary words like "action" or "prompt" in story text are preserved.
    """
    cleaned = text

    # 1) Remove ai-video-prompt template blocks
    cleaned = _IMAGE_DECL_BLOCK.sub("", cleaned)
    cleaned = _FENJING_BLOCK.sub("", cleaned)

    # 2) Remove known prompt section patterns
    for pattern in _PROMPT_SECTION_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # 3) Collapse multiple blank lines created by removals
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 4) Only strip leading whitespace — preserve trailing content (newlines matter for file boundaries)
    cleaned = cleaned.lstrip()

    return cleaned


__all__ = ["strip_video_prompts"]

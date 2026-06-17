"""Prompt Library — 精品提示词库。

可迁移、可编辑、可被 agent 读取的提示词模板库。
支持从本地 JSON 文件加载，按 category/tags/query 简单检索。
"""

from lib.prompt_library.loader import load_prompt_library, template_list
from lib.prompt_library.models import PromptTemplate
from lib.prompt_library.resolver import resolve_prompts

__all__ = [
    "load_prompt_library",
    "PromptTemplate",
    "resolve_prompts",
    "template_list",
]

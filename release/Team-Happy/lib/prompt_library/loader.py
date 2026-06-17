"""Prompt Library 加载器。

加载内置模板（builtins/*.json）+ 可选项目级自定义模板。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.prompt_library.models import PromptTemplate

_BUILTINS_DIR = Path(__file__).parent / "builtins"


def load_builtins() -> list[PromptTemplate]:
    """加载所有内置模板。"""
    templates: list[PromptTemplate] = []
    if not _BUILTINS_DIR.is_dir():
        return templates
    for f in sorted(_BUILTINS_DIR.glob("*.json")):
        templates.extend(_load_json_file(f, source="builtin"))
    return templates


def load_custom(project_path: Path | None) -> list[PromptTemplate]:
    """加载项目级自定义模板（context/prompt_library/*.json）。

    如果 project_path 为 None 或目录不存在，返回空列表。
    """
    if project_path is None:
        return []
    custom_dir = project_path / "context" / "prompt_library"
    if not custom_dir.is_dir():
        return []
    templates: list[PromptTemplate] = []
    for f in sorted(custom_dir.glob("*.json")):
        templates.extend(_load_json_file(f, source="custom"))
    return templates


def load_prompt_library(project_path: Path | None = None) -> dict[str, PromptTemplate]:
    """加载完整提示词库：builtins + 项目自定义。

    自定义模板的 id 与 builtin 冲突时，自定义覆盖 builtin。
    返回 {id: PromptTemplate} 字典。
    """
    lib: dict[str, PromptTemplate] = {}
    for t in load_builtins():
        lib[t.id] = t
    for t in load_custom(project_path):
        lib[t.id] = t  # 自定义覆盖 builtin
    return lib


def _load_json_file(filepath: Path, source: str) -> list[PromptTemplate]:
    """从单个 JSON 文件加载模板列表。跳过解析失败的文件。"""
    try:
        raw = json.loads(filepath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    templates: list[PromptTemplate] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        t = PromptTemplate.from_dict(entry)
        # source 由加载器覆盖，不信任文件内的值
        t.source = source
        templates.append(t)
    return templates


def template_list(lib: dict[str, PromptTemplate]) -> list[dict[str, Any]]:
    """将模板字典转成 list[dict]，按 priority 降序排列。"""
    items = sorted(lib.values(), key=lambda t: t.priority, reverse=True)
    return [t.to_dict() for t in items]

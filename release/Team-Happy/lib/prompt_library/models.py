"""Prompt Library 数据模型。

每个模板是一条可检索的提示词条目，支持按 category / tags / query 简单检索。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """单条提示词模板。"""

    id: str
    category: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    language: str = "zh"
    content: str = ""
    negative: str = ""
    notes: str = ""
    source: str = "builtin"  # "builtin" | "custom"
    priority: int = 50
    format_type: str = "plain"
    variables: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> PromptTemplate:
        return cls(
            id=str(d.get("id", "")),
            category=str(d.get("category", "")),
            title=str(d.get("title", "")),
            tags=[t for t in d.get("tags", []) if isinstance(t, str)],
            language=str(d.get("language", "zh")),
            content=str(d.get("content", "")),
            negative=str(d.get("negative", "")),
            notes=str(d.get("notes", "")),
            source=str(d.get("source", "builtin")),
            priority=int(d.get("priority", 50)),
            format_type=str(d.get("format_type", "plain")),
            variables=[v for v in d.get("variables", []) if isinstance(v, str)],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "tags": self.tags,
            "language": self.language,
            "content": self.content,
            "negative": self.negative,
            "notes": self.notes,
            "source": self.source,
            "priority": self.priority,
            "format_type": self.format_type,
            "variables": self.variables,
        }

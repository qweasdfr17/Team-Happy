"""Prompt Library 检索器。

按 category / tags / query 简单检索，返回最相关的模板。
不使用 AI，不使用向量数据库。
"""

from __future__ import annotations

from lib.prompt_library.models import PromptTemplate


def _score_template(
    template: PromptTemplate,
    tags: list[str] | None,
    query_lower: str,
) -> int:
    """计算模板对当前请求的相关性分数。

    - tags 命中：每个匹配 +10
    - query 命中 title：+5
    - query 命中 content/notes：+3
    - priority：直接加分（0–100）
    """
    score = template.priority

    if tags:
        tag_set = {t.lower() for t in template.tags}
        for tag in tags:
            if tag.lower().strip() in tag_set:
                score += 10

    if query_lower:
        if query_lower in template.title.lower():
            score += 5
        if query_lower in template.content.lower():
            score += 3
        if query_lower in template.notes.lower():
            score += 3

    return score


def resolve_prompts(
    lib: dict[str, PromptTemplate],
    *,
    category: str = "",
    tags: list[str] | None = None,
    query: str = "",
    limit: int = 3,
) -> list[dict]:
    """从库中检索最相关的模板。

    Args:
        lib: {id: PromptTemplate} 字典
        category: 必须匹配的分类（为空时不过滤）
        tags: 标签列表，命中越多越靠前
        query: 搜索关键词，在 title/content/notes 中命中加分
        limit: 最多返回条数

    Returns:
        按分数降序排列的模板列表，最多 limit 条
    """
    query_lower = query.strip().lower()
    tag_list = [t.strip() for t in (tags or []) if t.strip()]

    candidates: list[PromptTemplate] = []
    for t in lib.values():
        if category and t.category != category:
            continue
        candidates.append(t)

    if not candidates:
        return []

    # 打分并排序
    scored = [(t, _score_template(t, tag_list, query_lower)) for t in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [t.to_dict() for t, _ in scored[:max(1, min(limit, len(scored)))]]

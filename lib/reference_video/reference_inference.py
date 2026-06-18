"""从 reference_video 成品提示词文本推断 reference 绑定。

当 prompt 文本含 "图1：角色参考图 — 欧阳韬" 这样的声明时，
按图号排序推断出正确的 references 顺序，避免 unit.references 与
prompt 声明错位导致视频模型收到的参考图顺序错误。
"""

from __future__ import annotations

import re
from typing import Any

# ── 图号模式 ────────────────────────────────────────────────────────────
# 匹配: 图1 / 图 1 / 图片1 / 图片 1 / image1 / img1 / [图1] / [图 1]
_IMG_INDEX_RE = re.compile(
    r"(?:图|图片|image|img|\[图)\s*(\d+)\s*\]?",
    re.IGNORECASE,
)

# 资产类型提示关键词（按匹配优先级排列）
_TYPE_HINTS: list[tuple[str, str]] = [
    ("product", "产品|product"),
    ("character", "角色|人物|character"),
    ("scene", "场景|地点|scene"),
    ("prop", "道具|物品|prop"),
]


def _find_asset_type(line: str) -> str | None:
    """根据行内关键词推断资产类型。"""
    line_lower = line.lower()
    for atype, pattern in _TYPE_HINTS:
        if re.search(pattern, line_lower):
            return atype
    return None


def _longest_name_first(names: list[str]) -> list[str]:
    """按长度降序排列，避免短名误命中长名。"""
    return sorted(names, key=lambda n: -len(n))


def _build_variant_costume_index(project: dict) -> dict[str, tuple[str, str]]:
    """构建 variant/costume 到基础角色的索引。

    对每个角色的 variants 和 costume_references，生成可用于 prompt 匹配的别名映射。
    如 "少年萧近宸" → ("character", "萧近宸")。

    Returns:
        {match_text: (asset_type, base_asset_name)}
    """
    index: dict[str, tuple[str, str]] = {}
    characters = project.get("characters") or {}
    if not isinstance(characters, dict):
        return index
    for char_name, entry in characters.items():
        if not isinstance(entry, dict):
            continue
        # 变体：variant label + 角色名 → 匹配 "少年萧近宸" / "萧近宸 少年时期"
        for v in (entry.get("variants") or []):
            if not isinstance(v, dict):
                continue
            vlabel = v.get("label", "").strip()
            if vlabel:
                # "少年萧近宸"
                index[f"{vlabel}{char_name}"] = ("character", char_name)
                # "萧近宸 少年时期"（variant label 自然匹配，不额外造句）
        # 服装：costume label → 匹配 "王爷常服"
        for c in (entry.get("costume_references") or []):
            if not isinstance(c, dict):
                continue
            clabel = c.get("label", "").strip()
            if clabel:
                # costume label 可能跨角色重复，这里用后出现的覆盖（later wins）
                index[clabel] = ("character", char_name)
    return index


def infer_references_from_prompt_text(project: dict, prompt: str) -> list[dict]:
    """从成品提示词文本推断 reference 绑定列表。

    识别模式（按优先级）：
    1. 图号行：``图1：角色参考图 — 欧阳韬`` → 解析图号 + 资产类型 + 名称
    2. 变体/服装匹配：``图1：少年萧近宸`` → variant label+name 组合匹配基础角色
    3. @mention：``@欧阳韬`` / ``@[欧阳韬]``
    4. 无图号声明时，按 @mention 出现顺序推断

    Args:
        project: project.json dict（含 characters/scenes/props/products）
        prompt: unit 的完整提示词文本

    Returns:
        [{"type": "character", "name": "欧阳韬"}, ...] 按图号排序。
        变体/服装匹配时仍绑定基础 character（reference schema 暂不扩展 variant/costume 类型）。
    """
    if not prompt or not isinstance(prompt, str):
        return []

    # 索引：{name: type}
    name_to_type: dict[str, str] = {}
    buckets: dict[str, dict] = {
        "character": project.get("characters") or {},
        "scene": project.get("scenes") or {},
        "prop": project.get("props") or {},
        "product": project.get("products") or {},
    }
    for atype, bucket in buckets.items():
        if isinstance(bucket, dict):
            for name in bucket:
                if isinstance(name, str) and name.strip():
                    name_to_type[name] = atype

    # 变体/服装索引（扩展匹配能力，但仍绑定基础角色）
    variant_index = _build_variant_costume_index(project)

    # 合并匹配候选：基础资产名 + variant/costume 别名
    all_candidates: dict[str, tuple[str, str]] = {}
    for name, atype in name_to_type.items():
        all_candidates[name] = (atype, name)
    for match_text, (atype, base_name) in variant_index.items():
        if match_text not in all_candidates:
            all_candidates[match_text] = (atype, base_name)

    # 第一遍：扫描图号行
    img_refs: dict[int, tuple[str, str]] = {}  # {img_num: (type, name)}
    lines = prompt.split("\n")
    for line in lines:
        m = _IMG_INDEX_RE.search(line)
        if not m:
            continue
        img_num = int(m.group(1))
        # 尝试匹配资产名（variant/costume 别名也参与匹配）
        candidates = _longest_name_first(list(all_candidates.keys()))
        matched_type = ""
        matched_name = ""
        for candidate_text in candidates:
            if candidate_text in line:
                matched_type, matched_name = all_candidates[candidate_text]
                # 尝试从行内关键词更精确地推断类型
                explicit_type = _find_asset_type(line)
                if explicit_type:
                    matched_type = explicit_type
                break
        if matched_name:
            img_refs[img_num] = (matched_type, matched_name)

    # 按图号排序
    refs: list[dict] = []
    for num in sorted(img_refs):
        atype, name = img_refs[num]
        if atype:
            refs.append({"type": atype, "name": name})

    # 第二遍：如果没有图号声明，从 @mention 推断
    if not refs:
        mention_re = re.compile(r"@\[([^\]]+)\]|@(\w[\w一-鿿]*)")
        seen: set[str] = set()
        for m in mention_re.finditer(prompt):
            name = m.group(1) or m.group(2)
            if not name or name in seen:
                continue
            # 先查 variant 索引，再查基础资产名
            if name in variant_index:
                atype, base_name = variant_index[name]
                seen.add(name)
                refs.append({"type": atype, "name": base_name})
            else:
                atype = name_to_type.get(name, "")
                if atype:
                    seen.add(name)
                    refs.append({"type": atype, "name": name})

    return refs

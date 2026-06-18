"""MCP tools: create / update / list character variants.

Agent 可通过这些受控工具管理角色变体（时期/服装/装束），
不允许直接 patch project.json 的 variants 字段。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from claude_agent_sdk import tool

from server.agent_runtime.sdk_tools._context import ToolContext, tool_error

# ---- stable id generation ------------------------------------------------

# 常见中文变体标签 → 稳定英文 slug 映射
_LABEL_SLUG_MAP: dict[str, str] = {
    "少年时期": "variant_young",
    "少年": "variant_young",
    "幼年时期": "variant_child",
    "幼年": "variant_child",
    "童年时期": "variant_child",
    "童年": "variant_child",
    "成年时期": "variant_adult",
    "成年": "variant_adult",
    "中年时期": "variant_midlife",
    "中年": "variant_midlife",
    "老年时期": "variant_elder",
    "老年": "variant_elder",
    "战损装": "variant_battle_worn",
    "战损": "variant_battle_worn",
    "战甲": "variant_armor",
    "常服": "variant_casual",
    "朝服": "variant_court",
    "官服": "variant_official",
    "夜行衣": "variant_night",
    "囚服": "variant_prison",
    "破衣": "variant_rags",
    "婚服": "variant_wedding",
    "王爷常服": "variant_prince_casual",
    "王爷服": "variant_prince_casual",
}


def _stable_variant_id(label: str) -> str:
    """从 label 生成稳定 variant id。已知中文标签走映射表，未知标签走短哈希。"""
    cleaned = label.strip()
    if cleaned in _LABEL_SLUG_MAP:
        return _LABEL_SLUG_MAP[cleaned]
    # 尝试去掉"时期"后缀再匹配
    if cleaned.endswith("时期") and cleaned[:-2] in _LABEL_SLUG_MAP:
        return _LABEL_SLUG_MAP[cleaned[:-2]]
    # 未知标签用短哈希
    h = hashlib.sha256(cleaned.encode()).hexdigest()[:8]
    return f"variant_{h}"


# ---- helpers ------------------------------------------------------------

def _get_character_entry(ctx: ToolContext, character_name: str) -> dict:
    """获取角色条目，不存在抛 ValueError。"""
    project = ctx.pm.load_project(ctx.project_name)
    chars = project.get("characters") or {}
    if character_name not in chars:
        raise ValueError(f"角色 '{character_name}' 不存在于 project.json")
    entry = chars[character_name]
    if not isinstance(entry, dict):
        raise ValueError(f"角色 '{character_name}' 数据格式异常")
    return entry


def _ensure_variants_list(entry: dict) -> list:
    """确保 variants 字段为列表并返回。"""
    variants = entry.get("variants")
    if not isinstance(variants, list):
        return []
    return variants


# ---- tools ---------------------------------------------------------------


def create_character_variant_tool(ctx: ToolContext):
    @tool(
        "create_character_variant",
        "为项目角色创建时期/服装变体（少年/成年/战损装等）。"
        "已存在同 label 的变体时返回 existing 不重复创建。"
        "变体创建后需用户通过 WebUI 上传或生成设计图。",
        {
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "角色名（必须在 project.json 中已存在）"},
                "label": {"type": "string", "description": "变体标签，如 '少年时期' / '成年时期' / '战损装'"},
                "description": {"type": "string", "description": "可选：变体视觉描述（年龄/体态/气质差异）"},
                "costume_reference_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：关联的服装参考 ID 列表",
                },
            },
            "required": ["character_name", "label"],
        },
    )
    async def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            character_name = str(args["character_name"]).strip()
            label = str(args["label"]).strip()
            description = str(args.get("description", "")).strip()
            costume_ids = args.get("costume_reference_ids")

            if not character_name or not label:
                raise ValueError("character_name 和 label 不能为空")

            if costume_ids is not None:
                if not isinstance(costume_ids, list) or not all(isinstance(i, str) for i in costume_ids):
                    raise ValueError("costume_reference_ids 必须是字符串列表")

            base_variant_id = _stable_variant_id(label)

            def _sync():
                nonlocal_vid = base_variant_id
                entry = _get_character_entry(ctx, character_name)
                existing = _ensure_variants_list(entry)

                # 检查同 label 是否已存在
                for v in existing:
                    if isinstance(v, dict) and v.get("label", "").strip() == label:
                        return {
                            "content": [{
                                "type": "text",
                                "text": f"ℹ️ 角色 '{character_name}' 已存在变体 '{label}' (id={v.get('id')})，跳过创建。",
                            }],
                        }

                # 检查同 id 是否冲突
                for v in existing:
                    if isinstance(v, dict) and v.get("id") == nonlocal_vid:
                        nonlocal_vid = f"{nonlocal_vid}_{hashlib.sha256(label.encode()).hexdigest()[:4]}"
                        break

                variant_entry = {
                    "id": nonlocal_vid,
                    "label": label,
                    "description": description,
                    "character_sheet": "",
                    "costume_reference_ids": list(costume_ids or []),
                }

                def _mutate(project: dict):
                    chars = project.setdefault("characters", {})
                    char_entry = chars[character_name]
                    variants = char_entry.setdefault("variants", [])
                    if not isinstance(variants, list):
                        variants = []
                        char_entry["variants"] = variants
                    variants.append(variant_entry)

                ctx.pm.update_project(ctx.project_name, _mutate)
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            f"✅ 已为角色 '{character_name}' 创建变体:\n"
                            f"  id: {nonlocal_vid}\n"
                            f"  label: {label}\n"
                            f"  description: {description or '（无）'}\n"
                            f"  costume_reference_ids: {costume_ids or []}\n\n"
                            f"⚠️ 变体设计图为空，请用户通过 WebUI 角色卡片上传或生成该变体的设计图。"
                        ),
                    }],
                }

            import asyncio
            return await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            return tool_error("create_character_variant", exc)

    return _handler


def update_character_variant_tool(ctx: ToolContext):
    @tool(
        "update_character_variant",
        "更新角色变体的元数据（label / description / costume_reference_ids）。"
        "不可修改 character_sheet（图片由用户通过 WebUI 上传）。",
        {
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "角色名"},
                "variant_id": {"type": "string", "description": "变体 ID（与 label 二选一）"},
                "label": {"type": "string", "description": "变体 label（与 variant_id 二选一，用于查找变体）"},
                "new_label": {"type": "string", "description": "可选：新的 label"},
                "description": {"type": "string", "description": "可选：新的视觉描述"},
                "costume_reference_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：新的服装参考 ID 列表",
                },
            },
            "required": ["character_name"],
        },
    )
    async def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            character_name = str(args["character_name"]).strip()
            variant_id = str(args.get("variant_id", "")).strip() or None
            lookup_label = str(args.get("label", "")).strip() or None
            new_label = args.get("new_label")
            new_desc = args.get("description")
            costume_ids = args.get("costume_reference_ids")

            if not variant_id and not lookup_label:
                raise ValueError("必须提供 variant_id 或 label 之一用于查找变体")
            if costume_ids is not None:
                if not isinstance(costume_ids, list) or not all(isinstance(i, str) for i in costume_ids):
                    raise ValueError("costume_reference_ids 必须是字符串列表")

            def _sync():
                entry = _get_character_entry(ctx, character_name)
                variants = _ensure_variants_list(entry)

                # 查找目标变体
                target_idx = None
                for i, v in enumerate(variants):
                    if isinstance(v, dict):
                        if variant_id and v.get("id") == variant_id:
                            target_idx = i
                            break
                        if lookup_label and v.get("label", "").strip() == lookup_label:
                            target_idx = i
                            break

                if target_idx is None:
                    lookup = variant_id or f"label='{lookup_label}'"
                    raise ValueError(f"未找到角色 '{character_name}' 的变体 ({lookup})")

                changed: list[str] = []
                target = variants[target_idx]

                def _mutate(project: dict):
                    v = project["characters"][character_name]["variants"][target_idx]
                    if new_label is not None:
                        old = v.get("label", "")
                        v["label"] = str(new_label).strip()
                        changed.append(f"label: '{old}' → '{v['label']}'")
                    if new_desc is not None:
                        v["description"] = str(new_desc).strip()
                        changed.append("description")
                    if costume_ids is not None:
                        v["costume_reference_ids"] = list(costume_ids)
                        changed.append(f"costume_reference_ids: {costume_ids}")

                ctx.pm.update_project(ctx.project_name, _mutate)
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            f"✅ 已更新角色 '{character_name}' 的变体 (id={target.get('id')})\n"
                            f"  修改字段: {', '.join(changed) if changed else '（无变更）'}"
                        ),
                    }],
                }

            import asyncio
            return await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            return tool_error("update_character_variant", exc)

    return _handler


def list_character_variants_tool(ctx: ToolContext):
    @tool(
        "list_character_variants",
        "列出项目角色已有的变体。传 character_name 查特定角色，不传则列出全部角色变体。",
        {
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "可选：角色名，不传则列出所有角色的变体"},
            },
            "required": [],
        },
    )
    async def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            character_name = str(args.get("character_name", "")).strip() or None

            def _sync():
                project = ctx.pm.load_project(ctx.project_name)
                chars = project.get("characters") or {}

                if character_name:
                    if character_name not in chars:
                        raise ValueError(f"角色 '{character_name}' 不存在")
                    chars = {character_name: chars[character_name]}

                lines: list[str] = []
                total = 0
                for cname, entry in chars.items():
                    if not isinstance(entry, dict):
                        continue
                    variants = entry.get("variants")
                    if not isinstance(variants, list) or not variants:
                        continue
                    for v in variants:
                        if not isinstance(v, dict):
                            continue
                        total += 1
                        vid = v.get("id", "?")
                        vlabel = v.get("label", "?")
                        vdesc = v.get("description", "")
                        sheet = v.get("character_sheet", "")
                        cids = v.get("costume_reference_ids", [])
                        has_sheet = "✅" if sheet else "❌"
                        lines.append(
                            f"  [{has_sheet}] {cname} / {vlabel}  id={vid}"
                            + (f"  desc={vdesc}" if vdesc else "")
                            + (f"  costumes={cids}" if cids else "")
                        )

                if not lines:
                    return {
                        "content": [{
                            "type": "text",
                            "text": "ℹ️ 没有找到角色变体。",
                        }],
                    }

                header = f"📋 角色变体列表（共 {total} 个）:\n"
                return {
                    "content": [{
                        "type": "text",
                        "text": header + "\n".join(lines),
                    }],
                }

            import asyncio
            return await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            return tool_error("list_character_variants", exc)

    return _handler


__all__ = [
    "create_character_variant_tool",
    "update_character_variant_tool",
    "list_character_variants_tool",
]

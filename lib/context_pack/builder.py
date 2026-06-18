"""Context Pack 构建器。

纯函数：从 project.json + script.json 两个 dict 中确定性提取，
不读磁盘、不写数据、不调 AI。
"""

from __future__ import annotations

from typing import Any

from lib.asset_types import ASSET_SPECS
from lib.context_pack.models import SCHEMA_VERSION, empty_context_pack
from lib.preflight.checks import _has_sheet, _has_any_product_images, _is_empty_prompt


def build_context_pack(project: dict, script: dict, *, source_script: str = "") -> dict[str, Any]:
    """从 project.json 和剧本 dict 构建 Context Pack。

    纯函数，只做确定性提取。非 ad 模式返回空 pack。
    """
    content_mode = project.get("content_mode", "")
    if content_mode != "ad":
        return empty_context_pack(content_mode)

    pack = empty_context_pack("ad")
    pack["source_script"] = source_script

    # ── 基础信息 ──────────────────────────────────────────────────────
    overview = project.get("overview")
    if isinstance(overview, dict):
        pack["logline"] = overview.get("synopsis", "")
        pack["theme"] = overview.get("theme", "")

    # ── style_bible ───────────────────────────────────────────────────
    sb = pack["style_bible"]
    sb["aspect_ratio"] = project.get("aspect_ratio", "9:16")
    sb["style"] = project.get("style", "")
    sb["style_description"] = project.get("style_description", "")

    # ── 资产提取 ──────────────────────────────────────────────────────
    characters = project.get("characters")
    scenes = project.get("scenes")
    props = project.get("props")
    products = project.get("products")
    if not isinstance(characters, dict):
        characters = {}
    if not isinstance(scenes, dict):
        scenes = {}
    if not isinstance(props, dict):
        props = {}
    if not isinstance(products, dict):
        products = {}

    shots = script.get("shots")
    if not isinstance(shots, list):
        shots = []

    # 反向索引：asset_name → 出现在哪些 shot
    char_shot_map: dict[str, list[str]] = {}
    scene_shot_map: dict[str, list[str]] = {}
    prop_shot_map: dict[str, list[str]] = {}
    product_shot_map: dict[str, list[str]] = {}

    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("shot_id", "")
        for name in _list_str(shot.get("characters_in_shot")):
            char_shot_map.setdefault(name, []).append(sid)
        for name in _list_str(shot.get("scenes")):
            scene_shot_map.setdefault(name, []).append(sid)
        for name in _list_str(shot.get("props")):
            prop_shot_map.setdefault(name, []).append(sid)
        for name in _list_str(shot.get("products_in_shot")):
            product_shot_map.setdefault(name, []).append(sid)

    # 角色
    char_spec = ASSET_SPECS.get("character")
    for name, entry in characters.items():
        if not isinstance(entry, dict):
            entry = {}
        costumes_raw = entry.get("costume_references")
        costume_refs: list[dict] = list(costumes_raw) if isinstance(costumes_raw, list) else []
        variants_raw = entry.get("variants")
        variants_list: list[dict] = list(variants_raw) if isinstance(variants_raw, list) else []
        pack["characters_with_aliases"].append({
            "name": name,
            "aliases": [],
            "description": entry.get("description", ""),
            "voice_style": entry.get("voice_style", ""),
            "voice_reference_audio": entry.get("voice_reference_audio", ""),
            "costume_references": costume_refs,
            "variants": variants_list,
            "referenced_shots": char_shot_map.get(name, []),
            "has_sheet": _has_sheet(characters, name, char_spec.sheet_field) if char_spec else False,
        })
    # 场景
    scene_spec = ASSET_SPECS.get("scene")
    for name, entry in scenes.items():
        if not isinstance(entry, dict):
            entry = {}
        pack["scenes"].append({
            "name": name,
            "description": entry.get("description", ""),
            "referenced_shots": scene_shot_map.get(name, []),
            "has_sheet": _has_sheet(scenes, name, scene_spec.sheet_field) if scene_spec else False,
        })
    # 道具
    prop_spec = ASSET_SPECS.get("prop")
    for name, entry in props.items():
        if not isinstance(entry, dict):
            entry = {}
        pack["props"].append({
            "name": name,
            "description": entry.get("description", ""),
            "referenced_shots": prop_shot_map.get(name, []),
            "has_sheet": _has_sheet(props, name, prop_spec.sheet_field) if prop_spec else False,
        })
    # 产品
    for name, entry in products.items():
        if not isinstance(entry, dict):
            entry = {}
        pack["products"].append({
            "name": name,
            "brand": entry.get("brand", ""),
            "description": entry.get("description", ""),
            "referenced_shots": product_shot_map.get(name, []),
            "has_any_images": _has_any_product_images(products, name),
        })

    # ── shot_intent_map ────────────────────────────────────────────────
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("shot_id", "")
        ip = shot.get("image_prompt")
        vp = shot.get("video_prompt")

        visual_intent = ""
        if isinstance(ip, dict):
            scene_text = ip.get("scene", "")
            if isinstance(scene_text, str):
                visual_intent = scene_text.strip()
        elif isinstance(ip, str):
            visual_intent = ip.strip()

        motion_intent = ""
        if isinstance(vp, dict):
            action_text = vp.get("action", "")
            if isinstance(action_text, str):
                motion_intent = action_text.strip()
        elif isinstance(vp, str):
            motion_intent = vp.strip()

        pack["shot_intent_map"].append({
            "shot_id": sid,
            "section": shot.get("section", ""),
            "duration_seconds": _int_pos(shot.get("duration_seconds")),
            "voiceover_text": shot.get("voiceover_text", ""),
            "visual_intent": visual_intent,
            "motion_intent": motion_intent,
            "referenced_assets": {
                "characters": _list_str(shot.get("characters_in_shot")),
                "scenes": _list_str(shot.get("scenes")),
                "props": _list_str(shot.get("props")),
                "products": _list_str(shot.get("products_in_shot")),
            },
            "prompt_ready": not _is_empty_prompt(ip) and not _is_empty_prompt(vp),
        })

    # ── asset_reference_state（复用 preflight） ─────────────────────────
    from lib.preflight.checks import run_preflight
    preflight = run_preflight(project, script)

    missing: list[str] = []
    no_sheet: list[str] = []
    no_refs: list[str] = []

    for issue in preflight.blocking:
        if issue.code == "UNREGISTERED_REFERENCE":
            missing.append(f"{issue.location}: {issue.message}")
        elif issue.code in ("ASSET_WITHOUT_SHEET", "UNIT_ASSET_WITHOUT_SHEET"):
            no_sheet.append(f"{issue.location}: {issue.message}")
        elif issue.code == "PRODUCT_WITHOUT_REF":
            no_sheet.append(f"{issue.location}: {issue.message}")
    for issue in preflight.warnings:
        if issue.code == "NO_REFERENCES":
            no_refs.append(issue.location)

    pack["asset_reference_state"] = {
        "missing_assets": missing,
        "assets_without_sheet": no_sheet,
        "shots_without_references": no_refs,
    }

    return pack


# ── helpers ──────────────────────────────────────────────────────────────

def _list_str(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v.strip()]


def _int_pos(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0

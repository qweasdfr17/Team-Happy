"""Premium-format unit prompt builder.

从 unit 数据和项目资产自动生成精品提示词（9 段式模板），
替代原版简单 shots[].text 串接。
"""

from __future__ import annotations

from typing import Any

from lib.asset_types import BUCKET_KEY
from lib.reference_video.reference_inference import infer_references_from_prompt_text


def _asset_list(project: dict) -> dict[str, str]:
    """Build {name: type} index from project assets."""
    index: dict[str, str] = {}
    for atype, bkey in BUCKET_KEY.items():
        bucket = project.get(bkey) or {}
        if isinstance(bucket, dict):
            for name in bucket:
                if isinstance(name, str) and name.strip():
                    index[name] = atype
    return index


def _gather_unit_assets(
    unit: dict, project: dict
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """从 unit 的 shots 和 references 中收集角色/场景/道具引用。

    reference_video 的 Shot 仅有 text + duration，asset 信息在 unit.references 中。
    同时扫描 shot.text 中的 @mention 作为补充。

    Returns:
        (characters, scenes, props): each is [(name, sheet_path), ...]
    """
    import re

    chars: dict[str, str] = {}
    scs: dict[str, str] = {}
    prps: dict[str, str] = {}

    project_chars = (project.get("characters") or {}) if isinstance(project.get("characters"), dict) else {}
    project_scenes = (project.get("scenes") or {}) if isinstance(project.get("scenes"), dict) else {}
    project_props = (project.get("props") or {}) if isinstance(project.get("props"), dict) else {}

    # 主要来源：unit.references
    for ref in unit.get("references") or []:
        if not isinstance(ref, dict):
            continue
        rtype = ref.get("type", "")
        rname = ref.get("name", "")
        if rtype == "character" and rname in project_chars:
            sheet = project_chars[rname].get("character_sheet", "") if isinstance(project_chars[rname], dict) else ""
            chars[rname] = sheet
        elif rtype == "scene" and rname in project_scenes:
            sheet = project_scenes[rname].get("scene_sheet", "") if isinstance(project_scenes[rname], dict) else ""
            scs[rname] = sheet
        elif rtype == "prop" and rname in project_props:
            sheet = project_props[rname].get("prop_sheet", "") if isinstance(project_props[rname], dict) else ""
            prps[rname] = sheet

    # 补充：扫 shot.text 中的 @mention
    mention_re = re.compile(r"@\[([^\]]+)\]|@([\w一-鿿]+)")
    for shot in unit.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        text = shot.get("text", "") or ""
        for m in mention_re.finditer(text):
            name = m.group(1) or m.group(2)
            if not name:
                continue
            if name in project_chars and name not in chars:
                sheet = project_chars[name].get("character_sheet", "") if isinstance(project_chars[name], dict) else ""
                chars[name] = sheet
            elif name in project_scenes and name not in scs:
                sheet = project_scenes[name].get("scene_sheet", "") if isinstance(project_scenes[name], dict) else ""
                scs[name] = sheet
            elif name in project_props and name not in prps:
                sheet = project_props[name].get("prop_sheet", "") if isinstance(project_props[name], dict) else ""
                prps[name] = sheet

    return (
        [(n, chars[n]) for n in chars],
        [(n, scs[n]) for n in scs],
        [(n, prps[n]) for n in prps],
    )


def render_unit_prompt_premium(unit: dict, project: dict, *, style: str = "", aspect_ratio: str = "9:16") -> str:
    """构建精品提示词文本（9 段式模板）。

    Args:
        unit: video_units[] 条目，含 shots / references / duration_seconds
        project: project.json dict
        style: 视觉风格标签
        aspect_ratio: 画面比例

    Returns:
        精品提示词全文
    """
    characters, scenes, props = _gather_unit_assets(unit, project)
    all_assets = [*characters, *scenes, *props]
    all_names = [n for n, _ in all_assets]

    # ── 图片引用声明 ──
    img_lines: list[str] = []
    for i, (name, _sheet) in enumerate(all_assets, 1):
        img_lines.append(f"图片{i}：{name}")
    img_section = "\n".join(img_lines) if img_lines else "图片1：（无资产）"

    # ── 切片段 ──
    shots = unit.get("shots") or []
    slice_sections: list[str] = []
    for si, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        sidx = si + 1
        text = shot.get("text", "") or shot.get("video_prompt", "") or ""
        duration = shot.get("duration", 5)
        voiceover = shot.get("voiceover_text", "")
        chars_in = shot.get("characters_in_shot") or []
        scenes_in = shot.get("scenes") or []
        props_in = shot.get("props") or []

        char_str = "、".join(chars_in) if chars_in else "无"
        scene_str = "、".join(scenes_in) if scenes_in else "无"
        prop_str = "、".join(props_in) if props_in else "无"

        slice_sections.append(
            f"【切片段{sidx}】\n"
            f"时长：{duration}s\n"
            f"出场角色：{char_str}\n"
            f"场景：{scene_str}\n"
            f"道具：{prop_str}\n"
            f"画面：{text}\n"
            f"运镜：镜头平稳推进，跟随主体运动\n"
            f"对白：{voiceover if voiceover else '无对白'}\n"
            f"音效：环境音 + 动作拟音"
        )

    slices_text = "\n\n".join(slice_sections) if slice_sections else "（无切片段）"

    # ── 场景设计（取第一个场景或全部） ──
    scene_names = [n for n, _ in scenes]
    scene_str = "、".join(scene_names) if scene_names else "未指定场景"
    project_scenes = project.get("scenes") or {}
    scene_desc = ""
    if scene_names and isinstance(project_scenes, dict):
        first_scene = project_scenes.get(scene_names[0], {})
        if isinstance(first_scene, dict):
            scene_desc = first_scene.get("description", "")

    # ── 风格 ──
    style_label = style or project.get("style", "") or "写实"
    style_desc = project.get("style_description", "") or ""

    prompt = f"""【图片引用声明】
{img_section}

【全局视频要求】
{style_label}。{style_desc}
竖屏，{aspect_ratio}，多场景，多角度，60fps 流畅动画。
有环境音和动作音效，无音乐，无字幕，不出现任何文字、水印、Logo。
中文对白，人物动作流畅，运镜丝滑。
0s-0.15s 作为废帧缓冲，不安排关键动作、关键表情和关键对白。

【场景设计】
场景：{scene_str}，自然光，室内/室外混合。
{scene_desc}
整体空间氛围：与剧情氛围一致。

【目标情绪】
与当前片段情绪基调一致

{slices_text}

【负面约束】
禁止字幕、水印、Logo、画面文字。
禁止 BGM。
禁止角色外貌走样、肢体扭曲、手指异常。
禁止静帧、卡顿、跳帧。
禁止画面模糊、过曝、死黑。
禁止出现现代元素（与世界观冲突的物体/服装/建筑）。
"""

    return prompt


def apply_premium_prompt_to_unit(unit: dict, project: dict) -> dict:
    """为 unit 生成精品提示词，写入 shots[].text 并推断 references。

    保留字段：unit_id / duration_seconds / generated_assets /
    transition_to_next / note 均不修改。

    Args:
        unit: video_units[] 条目
        project: project.json dict

    Returns:
        修改后的 unit（原地修改 + 返回）
    """
    # 记录原始总时长（_add_metadata 已写入）
    total_duration: int = int(unit.get("duration_seconds", 0))
    if total_duration <= 0:
        # 回退：从原 shots 求和
        total_duration = sum(int(s.get("duration", 5)) for s in (unit.get("shots") or []) if isinstance(s, dict))

    prompt = render_unit_prompt_premium(unit, project)

    # 替换为单 shot：duration = 原总时长，text = 精品提示词全文
    unit["shots"] = [{"text": prompt, "duration": total_duration}]
    unit["duration_seconds"] = total_duration
    unit["duration_override"] = True

    # 推断 references：
    #   - 推断成功 → 写入推断结果
    #   - 推断失败 → 保留旧 references（不清空）
    #   - 推断失败 + 旧 references 为空 → 设为空列表
    old_refs: list = unit.get("references") or []
    inferred = infer_references_from_prompt_text(project, prompt)
    if inferred:
        unit["references"] = inferred
    elif not old_refs:
        unit["references"] = []

    return unit


__all__ = ["render_unit_prompt_premium", "apply_premium_prompt_to_unit"]

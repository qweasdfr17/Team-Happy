"""Premium-format unit prompt builder.

从 unit 数据和项目资产自动生成精品提示词（9 段式模板），
替代原版简单 shots[].text 串接。
"""

from __future__ import annotations

import re
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


def _format_aspect_ratio(aspect_ratio: str) -> str:
    """将比例值转为带方向的展示文本，不硬编码竖屏/横屏。

    >>> _format_aspect_ratio("9:16")
    '竖屏 9:16'
    >>> _format_aspect_ratio("16:9")
    '横屏 16:9'
    >>> _format_aspect_ratio("1:1")
    '1:1'
    """
    ratio = aspect_ratio.strip()
    if ratio == "9:16":
        return "竖屏 9:16"
    if ratio == "16:9":
        return "横屏 16:9"
    return ratio


# 匹配行内图片编号引用（不含开头的【图片引用声明】格式），
# 用于清理切片段/画面描述中不应出现的图片编号。
# 覆盖：图片1 / 图片 1 / 图1 / [图1] / 【图1】 / I图片1 / 晋图片3 / !图片2 / 1图片4 / #图片1
_INLINE_IMG_REF_RE = re.compile(
    r"[A-Za-z0-9一-鿿ＩＩI!！#【\[]*"
    r"(?:图片|图|image|img|\[图|【图)"
    r"\s*\d+\s*[】\]]?",
    re.IGNORECASE,
)


def _strip_inline_image_refs(text: str) -> str:
    """移除行内图片编号引用，保留资产名。

    >>> _strip_inline_image_refs("图片1：凯尔立于近地轨道")
    '凯尔立于近地轨道'
    >>> _strip_inline_image_refs("[图1] 萧近宸 推门而入")
    '萧近宸 推门而入'
    >>> _strip_inline_image_refs("I图片1 晋图片3")
    ''
    """
    cleaned = _INLINE_IMG_REF_RE.sub("", text)
    # 移除可能残留的冒号、破折号、空白前缀
    cleaned = re.sub(r"^[\s：:—\-]+", "", cleaned)
    # 压缩多余空白
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _compress_blank_lines(text: str) -> str:
    """压缩连续 3+ 个换行为最多两个（段落间最多一个空行）。

    >>> _compress_blank_lines("a\\n\\n\\nb")
    'a\\n\\nb'
    """
    return re.sub(r"\n{3,}", "\n\n", text)


def _resolve_project_style(project: dict, explicit_style: str = "") -> tuple[str, str]:
    """从 project.json 读取画风/风格，不硬编码默认画风。

    Returns:
        (style_label, style_description): 若项目未设置 style，返回空串而非模板默认值。
    """
    style_label = explicit_style.strip() if explicit_style else ""
    if not style_label:
        raw = project.get("style")
        if isinstance(raw, str) and raw.strip():
            style_label = raw.strip()
    style_desc = ""
    raw_desc = project.get("style_description")
    if isinstance(raw_desc, str) and raw_desc.strip():
        style_desc = raw_desc.strip()
    return style_label, style_desc


def render_unit_prompt_premium(unit: dict, project: dict, *, style: str = "", aspect_ratio: str = "") -> str:
    """构建精品提示词文本（9 段式模板）。

    所有画风/比例/风格均从 project.json 读取，不硬编码模板默认值。

    Args:
        unit: video_units[] 条目，含 shots / references / duration_seconds
        project: project.json dict
        style: 调用方显式传入的视觉风格标签（优先级高于 project.json）
        aspect_ratio: 调用方显式传入的画面比例（优先级高于 project.json）

    Returns:
        精品提示词全文
    """
    characters, scenes, props = _gather_unit_assets(unit, project)

    # ── 图片引用声明 ──
    img_lines: list[str] = []
    for i, (name, _sheet) in enumerate(characters + scenes + props, 1):
        img_lines.append(f"图片{i}：{name}")
    img_section = "\n".join(img_lines) if img_lines else "图片1：（无资产）"

    # ── 比例：从 project 读取，调用方显式传入优先 ──
    resolved_ratio = aspect_ratio.strip() if aspect_ratio else ""
    if not resolved_ratio:
        raw = project.get("aspect_ratio")
        if isinstance(raw, str) and raw.strip():
            resolved_ratio = raw.strip()
    # 一级项目 aspect_ratio 未设置时，从 sub-dict 读取（某些项目结构）
    if not resolved_ratio:
        ar_dict = project.get("aspect_ratio")
        if isinstance(ar_dict, dict):
            for key in ("video", "storyboard", "characters"):
                v = ar_dict.get(key)
                if isinstance(v, str) and v.strip():
                    resolved_ratio = v.strip()
                    break
    if not resolved_ratio:
        resolved_ratio = "16:9"  # 最终回退：横屏（视频最常用）

    ratio_display = _format_aspect_ratio(resolved_ratio)

    # ── 风格：从 project 读取，不硬编码 ──
    style_label, style_desc = _resolve_project_style(project, style)

    # 构建风格行：有 label 写 label，有 desc 追加
    style_parts: list[str] = []
    if style_label:
        style_parts.append(style_label)
    if style_desc:
        style_parts.append(style_desc)
    style_line = "。".join(style_parts) if style_parts else ""

    # ── 切片段 ──
    shots = unit.get("shots") or []
    slice_sections: list[str] = []
    for si, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        sidx = si + 1
        raw_text = shot.get("text", "") or shot.get("video_prompt", "") or ""
        # 清理行内图片编号引用，只保留资产名
        text = _strip_inline_image_refs(raw_text) if raw_text else ""
        duration = shot.get("duration", 5)
        voiceover_raw = shot.get("voiceover_text", "")
        voiceover = _strip_inline_image_refs(voiceover_raw) if voiceover_raw else ""

        slice_sections.append(
            f"【切片段{sidx}】\n"
            f"时长：{duration}s\n"
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

    # 全局要求行：仅包含项目配置中存在的字段
    global_lines: list[str] = []
    if style_line:
        global_lines.append(style_line + "。")
    global_lines.append(f"{ratio_display}，多场景，多角度，60fps 流畅动画。")
    global_lines.append("有环境音和动作音效，无音乐，无字幕，不出现任何文字、水印、Logo。")
    global_lines.append("中文对白，人物动作流畅，运镜丝滑。")
    global_lines.append("0s-0.15s 作为废帧缓冲，不安排关键动作、关键表情和关键对白。")

    prompt = f"""【图片引用声明】
{img_section}

【全局视频要求】
{chr(10).join(global_lines)}

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

    # 压缩连续 3+ 空行 → 最多一个空行
    prompt = _compress_blank_lines(prompt)
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

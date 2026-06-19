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

    def _sheet(bucket: dict, name: str, field: str) -> str:
        entry = bucket.get(name)
        return entry.get(field, "") if isinstance(entry, dict) else ""

    def _add_asset(ref_type: str, name: str) -> None:
        if ref_type == "character" and name in project_chars and name not in chars:
            chars[name] = _sheet(project_chars, name, "character_sheet")
        elif ref_type == "scene" and name in project_scenes and name not in scs:
            scs[name] = _sheet(project_scenes, name, "scene_sheet")
        elif ref_type == "prop" and name in project_props and name not in prps:
            prps[name] = _sheet(project_props, name, "prop_sheet")

    # 主要来源：unit.references
    for ref in unit.get("references") or []:
        if not isinstance(ref, dict):
            continue
        rtype = ref.get("type", "")
        rname = ref.get("name", "")
        _add_asset(rtype, rname)

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
            if name in project_chars:
                _add_asset("character", name)
            elif name in project_scenes:
                _add_asset("scene", name)
            elif name in project_props:
                _add_asset("prop", name)

    # 兜底：LLM 有时直接写资产名而不写 references/@mention；开头声明仍需绑定这些资产。
    plain_candidates: list[tuple[str, str]] = []
    for ref_type, bucket in (("character", project_chars), ("scene", project_scenes), ("prop", project_props)):
        for name in bucket:
            if isinstance(name, str) and name.strip():
                plain_candidates.append((ref_type, name))
    plain_candidates.sort(key=lambda item: len(item[1]), reverse=True)
    for shot in unit.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        text = " ".join(str(shot.get(key) or "") for key in ("text", "video_prompt", "voiceover_text"))
        for ref_type, name in plain_candidates:
            if name in text:
                _add_asset(ref_type, name)

    return (
        [(n, chars[n]) for n in chars],
        [(n, scs[n]) for n in scs],
        [(n, prps[n]) for n in prps],
    )


def _references_from_assets(
    characters: list[tuple[str, str]],
    scenes: list[tuple[str, str]],
    props: list[tuple[str, str]],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for ref_type, assets in (("character", characters), ("scene", scenes), ("prop", props)):
        for name, _sheet in assets:
            refs.append({"type": ref_type, "name": name})
    return refs


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


def _format_asset_mention(name: str) -> str:
    """Render an asset name as a prompt mention that reference inference can read."""
    return f"@{name}" if re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fff]+", name) else f"@[{name}]"


# 匹配行内图片编号引用（不含开头的【图片引用声明】格式），
# 用于清理切片段/画面描述中不应出现的图片编号。
# 覆盖：图片1 / 图片 1 / 图1 / [图1] / 【图1】 / I图片1 / 晋图片3 / !图片2 / 1图片4 / #图片1
_INLINE_IMG_REF_RE = re.compile(
    r"[A-Za-z0-9一-鿿ＩＩI!！#【\[]*"
    r"(?:图片|图|image|img|\[图|【图)"
    r"\s*\d+\s*[】\]]?",
    re.IGNORECASE,
)
_INLINE_MENTION_REF_RE = re.compile(r"(?<!\w)@\[([^\]\r\n]+)\]|(?<!\w)@([A-Za-z0-9_\u4e00-\u9fff]+)")


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


def _strip_inline_asset_mentions(text: str) -> str:
    """移除切片段正文里的 @mention 引用语法，只保留资产名。

    图片/资产引用只应出现在开头【图片引用声明】中，正文保留可读资产名即可。

    >>> _strip_inline_asset_mentions("@[近地轨道] 黑屏后 @[凯尔] 抬头")
    '近地轨道 黑屏后 凯尔 抬头'
    >>> _strip_inline_asset_mentions("@凯尔 看向 @叶琳")
    '凯尔 看向 叶琳'
    """

    def _replace(match: re.Match[str]) -> str:
        return match.group(1) or match.group(2) or ""

    cleaned = _INLINE_MENTION_REF_RE.sub(_replace, text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _clean_slice_text(text: str) -> str:
    cleaned = _strip_inline_image_refs(text)
    cleaned = _strip_inline_asset_mentions(cleaned)
    return cleaned


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


def _per_shot_assets(
    shot: dict, project: dict
) -> tuple[list[str], list[str], list[str]]:
    """从一个 shot 的 text 中提取该分镜涉及的角色/场景/道具名（无 @ 前缀）。

    优先从 @mention 提取，兜底从项目资产库的普通名称匹配。

    Returns:
        (character_names, scene_names, prop_names)
    """
    text = str(shot.get("text", "") or "")
    project_chars = (project.get("characters") or {}) if isinstance(project.get("characters"), dict) else {}
    project_scenes = (project.get("scenes") or {}) if isinstance(project.get("scenes"), dict) else {}
    project_props = (project.get("props") or {}) if isinstance(project.get("props"), dict) else {}

    chars: list[str] = []
    scs: list[str] = []
    prps: list[str] = []

    # 1) @mentions
    mention_re = re.compile(r"@\[([^\]]+)\]|@([\w一-鿿]+)")
    for m in mention_re.finditer(text):
        name = m.group(1) or m.group(2)
        if not name:
            continue
        if name in project_chars and name not in chars:
            chars.append(name)
        elif name in project_scenes and name not in scs:
            scs.append(name)
        elif name in project_props and name not in prps:
            prps.append(name)

    # 2) 兜底：普通名称匹配（按资产名长度降序，避免短名误匹配）
    plain_candidates: list[tuple[str, str]] = []
    for ref_type, bucket in (("character", project_chars), ("scene", project_scenes), ("prop", project_props)):
        for name in bucket:
            if isinstance(name, str) and name.strip():
                plain_candidates.append((ref_type, name))
    plain_candidates.sort(key=lambda item: len(item[1]), reverse=True)
    for ref_type, name in plain_candidates:
        if name in text:
            if ref_type == "character" and name not in chars:
                chars.append(name)
            elif ref_type == "scene" and name not in scs:
                scs.append(name)
            elif ref_type == "prop" and name not in prps:
                prps.append(name)

    return chars, scs, prps


def _normalize_shot_durations(shots: list[dict]) -> list[dict]:
    """兜底：确保每个 shot 的 duration 在 8-15 秒。

    - < 8s 的 shot 尝试与下一个 shot 合并（合并后 duration ≤ 15s），text 用空格拼接
    - 无法合并时 bump 到 8s 并记录 warning
    - 返回新 shots 列表（不修改输入）
    """
    import logging
    logger = logging.getLogger(__name__)

    if not shots:
        return shots

    normalized: list[dict] = []
    i = 0
    while i < len(shots):
        shot = dict(shots[i])  # 浅拷贝
        duration = int(shot.get("duration", 5))

        if duration >= 8:
            normalized.append(shot)
            i += 1
            continue

        # duration < 8：尝试与下一个合并
        if i + 1 < len(shots):
            next_shot = shots[i + 1]
            next_duration = int(next_shot.get("duration", 5))
            merged_duration = duration + next_duration
            if merged_duration <= 15:
                merged_text = " ".join([
                    str(shot.get("text", "")),
                    str(next_shot.get("text", "")),
                ])
                merged_voiceover = " ".join(filter(None, [
                    str(shot.get("voiceover_text", "")),
                    str(next_shot.get("voiceover_text", "")),
                ]))
                normalized.append({
                    "text": merged_text,
                    "duration": merged_duration,
                    "voiceover_text": merged_voiceover or shot.get("voiceover_text", ""),
                })
                logger.warning(
                    "shot duration %ds < 8s，已与相邻 shot(%ds) 合并为 %ds",
                    duration, next_duration, merged_duration,
                )
                i += 2
                continue

        # 无法合并：bump 到 8s
        logger.warning("shot duration %ds < 8s 且无法合并，bump 到 8s", duration)
        shot["duration"] = 8
        normalized.append(shot)
        i += 1

    return normalized


def render_unit_prompt_premium(unit: dict, project: dict, *, style: str = "", aspect_ratio: str = "") -> str:
    """构建精品提示词文本 — 对齐 ai-video-prompt skill 格式。

    所有画风/比例/风格均从 project.json 读取，不硬编码模板默认值。
    每个分镜独立写完整【基础设定】【画风】【场景光影基调】【负面约束】。

    Args:
        unit: video_units[] 条目，含 shots / references / duration_seconds
        project: project.json dict
        style: 调用方显式传入的视觉风格标签（优先级高于 project.json）
        aspect_ratio: 调用方显式传入的画面比例（优先级高于 project.json）

    Returns:
        精品提示词全文
    """
    characters, scenes, props = _gather_unit_assets(unit, project)

    # ── 图片引用声明（唯一使用 @资产 的位置）──
    img_lines: list[str] = []
    for name, _sheet in characters + scenes + props:
        img_lines.append(_format_asset_mention(name))
    img_section = "\n".join(img_lines) if img_lines else "（无资产）"

    # ── 比例：从 project 读取 ──
    resolved_ratio = aspect_ratio.strip() if aspect_ratio else ""
    if not resolved_ratio:
        raw = project.get("aspect_ratio")
        if isinstance(raw, str) and raw.strip():
            resolved_ratio = raw.strip()
    if not resolved_ratio:
        ar_dict = project.get("aspect_ratio")
        if isinstance(ar_dict, dict):
            for key in ("video", "storyboard", "characters"):
                v = ar_dict.get(key)
                if isinstance(v, str) and v.strip():
                    resolved_ratio = v.strip()
                    break
    if not resolved_ratio:
        resolved_ratio = "16:9"

    ratio_display = _format_aspect_ratio(resolved_ratio)

    # ── 风格：从 project 读取 ──
    style_label, style_desc = _resolve_project_style(project, style)
    style_parts: list[str] = []
    if style_label:
        style_parts.append(style_label)
    if style_desc:
        style_parts.append(style_desc)
    style_line = "。".join(style_parts) if style_parts else ""

    # ── 全局要求 ──
    global_lines: list[str] = []
    if style_line:
        global_lines.append(f"画风：{style_line}")
    global_lines.append(f"{ratio_display}，多场景，多角度，60fps 流畅动画。")
    global_lines.append("有环境音和动作音效，无音乐，无字幕，不出现任何文字、水印、Logo。")
    global_lines.append("中文对白，人物动作流畅，运镜丝滑。")
    global_lines.append("0s-0.15s 作为废帧缓冲，不安排关键动作、关键表情和关键对白。")

    # ── 各分镜独立渲染 ──
    shots = unit.get("shots") or []
    slice_sections: list[str] = []

    # 取第一个场景描述用于光影参考
    scene_names = [n for n, _ in scenes]
    project_scenes = project.get("scenes") or {}
    base_lighting = ""
    if scene_names and isinstance(project_scenes, dict):
        first_scene = project_scenes.get(scene_names[0], {})
        if isinstance(first_scene, dict):
            base_lighting = first_scene.get("description", "")

    for si, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        sidx = si + 1
        raw_text = shot.get("text", "") or shot.get("video_prompt", "") or ""
        duration = shot.get("duration", 8)
        voiceover_raw = shot.get("voiceover_text", "")
        # 正文只保留普通资产名，不保留 @ 引用和图片编号
        body_text = _clean_slice_text(raw_text) if raw_text else ""
        voiceover = _clean_slice_text(voiceover_raw) if voiceover_raw else ""

        # 该分镜涉及的资产（无 @ 前缀）
        s_chars, s_scs, s_prps = _per_shot_assets(shot, project)

        # 基础设定行
        basic_lines: list[str] = []
        if s_chars:
            basic_lines.append(f"角色：{'、'.join(s_chars)}（已生成角色参考图，不给外貌描述）")
        elif characters:
            # 退到 unit 级
            basic_lines.append(f"角色：{'、'.join(n for n, _ in characters)}（已生成角色参考图，不给外貌描述）")
        else:
            basic_lines.append("角色：未指定")
        if s_scs:
            basic_lines.append(f"场景：{'、'.join(s_scs)}（只写时空和关键信息）")
        elif scenes:
            basic_lines.append(f"场景：{'、'.join(n for n, _ in scenes)}（只写时空和关键信息）")
        else:
            basic_lines.append("场景：未指定")

        # 画风
        shot_style_line = f"画风：{style_line}" if style_line else "画风：与项目设定一致"

        # 场景光影基调
        if base_lighting:
            lighting = base_lighting
        else:
            lighting = "自然光，与场景氛围一致"

        # 画面内容
        content_parts: list[str] = [body_text]
        if voiceover:
            content_parts.append(f"对白：{voiceover}")
        content_text = "\n".join(content_parts)

        slice_sections.append(
            f"---\n"
            f"【分镜{sidx} | 时长 {duration}s】\n"
            f"\n"
            f"【基础设定】\n"
            f"{chr(10).join(basic_lines)}\n"
            f"\n"
            f"【画风】\n"
            f"{shot_style_line}\n"
            f"\n"
            f"【场景光影基调】\n"
            f"{lighting}\n"
            f"\n"
            f"不要背景音乐，不要字幕，仅保留音效和环境音。\n"
            f"\n"
            f"[画面内容]\n"
            f"{content_text}\n"
            f"\n"
            f"【负面约束】\n"
            f"禁止字幕、水印、Logo、画面文字。禁止 BGM。"
            f"禁止角色外貌走样、肢体扭曲、手指异常。"
            f"禁止静帧、卡顿、跳帧。"
            f"禁止画面模糊、过曝、死黑。"
        )

    slices_text = "\n\n".join(slice_sections) if slice_sections else "（无分镜）"

    prompt = f"""【图片引用声明】
{img_section}

【全局视频要求】
{chr(10).join(global_lines)}

{slices_text}
"""

    prompt = _compress_blank_lines(prompt)
    return prompt


def apply_premium_prompt_to_unit(unit: dict, project: dict) -> dict:
    """为 unit 生成精品提示词，写入 shots[].text 并推断 references。

    流程：先 normalize shot durations → 渲染 prompt → 保留多 shot 结构。

    - shots[0] 携带完整精品提示词，后续 shot text 为空串（避免红框重复）
    - 每个 shot.duration 为 normalized 后的独立时长（8-15s）
    - duration_override=true 告知 WebUI 只显示 shots[0].text
    - duration_seconds = 所有 shot duration 之和

    保留字段：unit_id / generated_assets / transition_to_next / note 均不修改。

    Args:
        unit: video_units[] 条目
        project: project.json dict

    Returns:
        修改后的 unit（原地修改 + 返回）
    """
    import logging
    logger = logging.getLogger(__name__)

    # 1) 兜底：normalize shot durations（确保 8-15s）
    raw_shots: list[dict] = unit.get("shots") or []
    if raw_shots:
        normalized_shots = _normalize_shot_durations(raw_shots)
        unit["shots"] = normalized_shots

    # 2) 用 normalized shots 计算总时长
    total_duration = sum(int(s.get("duration", 8)) for s in (unit.get("shots") or []) if isinstance(s, dict))
    if total_duration <= 0:
        total_duration = 8
    if total_duration < 8:
        logger.warning("unit total_duration %ds < 8s，bump 到 8s", total_duration)
        total_duration = 8

    # 3) 收集资产 + 渲染
    characters, scenes, props = _gather_unit_assets(unit, project)
    gathered_refs = _references_from_assets(characters, scenes, props)
    prompt = render_unit_prompt_premium(unit, project)

    # 4) 写回：保留多 shot 结构，精品提示词全文放入 shots[0].text
    #    duration_override=true → WebUI 只显示 shots[0].text（完整红框提示词）
    #    后续 shot text 为空串，避免 assemble_shots_text 拼接出冗余内容
    final_shots: list[dict] = []
    for si, shot in enumerate(unit.get("shots") or []):
        if not isinstance(shot, dict):
            continue
        d = int(shot.get("duration", 8))
        if d < 8:
            d = 8
        elif d > 15:
            d = 15
        final_shots.append({
            "text": prompt if si == 0 else "",
            "duration": d,
        })

    if not final_shots:
        final_shots = [{"text": prompt, "duration": 8}]

    unit["shots"] = final_shots
    unit["duration_seconds"] = total_duration
    unit["duration_override"] = True

    # 5) 推断 references
    old_refs: list = unit.get("references") or []
    inferred = infer_references_from_prompt_text(project, prompt)
    if inferred:
        unit["references"] = inferred
    elif gathered_refs:
        unit["references"] = gathered_refs
    elif not old_refs:
        unit["references"] = []

    return unit


__all__ = [
    "_normalize_shot_durations",
    "render_unit_prompt_premium",
    "apply_premium_prompt_to_unit",
    "_per_shot_assets",
    "_strip_inline_image_refs",
    "_strip_inline_asset_mentions",
]

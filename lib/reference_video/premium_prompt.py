"""Premium-format unit prompt builder.

从 unit 数据和项目资产自动生成精品提示词（9 段式模板），
替代原版简单 shots[].text 串接。
"""

from __future__ import annotations

import re

from lib.asset_types import BUCKET_KEY
from lib.reference_video.prompt_text_cleaner import clean_cn_prompt_spacing
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
    return clean_cn_prompt_spacing(cleaned.strip())


def _strip_subtitle_directives(text: str) -> str:
    """Remove explicit subtitle directives from visual text."""
    cleaned = re.sub(r"字幕\s*[:：]?\s*[「“\"]?[^。！？；\n「」“”\"]{1,20}[」”\"]?\s*[。；;]?", "", text)
    return clean_cn_prompt_spacing(cleaned.strip())


def _dedupe_nonempty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = clean_cn_prompt_spacing(str(item).strip())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _speech_from_value(value: object) -> list[str]:
    """Normalize dialogue/voiceover values without touching visual prompt text."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            lines.extend(_speech_from_value(item))
        return lines
    if isinstance(value, dict):
        speaker = str(value.get("speaker") or value.get("role") or value.get("character") or "").strip()
        line = str(
            value.get("line")
            or value.get("text")
            or value.get("content")
            or value.get("dialogue")
            or value.get("voiceover_text")
            or ""
        ).strip()
        if speaker and line:
            return [f"{speaker}「{line}」"]
        if line:
            return [line]
    return []


def _speech_from_text(text: str, speaker_names: list[str] | None = None) -> list[str]:
    """Best-effort fallback for legacy drama units that embedded speech in text."""
    if not isinstance(text, str) or not text.strip():
        return []

    valid_speakers = [name for name in (speaker_names or []) if name]
    valid_speaker_set = set(valid_speakers)
    role_words = (
        "保安",
        "职员",
        "司机",
        "记者",
        "主持人",
        "评审",
        "代表",
        "同事",
        "员工",
        "老师",
        "水总",
        "欧阳总",
    )

    def pick_last_speaker_name(value: str) -> str:
        matches = [(value.rfind(name), name) for name in valid_speakers if name in value]
        matches = [(idx, name) for idx, name in matches if idx >= 0]
        if not matches:
            return ""
        return max(matches, key=lambda item: item[0])[1]

    def infer_plain_speaker(sentence: str) -> str:
        colon_match = re.search(r"([\u4e00-\u9fffA-Za-z0-9_]{1,12})(?:（[^）]{1,20}）)?\s*[:：]\s*$", sentence)
        if colon_match:
            return normalize_plain_speaker(colon_match.group(1).strip())

        speech_match = re.search(
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,12})"
            r"(?:轻声|低声|沉声|拔高语气|故作大方)?"
            r"(?:说|问|喊|叫|答|开口|解释|怒斥|嗤笑)\s*[:：]?\s*$",
            sentence,
        )
        return normalize_plain_speaker(speech_match.group(1).strip()) if speech_match else ""

    def normalize_plain_speaker(candidate: str) -> str:
        match = re.search(r"([一二三四五六七八九十两几]名保安|保安)$", candidate)
        if match:
            return match.group(1)
        for word in role_words:
            if candidate.endswith(word):
                tail = re.search(r"([\u4e00-\u9fffA-Za-z0-9_]{0,4}" + re.escape(word) + r")$", candidate)
                return tail.group(1) if tail else word
        return candidate

    def is_plausible_plain_speaker(candidate: str) -> bool:
        if not candidate:
            return False
        if valid_speaker_set and candidate in valid_speaker_set:
            return True
        if candidate.startswith(("他", "她", "其")):
            return False
        if candidate.endswith(("开口", "低声", "轻声", "沉声", "语气镇定", "故作大方")):
            return False
        return any(word in candidate for word in role_words)

    def infer_speaker(quote_start: int) -> str:
        prefix = text[:quote_start]
        boundary = max(prefix.rfind(mark) for mark in ("。", "！", "？", "；", "\n"))
        sentence = prefix[boundary + 1 :]

        plain_speaker = infer_plain_speaker(sentence)
        if plain_speaker and plain_speaker not in {"字幕", "画面"} and is_plausible_plain_speaker(plain_speaker):
            return plain_speaker

        named_speaker = pick_last_speaker_name(sentence)
        if named_speaker:
            return named_speaker

        mentions = re.findall(r"@\[([^\]]+)\]", sentence)
        if valid_speaker_set:
            mentions = [name for name in mentions if name in valid_speaker_set]
        if mentions:
            return mentions[-1].strip()

        previous_mentions = re.findall(r"@\[([^\]]+)\]", prefix)
        if valid_speaker_set:
            previous_mentions = [name for name in previous_mentions if name in valid_speaker_set]
        if previous_mentions:
            return previous_mentions[-1].strip()
        return ""

    def is_non_dialogue_quote(quote_start: int, spoken: str) -> bool:
        prefix = text[:quote_start]
        sentence_start = max(prefix.rfind(mark) for mark in ("。", "！", "？", "；", "\n"))
        sentence = prefix[sentence_start + 1 :]
        return "字幕" in sentence[-16:] or spoken in {"十年后"}

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(?:对白|旁白|台词|配音)\s*[:：]\s*(.+)$", line)
        if match:
            lines.append(match.group(1).strip())

    # Preserve short quoted dialogue already embedded in the shot description.
    for match in re.finditer(r"[「“\"](.{1,80}?)[」”\"]", text):
        speaker = infer_speaker(match.start())
        spoken = match.group(1).strip()
        if not spoken or is_non_dialogue_quote(match.start(), spoken):
            continue
        lines.append(f"{speaker}「{spoken}」" if speaker else f"「{spoken}」")

    return _dedupe_nonempty(lines)


def _resolve_shot_speech(shot: dict, raw_text: str, speaker_names: list[str] | None = None) -> str:
    """Resolve dialogue/voiceover from known fields, falling back to legacy text."""
    values: list[str] = []
    for key in ("voiceover_text", "dialogue_text", "dialogue", "voiceover", "narration"):
        values.extend(_speech_from_value(shot.get(key)))

    video_prompt = shot.get("video_prompt")
    if isinstance(video_prompt, dict):
        for key in ("voiceover_text", "dialogue_text", "dialogue", "voiceover", "narration"):
            values.extend(_speech_from_value(video_prompt.get(key)))

    if not values:
        values.extend(_speech_from_text(raw_text, speaker_names))

    cleaned = [_strip_inline_image_refs(item) for item in values]
    return "；".join(_dedupe_nonempty(cleaned))


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
    for name, _sheet in characters + scenes + props:
        img_lines.append(f"@[{name}]")
    img_section = "\n".join(img_lines) if img_lines else "（无资产）"

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
        text = _strip_subtitle_directives(_strip_inline_image_refs(raw_text)) if raw_text else ""
        duration = shot.get("duration", 5)
        voiceover = _resolve_shot_speech(shot, raw_text, [name for name, _sheet in characters])

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
    return clean_cn_prompt_spacing(prompt)


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
    if not any(
        isinstance(s, dict) and str(s.get("text") or s.get("video_prompt") or "").strip()
        for s in (unit.get("shots") or [])
    ):
        raise ValueError(f"unit {unit.get('unit_id') or '?'} 缺少画面内容，拒绝生成空提示词")

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
    unit["video_prompt_source"] = "skill"

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

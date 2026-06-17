"""MCP tool: patch_reference_video_unit_prompt。

将精品视频提示词写入 scripts/episode_N.json 的 video_units[].shots[].text。
不生成视频，不入队。
"""

from __future__ import annotations

import re
from typing import Any

from claude_agent_sdk import tool

from lib.asset_types import BUCKET_KEY
from lib.reference_video import parse_prompt
from server.agent_runtime.sdk_tools._context import ToolContext, tool_error, validate_script_filename


_DECLARED_IMAGE_RE = re.compile(r"(?:图片|图|image|img)\s*([0-9０-９]+)", re.IGNORECASE)
_MENTION_RE = re.compile(r"@\[([^\]\r\n]+)\]|@([A-Za-z0-9_\u4e00-\u9fff]+)")
_TYPE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product", ("产品", "商品", "主产品", "product")),
    ("character", ("角色", "人物", "character")),
    ("scene", ("场景", "环境", "scene", "location")),
    ("prop", ("道具", "物件", "prop")),
)


def _find_unit(script: dict, unit_id: str) -> tuple[dict, str]:
    """Find a reference-video unit.

    narration/drama reference-video scripts store full units in ``video_units``.
    ad reference-video scripts store lightweight derived indexes in
    ``reference_units``.  The WebUI/generator must support both.
    """
    for key in ("video_units", "reference_units"):
        units = script.get(key)
        if not isinstance(units, list):
            continue
        for u in units:
            if isinstance(u, dict) and u.get("unit_id") == unit_id:
                return u, key
    raise ValueError(f"未找到 unit: {unit_id}")


def _apply_prompt_to_unit(unit: dict, prompt: str, duration_seconds: int | None, refs: list | None) -> dict:
    """将 prompt 文本解析后写入 unit.shots / unit.duration_seconds / unit.references。

    parse_prompt 返回 (shots, mentions, override)：
    - override=True：纯文本模式，shots[0].text=prompt
    - override=False：含 Shot header 的多 shot 模式
    """
    shots, _mentions, override = parse_prompt(prompt)

    if override:
        # 纯文本 → duration_override 模式；取传入秒数或原值或 shot 自身 duration
        duration = duration_seconds or unit.get("duration_seconds") or (shots[0].duration if shots else 5)
        if shots:
            shots[0].duration = int(duration)
    else:
        # 含 Shot header → 不 override；duration_seconds 为各 shot 之和
        pass

    unit["shots"] = [s.model_dump() for s in shots]
    unit["duration_seconds"] = sum(s.duration for s in shots)
    unit["duration_override"] = override

    if refs is not None:
        unit["references"] = refs

    return unit


def _asset_names(project: dict, ref_type: str) -> list[str]:
    bucket = project.get(BUCKET_KEY[ref_type])
    if not isinstance(bucket, dict):
        return []
    # Longest first avoids matching a short alias inside a longer asset name.
    return sorted((name for name in bucket if isinstance(name, str) and name), key=len, reverse=True)


def _line_type_hint(line: str) -> str | None:
    lowered = line.lower()
    for ref_type, hints in _TYPE_HINTS:
        if any(hint.lower() in lowered for hint in hints):
            return ref_type
    return None


def _add_ref_once(refs: list[dict], seen: set[tuple[str, str]], ref_type: str, name: str) -> None:
    key = (ref_type, name)
    if key in seen:
        return
    seen.add(key)
    refs.append({"type": ref_type, "name": name})


def _infer_refs_from_text(project: dict, prompt: str) -> list[dict]:
    """Infer reference assets from a finished prompt when the agent omits refs.

    The premium prompt skill often writes a human-readable section such as
    "图片1：角色参考图 — 小美" instead of passing the structured ``references``
    argument.  Convert those declarations, plus @mentions, into the same
    reference list the backend uses to attach images.
    """
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    # 1) Numbered image declarations define the user's intended order.
    declared: list[tuple[int, int, str, str]] = []
    for line_no, line in enumerate(prompt.splitlines()):
        image_match = _DECLARED_IMAGE_RE.search(line)
        if not image_match:
            continue
        number_text = image_match.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        hinted = _line_type_hint(line)
        types = [hinted] if hinted else ["product", "character", "scene", "prop"]
        for ref_type in types:
            for name in _asset_names(project, ref_type):
                if name in line:
                    declared.append((int(number_text), line_no, ref_type, name))
                    break
            if any(item[1] == line_no for item in declared):
                break
    for _number, _line_no, ref_type, name in sorted(declared, key=lambda x: (x[0], x[1])):
        _add_ref_once(refs, seen, ref_type, name)

    # 2) @mentions are a compact way for a skill/user to request binding.
    mentions = [
        match.group(1) or match.group(2)
        for match in _MENTION_RE.finditer(prompt)
        if match.group(1) or match.group(2)
    ]
    for mention in dict.fromkeys(mentions):
        for ref_type in ("product", "character", "scene", "prop"):
            if mention in _asset_names(project, ref_type):
                _add_ref_once(refs, seen, ref_type, mention)
                break

    return refs


def _apply_prompt_to_ad_reference_unit(unit: dict, prompt: str, refs: list | None) -> dict:
    """Persist a finished premium prompt for an ad reference unit.

    ad ``reference_units`` do not own shot content; they only point at
    ``shots[]``.  Store the agent-authored prompt as an override so generation
    can prefer it without rewriting the mother script or shot fields.
    """
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("prompt 不能为空")
    unit["prompt_override"] = cleaned
    if refs is not None:
        unit["references"] = refs
    return unit


def patch_reference_video_unit_prompt_tool(ctx: ToolContext):
    @tool(
        "patch_reference_video_unit_prompt",
        "将精品视频提示词写入 reference_video unit（WebUI 红框）。"
        "纯文本写入 unit.shots[0].text；含 Shot header 则拆为多 shot。"
        "不生成视频，不入队。完成后提示用户在页面审核，确认后再生成视频。",
        {
            "type": "object",
            "properties": {
                "episode": {"type": "integer", "description": "集号（通常为 1）"},
                "unit_id": {"type": "string", "description": "unit ID，如 E1U01"},
                "prompt": {"type": "string", "description": "完整精品视频提示词"},
                "references": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"type": {"type": "string"}, "name": {"type": "string"}}},
                    "description": "可选：参考图引用列表",
                },
                "duration_seconds": {"type": "integer", "description": "可选：unit 总时长秒数（纯文本模式使用）"},
            },
            "required": ["episode", "unit_id", "prompt"],
        },
    )
    async def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            episode = int(args["episode"])
            unit_id = str(args["unit_id"])
            prompt = str(args["prompt"])
            refs = args.get("references")
            duration_seconds = args.get("duration_seconds")
            if duration_seconds is not None:
                duration_seconds = int(duration_seconds)

            script_file = f"episode_{episode}.json"
            validate_script_filename(script_file)

            project = ctx.pm.load_project(ctx.project_name)
            with ctx.pm.locked_script(ctx.project_name, script_file) as script:
                unit, unit_kind = _find_unit(script, unit_id)
                if unit_kind == "reference_units":
                    if refs is None:
                        inferred = _infer_refs_from_text(project, prompt)
                        refs = inferred or unit.get("references")
                    _apply_prompt_to_ad_reference_unit(unit, prompt, refs)
                else:
                    _apply_prompt_to_unit(unit, prompt, duration_seconds, refs)

            return {
                "content": [{
                    "type": "text",
                    "text": (
                        f"✅ 已将提示词写入 {unit_id}\n"
                        f"请在 WebUI 红框中审核内容，确认无误后再生成视频。\n"
                        f"⚠️ 视频生成是高成本操作，请不要自动触发。"
                    ),
                }]
            }
        except Exception as exc:  # noqa: BLE001
            return tool_error("patch_reference_video_unit_prompt", exc)

    return _handler


__all__ = ["patch_reference_video_unit_prompt_tool"]

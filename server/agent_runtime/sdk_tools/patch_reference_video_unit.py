"""MCP tool: patch_reference_video_unit_prompt。

将精品视频提示词写入 scripts/episode_N.json 的 video_units[].shots[].text。
不生成视频，不入队。
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool

from lib.reference_video import parse_prompt
from server.agent_runtime.sdk_tools._context import ToolContext, tool_error, validate_script_filename


def _find_unit(script: dict, unit_id: str) -> dict:
    """在 script["video_units"] 中查找 unit。"""
    units = script.get("video_units")
    if not isinstance(units, list):
        raise ValueError("video_units 不存在或不是数组")
    for u in units:
        if isinstance(u, dict) and u.get("unit_id") == unit_id:
            return u
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

            with ctx.pm.locked_script(ctx.project_name, script_file) as script:
                unit = _find_unit(script, unit_id)
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

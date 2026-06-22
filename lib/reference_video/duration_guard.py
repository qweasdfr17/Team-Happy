"""Duration normalization for reference-video units.

The video backend receives one request per video unit, so the unit total is the
hard boundary that must respect model limits.  This module keeps that rule in
one place for generation, WebUI edits, and agent write-back tools.
"""

from __future__ import annotations

from copy import deepcopy

from lib.config.registry import PROVIDER_REGISTRY
from lib.script_models import GeneratedAssets

REFERENCE_VIDEO_HARD_MAX_DURATION = 15
REFERENCE_VIDEO_MAX_SHOTS = 4


def resolve_reference_video_max_duration(project: dict, max_duration: int | None = None) -> int:
    """Resolve the effective reference-video unit cap, never above 15 seconds."""
    candidates: list[int] = []
    if isinstance(max_duration, int) and not isinstance(max_duration, bool) and max_duration > 0:
        candidates.append(max_duration)

    durations = project.get("_supported_durations") if isinstance(project, dict) else None
    if isinstance(durations, list):
        parsed = [int(d) for d in durations if isinstance(d, int) and not isinstance(d, bool) and d > 0]
        if parsed:
            candidates.append(max(parsed))

    video_backend = project.get("video_backend") if isinstance(project, dict) else None
    if isinstance(video_backend, str) and "/" in video_backend:
        provider_id, model_id = video_backend.split("/", 1)
        provider_meta = PROVIDER_REGISTRY.get(provider_id)
        model_info = provider_meta.models.get(model_id) if provider_meta else None
        if model_info and model_info.supported_durations:
            candidates.append(max(int(d) for d in model_info.supported_durations))

    cap = min(candidates) if candidates else REFERENCE_VIDEO_HARD_MAX_DURATION
    return max(1, min(int(cap), REFERENCE_VIDEO_HARD_MAX_DURATION))


def split_duration(duration: object, max_duration: int) -> list[int]:
    """Split an arbitrary positive duration into balanced chunks <= max_duration."""
    try:
        total = int(duration)
    except (TypeError, ValueError):
        total = 1
    total = max(1, total)
    max_duration = max(1, int(max_duration))
    if total <= max_duration:
        return [total]

    chunk_count = (total + max_duration - 1) // max_duration
    base = total // chunk_count
    remainder = total % chunk_count
    return [base + (1 if index < remainder else 0) for index in range(chunk_count)]


def _shot_duration(shot: dict) -> int:
    return split_duration(shot.get("duration"), REFERENCE_VIDEO_HARD_MAX_DURATION)[0]


def _split_long_shot(shot: dict, max_duration: int) -> list[dict]:
    chunks = split_duration(shot.get("duration"), max_duration)
    if len(chunks) == 1:
        cloned = deepcopy(shot)
        cloned["duration"] = chunks[0]
        return [cloned]

    text = shot.get("text")
    parts: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        cloned = deepcopy(shot)
        cloned["duration"] = chunk
        if isinstance(text, str) and text.strip():
            phase = "前半段" if index == 1 else ("后半段" if index == len(chunks) else f"第{index}段")
            cloned["text"] = f"{text.strip()}\n\n自动拆分：这是原长镜头的{phase}，只表现本段时长内的动作与画面。"
        parts.append(cloned)
    return parts


def _group_shots(shots: object, max_duration: int) -> list[list[dict]]:
    if not isinstance(shots, list):
        return []

    groups: list[list[dict]] = []
    current: list[dict] = []
    current_duration = 0

    for raw in shots:
        if not isinstance(raw, dict):
            continue
        for shot in _split_long_shot(raw, max_duration):
            duration = _shot_duration(shot)
            over_count = len(current) >= REFERENCE_VIDEO_MAX_SHOTS
            over_duration = bool(current) and current_duration + duration > max_duration
            if over_count or over_duration:
                groups.append(current)
                current = []
                current_duration = 0
            current.append(shot)
            current_duration += duration

    if current:
        groups.append(current)
    return groups


def _unit_identity(unit: dict) -> tuple:
    shots = unit.get("shots") if isinstance(unit.get("shots"), list) else []
    return (
        [(s.get("duration"), s.get("text")) for s in shots if isinstance(s, dict)],
        unit.get("references"),
        unit.get("duration_seconds"),
    )


def normalize_reference_video_units(
    units: object,
    *,
    episode: int,
    project: dict | None = None,
    max_duration: int | None = None,
) -> list[dict]:
    """Return units whose total duration never exceeds the effective cap.

    Unit IDs are rewritten sequentially so split units remain addressable in
    playback order.  Existing generated assets are preserved only when a unit is
    unchanged; split or otherwise normalized units get a fresh pending state.
    """
    if not isinstance(units, list):
        return []

    cap = resolve_reference_video_max_duration(project or {}, max_duration)
    normalized: list[dict] = []
    next_index = 1

    for unit in units:
        if not isinstance(unit, dict):
            continue
        groups = _group_shots(unit.get("shots"), cap)
        if not groups:
            continue

        for group in groups:
            new_unit = deepcopy(unit)
            new_unit["unit_id"] = f"E{int(episode)}U{next_index}"
            new_unit["shots"] = group
            new_unit["duration_seconds"] = sum(_shot_duration(shot) for shot in group)
            next_index += 1

            same_unit = len(groups) == 1 and new_unit.get("unit_id") == unit.get("unit_id")
            same_identity = same_unit and _unit_identity(new_unit) == _unit_identity(unit)
            if not same_identity:
                new_unit["generated_assets"] = GeneratedAssets().model_dump()
                new_unit.pop("prompt_override", None)
            normalized.append(new_unit)

    return normalized


def normalize_reference_video_script(
    script: dict,
    *,
    episode: int,
    project: dict | None = None,
    max_duration: int | None = None,
) -> list[dict]:
    """Normalize ``script['video_units']`` in place and return the new list."""
    normalized = normalize_reference_video_units(
        script.get("video_units"),
        episode=episode,
        project=project,
        max_duration=max_duration,
    )
    script["video_units"] = normalized
    script["duration_seconds"] = sum(int(unit.get("duration_seconds") or 0) for unit in normalized)
    metadata = script.get("metadata")
    if isinstance(metadata, dict):
        metadata["total_units"] = len(normalized)
    return normalized

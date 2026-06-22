"""Text cleanup helpers for reference-video prompts."""

from __future__ import annotations

import re

_CJK = r"\u3400-\u9fff"
_CJK_RE = f"[{_CJK}]"
_MENTION_RE = re.compile(r"@\[([^\]\r\n]+)\]|@([A-Za-z0-9_\u4e00-\u9fff]+)")
_TOKEN_RE = re.compile(r"\ue000(\d+)\ue001")


def _protect_mentions(text: str) -> tuple[str, list[str]]:
    mentions: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        mentions.append(match.group(0))
        return f"\ue000{len(mentions) - 1}\ue001"

    return _MENTION_RE.sub(_replace, text), mentions


def _restore_mentions(text: str, mentions: list[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return mentions[index] if 0 <= index < len(mentions) else match.group(0)

    return _TOKEN_RE.sub(_replace, text)


def clean_cn_prompt_spacing(text: str) -> str:
    """Remove unnatural spaces inside Chinese prompt prose.

    The cleaner targets Chinese/CJK prose only. It keeps English phrases,
    model names, ratios, time expressions, and ``@`` asset mentions intact.
    """
    if not isinstance(text, str) or not text:
        return text

    protected, mentions = _protect_mentions(text)

    cleaned = protected
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(f"({_CJK_RE})[ \\t]+({_CJK_RE})", r"\1\2", cleaned)
    cleaned = re.sub(r"\s+([，。！？；：、）」』】》])", r"\1", cleaned)
    cleaned = re.sub(r"([（「『【《])\s+", r"\1", cleaned)
    cleaned = re.sub(f"([，。！？；：、])\\s+({_CJK_RE})", r"\1\2", cleaned)
    cleaned = re.sub(r"([，。！？；：、])\s+([（「『【《])", r"\1\2", cleaned)
    cleaned = re.sub(f"({_CJK_RE})\\s+([）」』】》])", r"\1\2", cleaned)

    return _restore_mentions(cleaned, mentions)


def clean_shot_texts(shots: object) -> None:
    """Clean ``text`` fields in a mutable shots list in place."""
    if not isinstance(shots, list):
        return
    for shot in shots:
        if isinstance(shot, dict) and isinstance(shot.get("text"), str):
            shot["text"] = clean_cn_prompt_spacing(shot["text"])

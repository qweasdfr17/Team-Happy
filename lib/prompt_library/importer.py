"""Prompt Library 批量导入器。

从本地 TXT 文件目录扫描参考生视频成品提示词，生成候选 JSON。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ── 标签推断规则 ────────────────────────────────────────────────────────

_TAG_RULES: list[tuple[str, list[str]]] = [
    ("参考图", ["图1", "图 1", "图片1", "图片 1", "图片引用", "[图1]", "[图 1]"]),
    ("多切片", ["切片段", "片段说明", "切片说明", "切 片段"]),
    ("运镜", ["运镜", "镜头运动", "机位", "跟焦", "推近", "拉远", "摇镜"]),
    ("对白", ["对白", "配音", "台词", "说：", "道："]),
    ("60fps", ["60fps", "60 fps", "60帧"]),
    ("古风", ["古代", "国风", "中国古代", "武侠", "仙侠", "江湖"]),
    ("现代", ["现代"]),
    ("情绪", ["情绪", "压迫", "紧张", "暧昧", "愤怒", "恐惧", "悲伤", "喜悦"]),
]


def _infer_tags(content: str) -> list[str]:
    """从提示词内容推断标签列表。"""
    tags: list[str] = ["参考生视频", "成品提示词"]
    for tag, keywords in _TAG_RULES:
        for kw in keywords:
            if kw in content:
                tags.append(tag)
                break
    return tags


# ── 稳定 ID ──────────────────────────────────────────────────────────────

def _stable_id(rel_path: str, content: str) -> str:
    """基于相对路径 + 内容 sha1 前 10 位生成稳定 id。"""
    path_hash = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:6]
    content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
    return f"import_{path_hash}_{content_hash}"


# ── 扫描 ─────────────────────────────────────────────────────────────────

def scan_txt_files(input_dir: Path) -> list[Path]:
    """递归扫描目录下所有 .txt 文件，按路径排序。"""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")
    files = sorted(input_dir.rglob("*.txt"))
    return files


# ── 编码 fallback ─────────────────────────────────────────────────────────

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


def _read_text_with_fallback(path: Path) -> str | None:
    """依次尝试多种编码读取文件内容，全部失败返回 None。"""
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return None


# ── 构建候选 ─────────────────────────────────────────────────────────────

def build_candidates(txt_files: list[Path], input_dir: Path) -> tuple[list[dict], dict[str, int]]:
    """将 TXT 文件列表转为候选条目列表 + 统计信息。

    Returns:
        (candidates, stats) — stats 含 total, candidates, empty_skipped
    """
    candidates: list[dict] = []
    stats: dict[str, int] = {"total": len(txt_files), "candidates": 0, "empty_skipped": 0}

    for fpath in txt_files:
        raw = _read_text_with_fallback(fpath)
        if raw is None:
            stats["empty_skipped"] += 1
            continue

        # 仅用 strip 版做空判断，保留原始 raw 为 content
        if not raw.strip():
            stats["empty_skipped"] += 1
            continue

        # 相对路径用于 id
        try:
            rel = str(fpath.relative_to(input_dir))
        except ValueError:
            rel = fpath.name

        tags = _infer_tags(raw)
        preview = raw[:200]

        candidate: dict[str, Any] = {
            "id": _stable_id(rel, raw),
            "category": "video_prompt",
            "title": fpath.stem,
            "tags": tags,
            "language": "zh",
            "format_type": "reference_video_multishot",
            "variables": [],
            "content": raw,
            "negative": "",
            "notes": "从 TXT 批量导入的参考生视频成品提示词候选",
            "source": "import_candidate",
            "priority": 50,
            "source_file": str(fpath.resolve()),
            "preview": preview,
        }
        candidates.append(candidate)
        stats["candidates"] += 1

    return candidates, stats


def write_import_candidates(candidates: list[dict], output_path: Path) -> None:
    """将候选列表写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

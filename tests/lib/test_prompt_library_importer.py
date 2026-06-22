"""Prompt Library TXT 导入器（lib/prompt_library/importer.py）单元测试。"""

import json
import tempfile
from pathlib import Path

import pytest

from lib.prompt_library.importer import (
    _infer_tags,
    _stable_id,
    build_candidates,
    scan_txt_files,
    write_import_candidates,
)

# ── tests ─────────────────────────────────────────────────────────────────


class TestScanTxtFiles:
    """1. 嵌套 txt 扫描。"""

    def test_scans_nested_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "子目录A").mkdir()
            (root / "子目录B" / "深层").mkdir(parents=True)
            (root / "子目录A" / "a.txt").write_text("aaa", encoding="utf-8")
            (root / "子目录B" / "b.txt").write_text("bbb", encoding="utf-8")
            (root / "子目录B" / "深层" / "c.txt").write_text("ccc", encoding="utf-8")
            files = scan_txt_files(root)
            assert len(files) == 3

    def test_ignores_non_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a", encoding="utf-8")
            (root / "b.md").write_text("b", encoding="utf-8")
            (root / "c.json").write_text("c", encoding="utf-8")
            files = scan_txt_files(root)
            assert len(files) == 1

    def test_missing_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            scan_txt_files(Path("/nonexistent_dir_xyz"))


class TestChineseFilename:
    """2. 中文文件名。"""

    def test_chinese_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "古代战场.txt").write_text("古代战场内容", encoding="utf-8")
            candidates, stats = build_candidates(scan_txt_files(root), root)
            assert stats["candidates"] == 1
            assert candidates[0]["title"] == "古代战场"


class TestCategoryAndFormatType:
    """3. 统一 category/format_type。"""

    def test_uniform_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("内容A", encoding="utf-8")
            (root / "b.txt").write_text("内容B", encoding="utf-8")
            candidates, _ = build_candidates(scan_txt_files(root), root)
            for c in candidates:
                assert c["category"] == "video_prompt"
                assert c["format_type"] == "reference_video_multishot"
                assert c["source"] == "import_candidate"
                assert "参考生视频" in c["tags"]
                assert "成品提示词" in c["tags"]


class TestTagInference:
    """4. 标签识别。"""

    def test_ref_image_tag(self):
        content = "图1 显示角色A，图片1 是场景B"
        tags = _infer_tags(content)
        assert "参考图" in tags

    def test_multishot_tag(self):
        content = "切片段说明：本视频包含3个切片段"
        tags = _infer_tags(content)
        assert "多切片" in tags

    def test_camera_tag(self):
        content = "运镜：推近镜头，跟焦主体"
        tags = _infer_tags(content)
        assert "运镜" in tags

    def test_dialogue_tag(self):
        content = "对白：角色A说：你好。配音：低沉男声"
        tags = _infer_tags(content)
        assert "对白" in tags

    def test_60fps_tag(self):
        content = "60fps高帧率输出"
        tags = _infer_tags(content)
        assert "60fps" in tags

    def test_gufeng_tag(self):
        content = "古代国风场景，江湖武侠"
        tags = _infer_tags(content)
        assert "古风" in tags

    def test_emotion_tag(self):
        content = "情绪：紧张压迫感，愤怒与恐惧交织"
        tags = _infer_tags(content)
        assert "情绪" in tags

    def test_base_tags_always_present(self):
        tags = _infer_tags("没有特殊关键词的内容")
        assert "参考生视频" in tags
        assert "成品提示词" in tags


class TestStableId:
    """5. 稳定 id。"""

    def test_same_input_same_id(self):
        id1 = _stable_id("子目录/文件.txt", "相同内容")
        id2 = _stable_id("子目录/文件.txt", "相同内容")
        assert id1 == id2

    def test_different_content_different_id(self):
        id1 = _stable_id("a.txt", "内容A")
        id2 = _stable_id("a.txt", "内容B")
        assert id1 != id2

    def test_id_starts_with_import(self):
        id_val = _stable_id("x/y.txt", "hello")
        assert id_val.startswith("import_")


class TestEmptyFileSkip:
    """6. 空文件跳过。"""

    def test_empty_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("", encoding="utf-8")
            (root / "b.txt").write_text("有内容", encoding="utf-8")
            candidates, stats = build_candidates(scan_txt_files(root), root)
            assert stats["candidates"] == 1
            assert stats["empty_skipped"] == 1

    def test_whitespace_only_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("   \n  \n  ", encoding="utf-8")
            candidates, stats = build_candidates(scan_txt_files(root), root)
            assert stats["candidates"] == 0
            assert stats["empty_skipped"] == 1


class TestWriteImportCandidates:
    """7. write_import_candidates 输出 JSON。"""

    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "deep" / "out.json"
            candidates = [{"id": "import_abc", "title": "测试"}]
            write_import_candidates(candidates, out)
            assert out.exists()
            data = json.loads(out.read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert data[0]["id"] == "import_abc"

    def test_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new" / "nested" / "candidates.json"
            write_import_candidates([], out)
            assert out.parent.exists()
            assert out.exists()


class TestRawContentPreservation:
    """content 保留首尾换行/空格。"""

    def test_preserves_leading_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = "\n\n开头有空行的内容\n\n"
            (root / "a.txt").write_text(raw, encoding="utf-8")
            candidates, _ = build_candidates(scan_txt_files(root), root)
            assert candidates[0]["content"] == raw
            assert candidates[0]["content"].startswith("\n")
            assert candidates[0]["content"].endswith("\n")

    def test_preserves_trailing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = "末尾有空格   \n"
            (root / "a.txt").write_text(raw, encoding="utf-8")
            candidates, _ = build_candidates(scan_txt_files(root), root)
            assert candidates[0]["content"] == raw


class TestSourceFileAbsolute:
    """source_file 是绝对路径。"""

    def test_source_file_is_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("hello", encoding="utf-8")
            candidates, _ = build_candidates(scan_txt_files(root), root)
            src = candidates[0]["source_file"]
            assert Path(src).is_absolute()


class TestEncodingFallback:
    """gb18030 编码 txt 能读取。"""

    def test_gb18030_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "中文GB18030编码测试内容"
            (root / "gb.txt").write_text(content, encoding="gb18030")
            candidates, stats = build_candidates(scan_txt_files(root), root)
            assert stats["candidates"] == 1
            assert "中文" in candidates[0]["content"]

    def test_unreadable_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 写入二进制数据，不是合法文本
            (root / "binary.txt").write_bytes(b"\x80\x81\x82\x83\x00\x01")
            candidates, stats = build_candidates(scan_txt_files(root), root)
            assert stats["candidates"] == 0
            assert stats["empty_skipped"] == 1

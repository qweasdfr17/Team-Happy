"""episode_planner screenplay 快路径 单元测试。"""

import re

import pytest

from lib.episode_planner import EpisodePlanner


# ── marker regex 测试 ──────────────────────────────────────────────────────

_RE = EpisodePlanner._EPISODE_TITLE_RE


class TestEpisodeTitleRegex:
    """分集标题正则匹配。"""

    def test_chinese_ordinal(self):
        matches = _RE.findall("\n第一集\n场景：开门")
        assert len(matches) >= 1

    def test_chinese_arabic(self):
        matches = _RE.findall("第1集 开场")
        assert len(matches) >= 1

    def test_chinese_arabic_with_space(self):
        matches = _RE.findall("第 5 集 冲突")
        assert len(matches) >= 1

    def test_ep_english(self):
        matches = _RE.findall("EP1 Intro")
        assert len(matches) >= 1

    def test_episode_english(self):
        matches = _RE.findall("Episode 3 高潮")
        assert len(matches) >= 1

    def test_large_number(self):
        matches = _RE.findall("第三十集")
        assert len(matches) >= 1

    def test_multiple_markers(self):
        text = "第一集\n正文A\n第二集\n正文B\n第三集\n正文C"
        matches = _RE.findall(text)
        assert len(matches) == 3

    def test_no_markers(self):
        matches = _RE.findall("这是普通文本，没有分集标题")
        assert len(matches) == 0

    def test_single_marker_not_enough(self):
        """单个标记不应触发快路径。"""
        text = "第一集\n正文"
        matches = _RE.findall(text)
        assert len(matches) == 1  # 只有 1 个标记，< 2


class TestScreenplaySplit:
    """screenplay 分集行为。"""

    def test_split_yields_correct_episodes(self):
        text = "《测试剧本》\n\n第一集\n\n场景1：开门\n角色A进入。\n\n第二集\n\n场景2：对峙\n角色B出现。\n\n第三集\n\n场景3：和解。\n"
        markers = []
        for m in _RE.finditer(text):
            markers.append((m.start(), m.end(), m.group().strip()))
        assert len(markers) == 3

        # 验证区间不重叠且连续
        bodies = []
        for idx in range(len(markers)):
            m_start, m_end, title = markers[idx]
            body_start = markers[idx][1]
            body_end = markers[idx + 1][0] if idx + 1 < len(markers) else len(text)
            body = text[body_start:body_end].strip()
            bodies.append(body)
            assert len(body) > 0, f"{title} 的正文不应为空"

        assert len(bodies) == 3
        # 区间连续
        for idx in range(len(markers) - 1):
            assert markers[idx][0] < markers[idx + 1][0], "标记应按位置递增"

    def test_source_range_not_overlapping(self):
        text = "第一集\nAAAA\n第二集\nBBBB\n"
        markers = []
        for m in _RE.finditer(text):
            markers.append((m.start(), m.end()))
        # 区间: [m1_end, m2_start), [m2_end, len(text))
        r1 = (markers[0][1], markers[1][0])
        r2 = (markers[1][1], len(text))
        assert r1[0] < r1[1]
        assert r2[0] < r2[1]
        assert r1[1] <= r2[0]  # 不重叠

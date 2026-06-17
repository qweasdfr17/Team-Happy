"""reference_inference — 从成品提示词推断 reference 绑定 单元测试。"""

import pytest

from lib.reference_video.reference_inference import infer_references_from_prompt_text


def _project(**overrides) -> dict:
    return {
        "characters": {
            "欧阳韬": {"description": "男主", "character_sheet": "chars/欧阳韬.png"},
            "女主": {"description": "女主"},
        },
        "scenes": {
            "中学走廊": {"description": "学校走廊", "scene_sheet": "scenes/走廊.png"},
            "教室": {"description": "教室"},
        },
        "props": {"戒指": {"description": "婚戒"}},
        "products": {},
        **overrides,
    }


class TestImageNumberLines:
    def test_character_then_scene_order(self):
        prompt = "图1：角色参考图 — 欧阳韬\n图2：场景参考图 — 中学走廊\n\nShot 1 (5s): 画面描述"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert len(refs) == 2
        assert refs[0] == {"type": "character", "name": "欧阳韬"}
        assert refs[1] == {"type": "scene", "name": "中学走廊"}

    def test_chinese_space_format(self):
        prompt = "图片 1：欧阳韬\n图片 2：中学走廊"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert refs[0] == {"type": "character", "name": "欧阳韬"}
        assert refs[1] == {"type": "scene", "name": "中学走廊"}

    def test_bracket_format(self):
        prompt = "[图1] 欧阳韬\n[图 2] 中学走廊"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert refs[0]["name"] == "欧阳韬"
        assert refs[1]["name"] == "中学走廊"

    def test_longest_name_match_first(self):
        """避免短名误命中长名（如"戒指"不应在"戒指盒"出现时先匹配）。"""
        proj = _project(props={"戒指盒": {}, "戒指": {}})
        prompt = "图1：戒指盒特写"
        refs = infer_references_from_prompt_text(proj, prompt)
        assert len(refs) == 1
        assert refs[0]["name"] == "戒指盒"


class TestMentionFallback:
    def test_mentions_without_image_numbers(self):
        prompt = "@欧阳韬 站在 @中学走廊 里"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert len(refs) == 2
        names = {r["name"] for r in refs}
        assert "欧阳韬" in names
        assert "中学走廊" in names

    def test_empty_prompt(self):
        assert infer_references_from_prompt_text(_project(), "") == []

    def test_none_prompt(self):
        assert infer_references_from_prompt_text(_project(), None) == []

    def test_no_matching_assets(self):
        prompt = "图1：不存在的人物 图2：不存在的场景"
        assert infer_references_from_prompt_text(_project(), prompt) == []


class TestTypeInference:
    def test_product_type_hint(self):
        proj = _project(products={"保温杯": {"description": "杯子"}})
        prompt = "图1：产品参考图 — 保温杯"
        refs = infer_references_from_prompt_text(proj, prompt)
        assert refs[0]["type"] == "product"

    def test_prop_type_hint(self):
        prompt = "图1：道具参考图 — 戒指"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert refs[0]["type"] == "prop"

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


class TestSimplifiedDeclarations:
    """简化图片声明：图片N：资产名（无类型词、无括号描述）。"""

    def test_simplified_four_assets(self):
        prompt = """【图片引用声明】
图片1：萧近宸
图片2：侍卫
图片3：王府书房
图片4：《冷面王爷的娇软小逃妻》话本"""
        proj = _project(
            characters={"萧近宸": {}, "侍卫": {}},
            scenes={"王府书房": {}},
            props={"《冷面王爷的娇软小逃妻》话本": {}},
        )
        refs = infer_references_from_prompt_text(proj, prompt)
        assert len(refs) == 4
        assert refs[0] == {"type": "character", "name": "萧近宸"}
        assert refs[1] == {"type": "character", "name": "侍卫"}
        assert refs[2] == {"type": "scene", "name": "王府书房"}
        assert refs[3] == {"type": "prop", "name": "《冷面王爷的娇软小逃妻》话本"}

    def test_with_parentheses_description_still_extracts_name(self):
        """即使有括号描述也能识别资产名（虽然模板禁止生成括号描述）。"""
        prompt = "图片1：角色\"欧阳韬\"的外观参考。\n图片2：场景\"中学走廊\"的环境参考。"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert refs[0]["name"] == "欧阳韬"
        assert refs[1]["name"] == "中学走廊"

    def test_order_determined_by_image_number(self):
        """图片编号顺序决定 references 顺序，不按 asset type 重排。"""
        prompt = "图片2：中学走廊\n图片1：欧阳韬"
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert refs[0]["name"] == "欧阳韬"  # 图片1 在前
        assert refs[1]["name"] == "中学走廊"  # 图片2 在后

    def test_extra_numbers_not_forced(self):
        """不存在的图片编号不补齐。"""
        prompt = "图片1：欧阳韬\n图片5：中学走廊"  # 图片2-4 不存在
        refs = infer_references_from_prompt_text(_project(), prompt)
        assert len(refs) == 2  # 只有声明的两张，不补空位

    def test_no_type_words_still_correct_bucket(self):
        """不带类型词也能正确识别 bucket（靠 project.json 索引）。"""
        prompt = "图片1：欧阳韬\n图片2：中学走廊\n图片3：戒指"
        refs = infer_references_from_prompt_text(_project(), prompt)
        types = {r["name"]: r["type"] for r in refs}
        assert types["欧阳韬"] == "character"
        assert types["中学走廊"] == "scene"
        assert types["戒指"] == "prop"

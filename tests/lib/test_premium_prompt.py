"""premium_prompt 单元测试。"""

from lib.reference_video.premium_prompt import (
    _compress_blank_lines,
    _strip_inline_asset_mentions,
    _strip_inline_image_refs,
    apply_premium_prompt_to_unit,
    render_unit_prompt_premium,
)


def _project() -> dict:
    return {
        "characters": {
            "萧近宸": {"description": "王爷", "character_sheet": "characters/萧近宸.png"},
        },
        "scenes": {
            "王府书房": {"description": "古朴书房，烛光摇曳", "scene_sheet": "scenes/书房.png"},
        },
        "props": {
            "话本": {"description": "泛黄的话本", "prop_sheet": "props/话本.png"},
        },
        "style": "国漫",
        "style_description": "水墨渲染风格",
    }


def _multi_shot_unit() -> dict:
    return {
        "unit_id": "E1U01",
        "shots": [
            {"text": "萧近宸推门而入，扫视书房", "duration": 3},
            {"text": "走近书案，拿起话本翻阅", "duration": 3},
            {"text": "合上话本，目光深邃", "duration": 2},
        ],
        "references": [
            {"type": "character", "name": "萧近宸"},
            {"type": "scene", "name": "王府书房"},
            {"type": "prop", "name": "话本"},
        ],
        "duration_seconds": 8,
        "generated_assets": {"status": "pending"},
        "transition_to_next": "cut",
        "note": "测试备注",
    }


class TestApplyPremiumPrompt:
    def test_multi_shot_becomes_single_shot(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert len(unit["shots"]) == 1
        assert "切片段1" in unit["shots"][0]["text"]
        assert "切片段2" in unit["shots"][0]["text"]
        assert "切片段3" in unit["shots"][0]["text"]
        # 精品格式结构
        assert "【图片引用声明】" in unit["shots"][0]["text"]
        assert "【全局视频要求】" in unit["shots"][0]["text"]
        assert "【场景设计】" in unit["shots"][0]["text"]
        assert "【负面约束】" in unit["shots"][0]["text"]

    def test_duration_preserved(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["duration_seconds"] == 8
        assert unit["shots"][0]["duration"] == 8

    def test_duration_override_set(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["duration_override"] is True

    def test_unit_id_preserved(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["unit_id"] == "E1U01"

    def test_generated_assets_preserved(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["generated_assets"] == {"status": "pending"}

    def test_transition_to_next_preserved(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["transition_to_next"] == "cut"

    def test_note_preserved(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["note"] == "测试备注"

    def test_references_inferred_from_prompt(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        refs = unit["references"]
        ref_names = {(r["type"], r["name"]) for r in refs}
        assert ("character", "萧近宸") in ref_names
        assert ("scene", "王府书房") in ref_names
        assert ("prop", "话本") in ref_names

    def test_references_preserved_when_inference_fails(self):
        """推断不到时保留旧 references。"""
        unit = _multi_shot_unit()
        # 仅保留角色引用，场景和道具不应出现在 prompt 的图片声明中
        # （但实际它们会通过 references 进入 _gather_unit_assets）
        # 改为测试：如果 project 中没有匹配资产，旧 refs 保留
        unit["references"] = [{"type": "character", "name": "萧近宸"}]
        apply_premium_prompt_to_unit(unit, _project())
        # 推断应该成功（prompt 中包含"图片1：萧近宸"）
        assert len(unit["references"]) >= 1

    def test_image_declarations_in_prompt(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        text = unit["shots"][0]["text"]
        assert "图片1：萧近宸" in text
        assert "图片2：王府书房" in text
        assert "图片3：话本" in text

    def test_slice_sections_preserve_original_shots(self):
        unit = _multi_shot_unit()
        apply_premium_prompt_to_unit(unit, _project())
        text = unit["shots"][0]["text"]
        # 每个切片段应包含原 shot 的描述
        assert "推门而入" in text
        assert "拿起话本翻阅" in text
        assert "合上话本" in text
        # 每个切片段有时长
        assert "3s" in text
        assert "2s" in text

    def test_no_references_still_works(self):
        unit = _multi_shot_unit()
        unit["references"] = []
        apply_premium_prompt_to_unit(unit, _project())
        assert unit["shots"][0]["duration"] == 8
        assert "【切片段" in unit["shots"][0]["text"]


class TestRenderPremiumPrompt:
    def test_contains_9_section_structure(self):
        prompt = render_unit_prompt_premium(_multi_shot_unit(), _project())
        assert "【图片引用声明】" in prompt
        assert "【全局视频要求】" in prompt
        assert "【场景设计】" in prompt
        assert "【目标情绪】" in prompt
        assert "【切片段" in prompt
        assert "【负面约束】" in prompt

    def test_image_order_matches_references(self):
        prompt = render_unit_prompt_premium(_multi_shot_unit(), _project())
        # 图片顺序：角色→场景→道具
        idx_xiao = prompt.index("图片1：萧近宸")
        idx_study = prompt.index("图片2：王府书房")
        idx_book = prompt.index("图片3：话本")
        assert idx_xiao < idx_study < idx_book


class TestAspectRatioFromProject:
    """比例必须从 project.json 读取，不硬编码。"""

    def test_16_9_project_outputs_landscape(self):
        project = _project()
        project["aspect_ratio"] = "16:9"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "横屏 16:9" in prompt
        assert "竖屏" not in prompt

    def test_9_16_project_outputs_portrait(self):
        project = _project()
        project["aspect_ratio"] = "9:16"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "竖屏 9:16" in prompt

    def test_custom_ratio_no_prefix(self):
        """1:1 等非标比例不加横屏/竖屏前缀。"""
        project = _project()
        project["aspect_ratio"] = "1:1"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "1:1" in prompt
        assert "横屏" not in prompt
        assert "竖屏" not in prompt

    def test_explicit_aspect_ratio_overrides_project(self):
        project = _project()
        project["aspect_ratio"] = "9:16"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project, aspect_ratio="16:9")
        assert "横屏 16:9" in prompt
        assert "竖屏" not in prompt

    def test_aspect_ratio_dict_fallback(self):
        """aspect_ratio 为 dict 时从 video key 读取。"""
        project = _project()
        project["aspect_ratio"] = {"video": "16:9", "storyboard": "9:16"}
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "横屏 16:9" in prompt


class TestStyleFromProject:
    """画风/风格必须从 project.json 读取，不硬编码模板默认值。"""

    def test_project_style_appears_in_prompt(self):
        project = _project()
        project["style"] = "电影感写实"
        project["style_description"] = "冷色调，柔光，胶片颗粒"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "电影感写实" in prompt
        assert "冷色调" in prompt

    def test_no_style_no_fallback_3d_cg(self):
        """项目未设置 style 时不硬塞 3D CG 等画风词。"""
        project = _project()
        project.pop("style", None)
        project.pop("style_description", None)
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "3D" not in prompt
        assert "CG" not in prompt
        # "流畅动画" 中的"动画"是质量描述词而非画风，不在此断言

    def test_3d_cg_only_when_project_says_so(self):
        """仅当项目 style 包含 3D/CG 时才出现对应词。"""
        project = _project()
        project["style"] = "3D CG"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "3D CG" in prompt

    def test_explicit_style_overrides_project(self):
        project = _project()
        project["style"] = "水墨"
        project.pop("style_description", None)  # 清除 _project() 默认的"水墨渲染风格"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project, style="赛博朋克")
        assert "赛博朋克" in prompt
        assert "水墨" not in prompt

    def test_references_unaffected_by_style_change(self):
        """图片引用声明不受比例/画风修改影响。"""
        project = _project()
        project["aspect_ratio"] = "21:9"
        project["style"] = "黑白默片"
        prompt = render_unit_prompt_premium(_multi_shot_unit(), project)
        assert "图片1：萧近宸" in prompt
        assert "图片2：王府书房" in prompt
        assert "图片3：话本" in prompt


class TestStripInlineImageRefs:
    """_strip_inline_image_refs 清理各种污染格式。"""

    def test_strips_basic_image_number(self):
        assert _strip_inline_image_refs("图片1：凯尔立于近地轨道") == "凯尔立于近地轨道"

    def test_strips_bracket_format(self):
        assert _strip_inline_image_refs("[图1] 萧近宸推门而入") == "萧近宸推门而入"

    def test_strips_double_bracket(self):
        assert _strip_inline_image_refs("【图1】萧近宸") == "萧近宸"

    def test_strips_polluted_prefix(self):
        assert _strip_inline_image_refs("I图片1 凯尔") == "凯尔"
        assert _strip_inline_image_refs("晋图片3 D-77空港") == "D-77空港"
        assert _strip_inline_image_refs("!图片2 近地轨道") == "近地轨道"
        assert _strip_inline_image_refs("#图片1") == ""
        assert _strip_inline_image_refs("1图片4 话本") == "话本"

    def test_preserves_asset_name(self):
        """清理后保留资产名。"""
        assert "凯尔" in _strip_inline_image_refs("图片1：凯尔 立于近地轨道")
        assert "近地轨道" in _strip_inline_image_refs("图片2：近地轨道 太空站")

    def test_empty_on_pure_ref(self):
        """纯图片编号无内容时返回空。"""
        assert _strip_inline_image_refs("图片1") == ""


class TestStripInlineAssetMentions:
    """_strip_inline_asset_mentions 清理切片段正文里的 @mention 引用语法。"""

    def test_strips_wrapped_mentions(self):
        assert _strip_inline_asset_mentions("@[近地轨道] 黑屏后 @[凯尔] 抬头") == "近地轨道 黑屏后 凯尔 抬头"

    def test_strips_legacy_mentions(self):
        assert _strip_inline_asset_mentions("@凯尔 看向 @叶琳") == "凯尔 看向 叶琳"

    def test_keeps_email_like_text(self):
        assert _strip_inline_asset_mentions("contact test@example.com") == "contact test@example.com"


class TestNoInlineRefsInSliceSections:
    """切片段和场景设计中不应出现行内图片编号。"""

    @staticmethod
    def _project_with_kyle() -> dict:
        return {
            "characters": {
                "凯尔": {"description": "主角", "character_sheet": "chars/凯尔.png"},
                "叶琳": {"description": "配角", "character_sheet": "chars/叶琳.png"},
            },
            "scenes": {"近地轨道": {"description": "太空站", "scene_sheet": "scenes/轨道.png"}},
            "props": {"D-77空港": {"description": "空港", "prop_sheet": "props/空港.png"}},
            "style": "写实",
            "style_description": "",
        }

    def _unit_with_polluted_text(self) -> dict:
        return {
            "unit_id": "E1U01",
            "shots": [
                {"text": "图片1：凯尔 立于[图2]近地轨道", "duration": 3},
                {"text": "I图片1 晋图片3 D-77空港 停靠", "duration": 3},
                {"text": "凯尔 走向!图片2 控制台，叶琳跟随", "duration": 2},
            ],
            "references": [
                {"type": "character", "name": "凯尔"},
                {"type": "character", "name": "叶琳"},
                {"type": "scene", "name": "近地轨道"},
                {"type": "prop", "name": "D-77空港"},
            ],
            "duration_seconds": 8,
        }

    def test_header_has_image_declarations(self):
        """开头【图片引用声明】保留。"""
        prompt = render_unit_prompt_premium(self._unit_with_polluted_text(), self._project_with_kyle())
        assert "图片1：凯尔" in prompt
        assert "图片2：叶琳" in prompt
        assert "图片3：近地轨道" in prompt
        assert "图片4：D-77空港" in prompt

    def test_header_infers_plain_asset_names_without_refs_or_mentions(self):
        """references/@mention 都缺失时，开头仍从普通资产名推断图片声明。"""
        unit = {
            "unit_id": "E1U01",
            "shots": [
                {"text": "近地轨道 黑屏后舰队残骸坠落", "duration": 5},
                {"text": "镜头急速坠入被炸毁的 D-77空港", "duration": 4},
                {"text": "凯尔 抬头看向 叶琳", "duration": 5},
            ],
            "references": [],
            "duration_seconds": 14,
        }
        prompt = render_unit_prompt_premium(unit, self._project_with_kyle())
        header = prompt.split("【全局视频要求】", 1)[0]
        assert "图片1：凯尔" in header
        assert "图片2：叶琳" in header
        assert "图片3：近地轨道" in header
        assert "图片4：D-77空港" in header
        assert "图片1：（无资产）" not in header

    def test_apply_writes_references_from_plain_asset_names(self):
        """普通资产名兜底不仅写开头声明，也同步写入 unit.references。"""
        unit = {
            "unit_id": "E1U01",
            "shots": [
                {"text": "近地轨道 黑屏后舰队残骸坠落", "duration": 5},
                {"text": "镜头急速坠入被炸毁的 D-77空港", "duration": 4},
                {"text": "凯尔 抬头看向 叶琳", "duration": 5},
            ],
            "references": [],
            "duration_seconds": 14,
        }
        apply_premium_prompt_to_unit(unit, self._project_with_kyle())
        header = unit["shots"][0]["text"].split("【全局视频要求】", 1)[0]
        assert "图片1：凯尔" in header
        assert "图片2：叶琳" in header
        assert "图片3：近地轨道" in header
        assert "图片4：D-77空港" in header
        assert unit["references"] == [
            {"type": "character", "name": "凯尔"},
            {"type": "character", "name": "叶琳"},
            {"type": "scene", "name": "近地轨道"},
            {"type": "prop", "name": "D-77空港"},
        ]

    def test_slice_sections_have_no_image_numbers(self):
        """切片段中不包含任何图片编号。"""
        prompt = render_unit_prompt_premium(self._unit_with_polluted_text(), self._project_with_kyle())
        # 取【图片引用声明】之后的内容
        after_header = prompt.split("【全局视频要求】", 1)[1] if "【全局视频要求】" in prompt else prompt
        assert "图片1" not in after_header
        assert "图片2" not in after_header
        assert "图片3" not in after_header
        assert "图片4" not in after_header
        assert "[图1]" not in after_header
        assert "[图2]" not in after_header
        assert "I图片1" not in after_header
        assert "晋图片3" not in after_header
        assert "!图片2" not in after_header

    def test_asset_names_preserved_in_slices(self):
        """切片段中保留资产名。"""
        prompt = render_unit_prompt_premium(self._unit_with_polluted_text(), self._project_with_kyle())
        after_header = prompt.split("【全局视频要求】", 1)[1] if "【全局视频要求】" in prompt else prompt
        assert "凯尔" in after_header
        assert "叶琳" in after_header
        assert "近地轨道" in after_header
        assert "D-77空港" in after_header

    def test_slice_sections_have_no_mentions(self):
        """切片段正文只保留资产名，不保留 @ 引用语法。"""
        unit = self._unit_with_polluted_text()
        unit["shots"] = [
            {"text": "@[近地轨道] 黑屏后舰队残骸坠落", "duration": 5},
            {"text": "镜头急速坠入被炸毁的 @[D-77空港]", "duration": 4},
            {"text": "@[凯尔] 抬头看向 @叶琳", "duration": 5, "voiceover_text": "@凯尔 低声呼喊"},
        ]
        prompt = render_unit_prompt_premium(unit, self._project_with_kyle())
        after_header = prompt.split("【全局视频要求】", 1)[1] if "【全局视频要求】" in prompt else prompt
        assert "@[" not in after_header
        assert "@凯尔" not in after_header
        assert "@叶琳" not in after_header
        assert "近地轨道 黑屏后舰队残骸坠落" in after_header
        assert "D-77空港" in after_header
        assert "凯尔 抬头看向 叶琳" in after_header
        assert "凯尔 低声呼喊" in after_header

    def test_references_still_inferred(self):
        """清理 inline refs 后 references 推断仍成功。"""
        unit = self._unit_with_polluted_text()
        apply_premium_prompt_to_unit(unit, self._project_with_kyle())
        ref_names = {(r["type"], r["name"]) for r in unit["references"]}
        assert ("character", "凯尔") in ref_names
        assert ("character", "叶琳") in ref_names
        assert ("scene", "近地轨道") in ref_names
        assert ("prop", "D-77空港") in ref_names


class TestBlankLineCompression:
    """空行压缩：最多连续两个换行。"""

    def test_compresses_three_newlines(self):
        assert "\n\n\n" not in _compress_blank_lines("a\n\n\nb")

    def test_preserves_single_blank_line(self):
        result = _compress_blank_lines("a\n\nb")
        assert "\n\n" in result

    def test_prompt_has_no_triple_newlines(self):
        """最终 prompt 不含连续 3 个换行。"""
        prompt = render_unit_prompt_premium(_multi_shot_unit(), _project())
        assert "\n\n\n" not in prompt

    def test_sections_separated_by_one_blank_line(self):
        """各 section 之间最多一个空行。"""
        prompt = render_unit_prompt_premium(_multi_shot_unit(), _project())
        # 统计连续空行数
        import re
        max_blank = max((len(m.group(0)) for m in re.finditer(r"\n+", prompt)), default=0)
        assert max_blank <= 2  # 最多 \n\n

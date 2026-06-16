"""Context Pack 构建器（lib/context_pack/builder.py）单元测试。"""

import pytest

from lib.context_pack.builder import build_context_pack


# ── helpers ───────────────────────────────────────────────────────────────

def _project(**overrides) -> dict:
    return {
        "content_mode": "ad",
        "title": "测试短片",
        "aspect_ratio": "9:16",
        "style": "国风水墨",
        "style_description": "水墨画风，淡雅色调",
        "overview": {
            "synopsis": "一段关于勇气与牺牲的短篇故事",
            "theme": "勇气",
        },
        "characters": {
            "女主": {
                "description": "年轻女子，长发，神情坚毅",
                "character_sheet": "characters/女主.png",
            },
            "老者": {
                "description": "年迈智者",
                # 无 character_sheet
            },
        },
        "scenes": {
            "古庙": {
                "description": "残破古庙，青苔遍布",
                "scene_sheet": "scenes/古庙.png",
            },
        },
        "props": {
            "玉簪": {"description": "祖传玉簪"},
        },
        "products": {},
        **overrides,
    }


def _ad_shot(shot_id: str, **overrides) -> dict:
    return {
        "shot_id": shot_id,
        "section": "opening",
        "duration_seconds": 5,
        "voiceover_text": "一段口播",
        "characters_in_shot": [],
        "scenes": [],
        "props": [],
        "products_in_shot": [],
        "image_prompt": {
            "scene": f"{shot_id} 画面",
            "composition": {"shot_type": "Close-up", "lighting": "自然光", "ambiance": "明亮"},
        },
        "video_prompt": {
            "action": f"{shot_id} 动作",
            "camera_motion": "Static",
            "ambiance_audio": "环境音",
            "dialogue": [],
        },
        **overrides,
    }


# ── tests ─────────────────────────────────────────────────────────────────


class TestNormalGeneration:
    """a. 正常生成 pack。"""

    def test_generates_pack_structure(self):
        project = _project()
        shots = [
            _ad_shot("E1S01", characters_in_shot=["女主"], scenes=["古庙"]),
            _ad_shot("E1S02", characters_in_shot=["女主", "老者"], props=["玉簪"]),
        ]
        pack = build_context_pack(project, {"shots": shots})

        assert pack["schema_version"] == 1
        assert pack["content_mode"] == "ad"
        assert pack["source_script"] == ""  # 未传 source_script 时为空
        assert pack["logline"] == "一段关于勇气与牺牲的短篇故事"
        assert pack["theme"] == "勇气"

    def test_style_bible(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []})
        sb = pack["style_bible"]
        assert sb["aspect_ratio"] == "9:16"
        assert sb["style"] == "国风水墨"
        assert sb["style_description"] == "水墨画风，淡雅色调"


class TestReferencedShots:
    """b. referenced_shots 正确。"""

    def test_referenced_shots_for_characters(self):
        project = _project()
        shots = [
            _ad_shot("E1S01", characters_in_shot=["女主"]),
            _ad_shot("E1S02", characters_in_shot=["女主", "老者"]),
        ]
        pack = build_context_pack(project, {"shots": shots})

        chars = {c["name"]: c for c in pack["characters_with_aliases"]}
        assert chars["女主"]["referenced_shots"] == ["E1S01", "E1S02"]
        assert chars["老者"]["referenced_shots"] == ["E1S02"]

    def test_referenced_shots_for_scenes(self):
        project = _project()
        shots = [_ad_shot("E1S01", scenes=["古庙"])]
        pack = build_context_pack(project, {"shots": shots})
        scene = pack["scenes"][0]
        assert scene["referenced_shots"] == ["E1S01"]

    def test_unreferenced_asset_has_empty_list(self):
        project = _project()
        shots: list = []
        pack = build_context_pack(project, {"shots": shots})
        chars = {c["name"]: c for c in pack["characters_with_aliases"]}
        assert chars["女主"]["referenced_shots"] == []


class TestHasSheet:
    """c. has_sheet 正确。"""

    def test_has_sheet_true(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []})
        chars = {c["name"]: c for c in pack["characters_with_aliases"]}
        assert chars["女主"]["has_sheet"] is True
        assert chars["老者"]["has_sheet"] is False

    def test_scene_has_sheet(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []})
        scene = pack["scenes"][0]
        assert scene["has_sheet"] is True

    def test_prop_has_sheet_false(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []})
        prop = pack["props"][0]
        assert prop["has_sheet"] is False


class TestShotIntentMap:
    """d. shot_intent_map 正确提取 visual_intent / motion_intent。"""

    def test_extracts_visual_intent_from_structured(self):
        project = _project()
        shots = [_ad_shot("E1S01", image_prompt={
            "scene": "女主立于古庙前，风吹长发",
            "composition": {"shot_type": "Medium Shot", "lighting": "柔光", "ambiance": "肃穆"},
        })]
        pack = build_context_pack(project, {"shots": shots})
        shot = pack["shot_intent_map"][0]
        assert shot["visual_intent"] == "女主立于古庙前，风吹长发"

    def test_extracts_motion_intent(self):
        project = _project()
        shots = [_ad_shot("E1S01", video_prompt={
            "action": "女主缓缓转身，目光坚定",
            "camera_motion": "Tracking Shot",
            "ambiance_audio": "风声",
            "dialogue": [],
        })]
        pack = build_context_pack(project, {"shots": shots})
        shot = pack["shot_intent_map"][0]
        assert shot["motion_intent"] == "女主缓缓转身，目光坚定"

    def test_prompt_ready_true(self):
        project = _project()
        shots = [_ad_shot("E1S01")]
        pack = build_context_pack(project, {"shots": shots})
        assert pack["shot_intent_map"][0]["prompt_ready"] is True

    def test_prompt_ready_false_when_empty(self):
        project = _project()
        shots = [_ad_shot("E1S01", image_prompt="", video_prompt="")]
        pack = build_context_pack(project, {"shots": shots})
        assert pack["shot_intent_map"][0]["prompt_ready"] is False


class TestAssetReferenceState:
    """e. preflight 信息进入 asset_reference_state。"""

    def test_unregistered_asset_in_missing(self):
        project = _project()
        shots = [_ad_shot("E1S01", characters_in_shot=["不存在的人"])]
        pack = build_context_pack(project, {"shots": shots})
        state = pack["asset_reference_state"]
        assert len(state["missing_assets"]) >= 1

    def test_asset_without_sheet_in_state(self):
        project = _project()
        shots = [_ad_shot("E1S01", characters_in_shot=["老者"])]
        pack = build_context_pack(project, {"shots": shots})
        state = pack["asset_reference_state"]
        # 老者已注册但无 sheet → ASSET_WITHOUT_SHEET (blocking)
        assert len(state["assets_without_sheet"]) >= 1

    def test_shot_without_references(self):
        project = _project()
        shots = [_ad_shot("E1S01")]  # 所有引用字段为空
        pack = build_context_pack(project, {"shots": shots})
        state = pack["asset_reference_state"]
        assert "E1S01" in state["shots_without_references"]

    def test_clean_project_has_empty_state(self):
        project = _project()
        shots = [_ad_shot("E1S01", characters_in_shot=["女主"], scenes=["古庙"])]
        pack = build_context_pack(project, {"shots": shots})
        state = pack["asset_reference_state"]
        # 女主有 sheet → OK；古庙有 sheet → OK
        assert len(state["missing_assets"]) == 0
        assert len(state["assets_without_sheet"]) == 0


class TestNonAdMode:
    """非 ad 模式返回空 pack。"""

    def test_non_ad_returns_empty(self):
        project = _project(content_mode="narration")
        pack = build_context_pack(project, {"shots": []})
        assert pack["schema_version"] == 1
        assert pack["content_mode"] == "narration"
        assert pack["shot_intent_map"] == []
        assert pack["characters_with_aliases"] == []


class TestSourceScript:
    """source_script 参数。"""

    def test_default_empty(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []})
        assert pack["source_script"] == ""

    def test_custom_script_file(self):
        project = _project()
        pack = build_context_pack(project, {"shots": []}, source_script="my_ad.json")
        assert pack["source_script"] == "my_ad.json"

    def test_full_generation_with_script_name(self):
        project = _project()
        shots = [_ad_shot("E1S01")]
        pack = build_context_pack(project, {"shots": shots}, source_script="scripts/episode_1.json")
        assert pack["source_script"] == "scripts/episode_1.json"
        assert pack["shot_intent_map"][0]["shot_id"] == "E1S01"

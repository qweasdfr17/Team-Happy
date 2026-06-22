"""资产引用预检（lib/preflight/checks.py）单元测试。"""


from lib.preflight.checks import run_preflight
from lib.preflight.models import Severity

# ── helpers ───────────────────────────────────────────────────────────────

def _project(**overrides) -> dict:
    """构造 project.json 样板。"""
    return {
        "content_mode": "ad",
        "characters": {
            "主角A": {"description": "主角", "character_sheet": "characters/主角A.png"},
            "无图角色": {"description": "没有 sheet"},
        },
        "scenes": {
            "客厅": {"description": "温馨客厅", "scene_sheet": "scenes/客厅.png"},
            "无图场景": {"description": "没有 sheet"},
        },
        "props": {
            "手机": {"description": "智能手机", "prop_sheet": "props/手机.png"},
        },
        "products": {
            "产品X": {
                "description": "测试产品",
                "brand": "X牌",
                "product_sheet": "products/产品X.png",
                "reference_images": ["products/refs/X_01.jpg"],
            },
            "无图产品": {"description": "没有 sheet 也没有原图"},
        },
        **overrides,
    }


def _shot(shot_id: str, **overrides) -> dict:
    """构造 AdShot 样板。"""
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
            "scene": f"{shot_id} 画面描述",
            "composition": {"shot_type": "Close-up", "lighting": "自然光", "ambiance": "明亮"},
        },
        "video_prompt": {
            "action": f"{shot_id} 动作描述",
            "camera_motion": "Static",
            "ambiance_audio": "环境音",
            "dialogue": [],
        },
        **overrides,
    }


def _report_issues(report, severity: Severity | None = None):
    """展平预检报告为 (severity, code, location) 列表。"""
    if severity is None or severity == Severity.blocking:
        source = report.blocking
    elif severity == Severity.warning:
        source = report.warnings
    else:
        source = report.info
    return [(i.severity, i.code, i.location) for i in source]


def _codes(report, severity: Severity) -> set:
    return {i.code for i in (report.blocking if severity == Severity.blocking else
           report.warnings if severity == Severity.warning else report.info)}


# ── tests ─────────────────────────────────────────────────────────────────


class TestNormalAssets:
    """a. 正常资产都有图，无 warning。"""

    def test_all_assets_have_sheets(self):
        project = _project()
        shots = [
            _shot("E1S01", characters_in_shot=["主角A"], scenes=["客厅"], props=["手机"]),
            _shot("E1S02", characters_in_shot=["主角A"]),
        ]
        report = run_preflight(project, {"shots": shots})
        assert report.blocking_count == 0
        assert report.warning_count == 0
        # info 可能触发 PROMPT_MENTIONS_UNREFERENCED（prompt text 里没有 @ 但引用了），
        # 当前检查基于 prompt 文本包含资产名 —— 我们的测试 prompt 只说"E1S01 画面描述"，
        # 不包含"主角A"等资产名，所以 info 也为 0
        assert report.info_count == 0


class TestUnregisteredReference:
    """b. 引用不存在资产，blocking。"""

    def test_unregistered_character(self):
        project = _project()
        shots = [_shot("E1S01", characters_in_shot=["不存在的角色"])]
        report = run_preflight(project, {"shots": shots})
        assert "UNREGISTERED_REFERENCE" in _codes(report, Severity.blocking)

    def test_unregistered_scene(self):
        project = _project()
        shots = [_shot("E1S01", scenes=["不存在的场景"])]
        report = run_preflight(project, {"shots": shots})
        assert "UNREGISTERED_REFERENCE" in _codes(report, Severity.blocking)

    def test_unregistered_product(self):
        project = _project()
        shots = [_shot("E1S01", products_in_shot=["不存在的产品"])]
        report = run_preflight(project, {"shots": shots})
        assert "UNREGISTERED_REFERENCE" in _codes(report, Severity.blocking)


class TestAssetWithoutSheet:
    """c. 资产存在但 sheet 缺失，blocking。"""

    def test_character_without_sheet(self):
        project = _project()
        shots = [_shot("E1S01", characters_in_shot=["无图角色"])]
        report = run_preflight(project, {"shots": shots})
        assert "ASSET_WITHOUT_SHEET" in _codes(report, Severity.blocking)

    def test_scene_without_sheet(self):
        project = _project()
        shots = [_shot("E1S01", scenes=["无图场景"])]
        report = run_preflight(project, {"shots": shots})
        assert "ASSET_WITHOUT_SHEET" in _codes(report, Severity.blocking)


class TestProductWithoutRef:
    """产品镜头 products_in_shot 非空但产品没有 sheet 或原图 → blocking。"""

    def test_product_without_any_images(self):
        project = _project()
        shots = [_shot("E1S01", products_in_shot=["无图产品"])]
        report = run_preflight(project, {"shots": shots})
        assert "PRODUCT_WITHOUT_REF" in _codes(report, Severity.blocking)

    def test_product_with_sheet_is_ok(self):
        project = _project()
        shots = [_shot("E1S01", products_in_shot=["产品X"])]
        report = run_preflight(project, {"shots": shots})
        assert "PRODUCT_WITHOUT_REF" not in _codes(report, Severity.blocking)

    def test_product_with_only_originals_is_ok(self):
        """只有原图没有 sheet 也算有图。"""
        project = _project()
        project["products"]["只有原图"] = {
            "description": "没有 sheet",
            "reference_images": ["products/refs/only_01.jpg"],
        }
        shots = [_shot("E1S01", products_in_shot=["只有原图"])]
        report = run_preflight(project, {"shots": shots})
        assert "PRODUCT_WITHOUT_REF" not in _codes(report, Severity.blocking)


class TestNoReferences:
    """d. 镜头无任何引用，warning。"""

    def test_shot_without_any_references(self):
        project = _project()
        shots = [_shot("E1S01")]  # 所有引用字段为空
        report = run_preflight(project, {"shots": shots})
        assert "NO_REFERENCES" in _codes(report, Severity.warning)

    def test_shot_with_references_is_ok(self):
        project = _project()
        shots = [_shot("E1S01", characters_in_shot=["主角A"])]
        report = run_preflight(project, {"shots": shots})
        assert "NO_REFERENCES" not in _codes(report, Severity.warning)


class TestEmptyPrompt:
    """e. 空 prompt，warning。"""

    def test_empty_image_prompt_none(self):
        project = _project()
        shots = [_shot("E1S01", image_prompt=None)]
        report = run_preflight(project, {"shots": shots})
        assert "EMPTY_IMAGE_PROMPT" in _codes(report, Severity.warning)

    def test_empty_image_prompt_empty_str(self):
        project = _project()
        shots = [_shot("E1S01", image_prompt="")]
        report = run_preflight(project, {"shots": shots})
        assert "EMPTY_IMAGE_PROMPT" in _codes(report, Severity.warning)

    def test_empty_video_prompt_none(self):
        project = _project()
        shots = [_shot("E1S01", video_prompt=None)]
        report = run_preflight(project, {"shots": shots})
        assert "EMPTY_VIDEO_PROMPT" in _codes(report, Severity.warning)

    def test_empty_video_prompt_empty_dict(self):
        project = _project()
        shots = [_shot("E1S01", video_prompt={})]
        report = run_preflight(project, {"shots": shots})
        assert "EMPTY_VIDEO_PROMPT" in _codes(report, Severity.warning)

    def test_structured_image_prompt_with_content_is_ok(self):
        project = _project()
        shots = [_shot("E1S01", image_prompt={
            "scene": "有内容的画面",
            "composition": {"shot_type": "Close-up", "lighting": "柔光", "ambiance": "温暖"},
        })]
        report = run_preflight(project, {"shots": shots})
        assert "EMPTY_IMAGE_PROMPT" not in _codes(report, Severity.warning)


class TestEmptyShots:
    """边界：剧本没有 shots。"""

    def test_no_shots(self):
        project = _project()
        report = run_preflight(project, {"shots": []})
        assert report.warning_count == 1
        assert report.warnings[0].code == "NO_SHOTS"


class TestPromptMentions:
    """f. prompt 文本提到资产名但引用字段未注册 → info。"""

    def test_mention_without_reference(self):
        project = _project()
        # prompt 里写了"主角A"但 characters_in_shot 是空的
        shots = [_shot("E1S01",
                        characters_in_shot=[],
                        image_prompt={
                            "scene": "主角A 站在客厅里",
                            "composition": {"shot_type": "Medium Shot", "lighting": "柔光", "ambiance": "温馨"},
                        })]
        report = run_preflight(project, {"shots": shots})
        info_codes = _codes(report, Severity.info)
        assert "PROMPT_MENTIONS_UNREFERENCED" in info_codes

    def test_mention_with_reference_no_info(self):
        project = _project()
        # prompt 提到"主角A"且 characters_in_shot 也包含了 → 不触发 info
        # 注意：prompt 里提到"客厅"但 scenes 字段为空，会触发 info，所以用不含场景名的 prompt
        shots = [_shot("E1S01",
                        characters_in_shot=["主角A"],
                        image_prompt={
                            "scene": "主角A 站在房间中央",
                            "composition": {"shot_type": "Medium Shot", "lighting": "柔光", "ambiance": "温馨"},
                        })]
        report = run_preflight(project, {"shots": shots})
        # 引用了主角A → 不应有主角A 的 PROMPT_MENTIONS_UNREFERENCED
        char_info = [i for i in report.info if i.code == "PROMPT_MENTIONS_UNREFERENCED" and "主角A" in i.message]
        assert len(char_info) == 0


class TestReferenceUnits:
    """g. reference_units 预检。"""

    def test_unit_with_registered_assets(self):
        project = _project()
        shots = [_shot("E1S01", characters_in_shot=["主角A"], scenes=["客厅"])]
        script = {
            "shots": shots,
            "reference_units": [{
                "unit_id": "E1U01",
                "shot_ids": ["E1S01"],
                "references": [
                    {"type": "character", "name": "主角A"},
                    {"type": "scene", "name": "客厅"},
                ],
            }],
        }
        report = run_preflight(project, script)
        # 不应有 unit 级的阻断
        unit_blocking = [i for i in report.blocking if i.code == "UNIT_UNREGISTERED_REFERENCE"]
        assert len(unit_blocking) == 0

    def test_unit_with_unregistered_asset(self):
        project = _project()
        script = {
            "shots": [_shot("E1S01")],
            "reference_units": [{
                "unit_id": "E1U01",
                "shot_ids": ["E1S01"],
                "references": [
                    {"type": "character", "name": "不存在的角色"},
                ],
            }],
        }
        report = run_preflight(project, script)
        assert "UNIT_UNREGISTERED_REFERENCE" in _codes(report, Severity.blocking)

    def test_unit_with_asset_without_sheet(self):
        project = _project()
        script = {
            "shots": [_shot("E1S01")],
            "reference_units": [{
                "unit_id": "E1U01",
                "shot_ids": ["E1S01"],
                "references": [
                    {"type": "character", "name": "无图角色"},
                ],
            }],
        }
        report = run_preflight(project, script)
        assert "UNIT_ASSET_WITHOUT_SHEET" in _codes(report, Severity.blocking)


class TestSummary:
    """h. 验证 summary 计数。"""

    def test_summary_counts(self):
        project = _project()
        shots = [
            _shot("E1S01", characters_in_shot=["不存在的角色"], products_in_shot=["无图产品"]),
            _shot("E1S02", video_prompt=""),
        ]
        report = run_preflight(project, {"shots": shots})
        d = report.to_dict()
        s = d["summary"]
        # "不存在的角色" → UNREGISTERED_REFERENCE (blocking)
        # "无图产品" → 已注册但无图 → PRODUCT_WITHOUT_REF (blocking)
        assert s["blocking_count"] == 2
        assert s["warning_count"] >= 2  # NO_REFERENCES x2 + EMPTY_VIDEO_PROMPT + ...
        assert s["blocking_count"] + s["warning_count"] + s["info_count"] == len(d["blocking"]) + len(d["warnings"]) + len(d["info"])

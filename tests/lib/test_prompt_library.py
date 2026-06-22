"""Prompt Library（lib/prompt_library/）单元测试。"""

import json
import re
import tempfile
from pathlib import Path

import pytest

from lib.prompt_library.loader import load_builtins, load_prompt_library, template_list
from lib.prompt_library.models import PromptTemplate
from lib.prompt_library.resolver import resolve_prompts

# ── helpers ───────────────────────────────────────────────────────────────

def _custom_json(content: list[dict]) -> str:
    return json.dumps(content, ensure_ascii=False, indent=2)


def _write_custom(project_dir: Path, filename: str, content: list[dict]) -> None:
    d = project_dir / "context" / "prompt_library"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(_custom_json(content), encoding="utf-8")


# ── tests ─────────────────────────────────────────────────────────────────


class TestLoadBuiltins:
    """a. builtins 能加载。"""

    def test_loads_all_categories(self):
        templates = load_builtins()
        assert len(templates) >= 7  # 至少 7 个模板
        ids = {t.id for t in templates}
        assert "character_manga_001" in ids
        assert "video_manga_motion_001" in ids
        assert "negative_manga_default_001" in ids

    def test_all_have_valid_category(self):
        valid = {
            "character_asset", "scene_asset", "prop_asset",
            "video_prompt", "negative_prompt", "director_rewrite", "case_study",
        }
        for t in load_builtins():
            assert t.category in valid, f"{t.id} has invalid category: {t.category}"

    def test_source_is_builtin(self):
        for t in load_builtins():
            assert t.source == "builtin"


class TestCategoryFilter:
    """b. category 过滤正确。"""

    def test_filters_by_category(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt")
        assert len(items) >= 2
        for item in items:
            assert item["category"] == "video_prompt"

    def test_empty_category_returns_all(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="", limit=50)
        assert len(items) >= 7

    def test_nonexistent_category_returns_empty(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="nonexistent")
        assert items == []


class TestTagsSorting:
    """c. tags 命中排序正确。"""

    def test_tag_match_scores_higher(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", tags=["漫剧", "竖屏"], limit=5)
        # 漫剧+竖屏 双命中排最前
        assert len(items) >= 1
        # 第一个应同时有"漫剧"和"竖屏"
        first_tags = items[0]["tags"]
        assert "漫剧" in first_tags

    def test_more_tags_ranks_higher(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", tags=["漫剧"], limit=5)
        # 有"漫剧"标签的排前面
        for item in items:
            if "漫剧" in item["tags"]:
                return  # found at least one
        pytest.fail("No video_prompt with tag '漫剧' found")


class TestQuerySorting:
    """d. query 命中排序正确。"""

    def test_title_match_scores_higher(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="negative_prompt", query="漫剧", limit=5)
        assert len(items) >= 1
        # 标题含"漫剧"的排最前
        assert "漫剧" in items[0]["title"]

    def test_query_in_content(self):
        lib = load_prompt_library()
        # 写实标签 + 动作 query 组合，确保写实动作模板排前面
        items = resolve_prompts(lib, tags=["写实"], query="手持", limit=10)
        # 应该返回包含"手持"的模板（video_realistic_action_001）
        found = any("手持" in item.get("content", "") for item in items)
        assert found


class TestLimit:
    """e. limit 生效。"""

    def test_limit_1(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, limit=1)
        assert len(items) == 1

    def test_limit_3(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, limit=3)
        assert len(items) <= 3

    def test_limit_larger_than_total(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, limit=100)
        assert len(items) == len(lib)


class TestCustomOverride:
    """f. 自定义模板覆盖 builtin。"""

    def test_custom_overrides_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _write_custom(proj, "custom.json", [{
                "id": "character_manga_001",
                "category": "character_asset",
                "title": "我的自定义角色模板",
                "tags": ["自定义"],
                "content": "覆盖了内置版本",
                "priority": 99,
            }])
            lib = load_prompt_library(proj)
            t = lib["character_manga_001"]
            assert t.source == "custom"
            assert t.title == "我的自定义角色模板"
            assert t.content == "覆盖了内置版本"

    def test_custom_adds_new_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _write_custom(proj, "custom.json", [{
                "id": "my_custom_001",
                "category": "video_prompt",
                "title": "我的专属模板",
                "tags": ["专属"],
                "content": "全新的模板",
                "priority": 100,
            }])
            lib = load_prompt_library(proj)
            assert "my_custom_001" in lib
            assert lib["my_custom_001"].source == "custom"


class TestNoMatches:
    """g. 无匹配返回空列表。"""

    def test_no_category_match(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="nonexistent")
        assert items == []

    def test_no_query_match(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, query="zzz_nonexistent_zzz", limit=10)
        # 即使 query 不命中，只要 category 为空仍返回所有（按 priority 排）
        assert len(items) >= 1

    def test_template_list_sorted(self):
        lib = load_prompt_library()
        items = template_list(lib)
        for i in range(len(items) - 1):
            assert items[i]["priority"] >= items[i + 1]["priority"]


class TestPromptTemplateModel:
    """模型序列化/反序列化。"""

    def test_from_dict(self):
        d = {
            "id": "test_001",
            "category": "video_prompt",
            "title": "测试",
            "tags": ["a", "b"],
            "priority": 60,
        }
        t = PromptTemplate.from_dict(d)
        assert t.id == "test_001"
        assert t.tags == ["a", "b"]
        assert t.priority == 60
        assert t.source == "builtin"

    def test_to_dict_roundtrip(self):
        t = PromptTemplate(id="x", category="c", content="hello", priority=77, source="custom")
        d = t.to_dict()
        t2 = PromptTemplate.from_dict(d)
        assert t2.id == "x"
        assert t2.content == "hello"
        assert t2.priority == 77

    def test_format_type_default(self):
        t = PromptTemplate.from_dict({"id": "t1", "category": "c"})
        assert t.format_type == "plain"

    def test_format_type_roundtrip(self):
        t = PromptTemplate(id="f1", category="x", format_type="reference_video_multishot", variables=["a", "b", "c"])
        d = t.to_dict()
        assert d["format_type"] == "reference_video_multishot"
        assert d["variables"] == ["a", "b", "c"]
        t2 = PromptTemplate.from_dict(d)
        assert t2.format_type == "reference_video_multishot"
        assert t2.variables == ["a", "b", "c"]

    def test_variables_in_api_dict(self):
        t = PromptTemplate(id="v1", category="x", format_type="template", variables=["name", "description"])
        d = t.to_dict()
        assert "format_type" in d
        assert "variables" in d
        assert d["format_type"] == "template"
        assert d["variables"] == ["name", "description"]


class TestReferenceVideoMultishot:
    """reference_video_multishot 模板检索。"""

    def test_tags_match_ranks_first(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", tags=["参考图", "多切片"], limit=3)
        assert len(items) >= 1
        assert items[0]["id"] == "video_reference_multishot_manga_001"

    def test_query_hits_multishot_content(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", query="图1", limit=5)
        ids = [i["id"] for i in items]
        assert "video_reference_multishot_manga_001" in ids

    def test_query_hits_slice(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", query="切片段", limit=5)
        ids = [i["id"] for i in items]
        assert "video_reference_multishot_manga_001" in ids

    def test_has_format_type_and_variables(self):
        lib = load_prompt_library()
        items = resolve_prompts(lib, category="video_prompt", tags=["参考图"], limit=1)
        assert len(items) == 1
        assert items[0]["format_type"] == "reference_video_multishot"
        assert len(items[0]["variables"]) >= 5
        assert "image_reference_map" in items[0]["variables"]
        assert "shot_slices" in items[0]["variables"]

    def test_default_format_type_is_plain(self):
        """未声明的内置模板默认 format_type 为 plain（builtins 中所有模板已显式声明则不触发，此处测模型默认）。"""
        t = PromptTemplate.from_dict({"id": "x", "category": "c"})
        assert t.format_type == "plain"
        assert t.variables == []

    def test_all_builtins_have_explicit_format_type(self):
        for t in load_builtins():
            assert t.format_type in ("plain", "raw", "template", "reference", "reference_video_multishot"), \
                f"{t.id} has unexpected format_type: {t.format_type}"

    def test_placeholders_subset_of_variables(self):
        """content 中的 {placeholder} 必须是 variables 的子集。"""
        lib = load_prompt_library()
        t = lib["video_reference_multishot_manga_001"]
        placeholders = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", t.content))
        var_set = set(t.variables)
        missing = placeholders - var_set
        assert missing == set(), f"content 中有未声明的变量: {missing}"

    def test_all_required_variables_declared(self):
        """所有核心变量都在 variables 中声明。"""
        lib = load_prompt_library()
        t = lib["video_reference_multishot_manga_001"]
        required = {
            "image_reference_map", "global_style", "scene_design",
            "target_emotion", "shot_slices", "camera_motion",
            "dialogue", "negative_rules",
        }
        assert required <= set(t.variables), \
            f"缺少变量: {required - set(t.variables)}"

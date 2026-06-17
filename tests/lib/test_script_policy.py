"""script_policy 模块测试。"""

import pytest

from lib.script_policy import (
    DEFAULT_SCRIPT_POLICY,
    is_preserve_mode,
    is_suggest_mode,
    resolve_script_policy,
    validate_script_policy,
)


class TestResolveScriptPolicy:
    def test_default_preserve_when_missing(self):
        assert resolve_script_policy({}) == {"mode": "preserve"}

    def test_default_preserve_when_none(self):
        assert resolve_script_policy({"script_policy": None}) == {"mode": "preserve"}

    def test_explicit_preserve(self):
        assert resolve_script_policy({"script_policy": {"mode": "preserve"}}) == {"mode": "preserve"}

    def test_explicit_suggest(self):
        assert resolve_script_policy({"script_policy": {"mode": "suggest_rewrite"}}) == {"mode": "suggest_rewrite"}

    def test_invalid_mode_falls_back_to_preserve(self):
        assert resolve_script_policy({"script_policy": {"mode": "free_for_all"}}) == {"mode": "preserve"}


class TestIsPreserveMode:
    def test_preserve(self):
        assert is_preserve_mode({"script_policy": {"mode": "preserve"}})

    def test_not_preserve(self):
        assert not is_preserve_mode({"script_policy": {"mode": "suggest_rewrite"}})

    def test_default_is_preserve(self):
        assert is_preserve_mode({})


class TestIsSuggestMode:
    def test_suggest(self):
        assert is_suggest_mode({"script_policy": {"mode": "suggest_rewrite"}})

    def test_not_suggest(self):
        assert not is_suggest_mode({"script_policy": {"mode": "preserve"}})


class TestValidate:
    def test_valid_preserve(self):
        assert validate_script_policy({"mode": "preserve"}) == {"mode": "preserve"}

    def test_valid_suggest(self):
        assert validate_script_policy({"mode": "suggest_rewrite"}) == {"mode": "suggest_rewrite"}

    def test_invalid_mode_fallback(self):
        assert validate_script_policy({"mode": "bad"}) == {"mode": "preserve"}

    def test_non_dict_fallback(self):
        assert validate_script_policy("not a dict") == DEFAULT_SCRIPT_POLICY


class TestPromptTails:
    """preserve / suggest 提示词尾注入常量存在且非空。"""
    from lib.script_policy import PRESERVE_PROMPT_TAIL, SUGGEST_REWRITE_PROMPT_TAIL

    def test_preserve_tail_non_empty(self):
        assert len(self.PRESERVE_PROMPT_TAIL) > 50

    def test_suggest_tail_non_empty(self):
        assert len(self.SUGGEST_REWRITE_PROMPT_TAIL) > 50

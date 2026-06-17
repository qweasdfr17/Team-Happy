"""Auth bypass tests for AUTH_ENABLED=false (local no-login mode)."""

import os

import pytest

from server.auth import CurrentUserInfo, _anonymous_user, is_auth_enabled


def test_is_auth_enabled_defaults_true(monkeypatch):
    """默认（未设环境变量）auth 开启。"""
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    assert is_auth_enabled() is True


def test_is_auth_enabled_false(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    assert is_auth_enabled() is False


def test_is_auth_enabled_zero(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "0")
    assert is_auth_enabled() is False


def test_is_auth_enabled_no(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "no")
    assert is_auth_enabled() is False


def test_is_auth_enabled_off(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "off")
    assert is_auth_enabled() is False


def test_is_auth_enabled_true(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    assert is_auth_enabled() is True


def test_is_auth_enabled_empty_defaults_true(monkeypatch):
    """空串回退到默认（开启）。"""
    monkeypatch.setenv("AUTH_ENABLED", "")
    assert is_auth_enabled() is True


def test_anonymous_user_id():
    user = _anonymous_user()
    assert user.sub == "local"
    assert user.role == "admin"


def test_anonymous_user_frozen():
    user = _anonymous_user()
    with pytest.raises(Exception):
        user.sub = "hack"

from __future__ import annotations

import pytest

from lib.prompt_source_guard import (
    PromptSourceGuardError,
    assert_image_prompt_skill_generated,
    assert_image_prompt_skill_generated_from_payload,
    assert_video_prompt_skill_generated,
    assert_video_prompt_skill_generated_from_payload,
)


@pytest.mark.parametrize(
    ("item", "assertion"),
    [
        ({"image_prompt_source": "skill"}, assert_image_prompt_skill_generated),
        ({"video_prompt_source": "skill"}, assert_video_prompt_skill_generated),
        ({}, assert_image_prompt_skill_generated),
        ({}, assert_video_prompt_skill_generated),
    ],
)
def test_prompt_source_guard_allows_skill_and_legacy_missing_markers(item, assertion):
    assertion(item, "E1S1")


@pytest.mark.parametrize(
    ("item", "assertion"),
    [
        ({"image_prompt_source": "pending"}, assert_image_prompt_skill_generated),
        ({"image_prompt_source": "legacy"}, assert_image_prompt_skill_generated),
        ({"video_prompt_source": "pending"}, assert_video_prompt_skill_generated),
        ({"video_prompt_source": "legacy"}, assert_video_prompt_skill_generated),
    ],
)
def test_prompt_source_guard_rejects_explicit_non_skill_markers(item, assertion):
    with pytest.raises(PromptSourceGuardError):
        assertion(item, "E1S1")


@pytest.mark.parametrize(
    ("payload", "assertion"),
    [
        ({"image_prompt_source": "skill"}, assert_image_prompt_skill_generated_from_payload),
        ({"video_prompt_source": "skill"}, assert_video_prompt_skill_generated_from_payload),
        ({}, assert_image_prompt_skill_generated_from_payload),
        ({}, assert_video_prompt_skill_generated_from_payload),
    ],
)
def test_prompt_source_guard_payload_allows_skill_and_legacy_missing_markers(payload, assertion):
    assertion(payload, "E1S1")


@pytest.mark.parametrize(
    ("payload", "assertion"),
    [
        ({"image_prompt_source": "pending"}, assert_image_prompt_skill_generated_from_payload),
        ({"prompt_source": "legacy"}, assert_image_prompt_skill_generated_from_payload),
        ({"video_prompt_source": "pending"}, assert_video_prompt_skill_generated_from_payload),
        ({"prompt_source": "legacy"}, assert_video_prompt_skill_generated_from_payload),
    ],
)
def test_prompt_source_guard_payload_rejects_explicit_non_skill_markers(payload, assertion):
    with pytest.raises(PromptSourceGuardError):
        assertion(payload, "E1S1")

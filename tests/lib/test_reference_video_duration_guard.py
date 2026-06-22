from lib.reference_video.duration_guard import (
    normalize_reference_video_script,
    normalize_reference_video_units,
    resolve_reference_video_max_duration,
    split_duration,
)


def test_split_duration_balances_over_cap():
    assert split_duration(17, 15) == [9, 8]
    assert split_duration(31, 15) == [11, 10, 10]


def test_resolve_reference_video_max_duration_never_exceeds_15():
    project = {"_supported_durations": list(range(4, 31))}

    assert resolve_reference_video_max_duration(project) == 15
    assert resolve_reference_video_max_duration(project, max_duration=8) == 8


def test_normalize_splits_units_by_total_duration_and_rewrites_ids():
    units = [
        {
            "unit_id": "E1U1",
            "shots": [
                {"duration": 10, "text": "开门"},
                {"duration": 7, "text": "对峙"},
            ],
            "references": [{"type": "character", "name": "主角"}],
            "duration_seconds": 17,
            "generated_assets": {"video_clip": "reference_videos/E1U1.mp4", "status": "completed"},
        }
    ]

    normalized = normalize_reference_video_units(units, episode=1, project={"_supported_durations": list(range(4, 16))})

    assert [u["unit_id"] for u in normalized] == ["E1U1", "E1U2"]
    assert [u["duration_seconds"] for u in normalized] == [10, 7]
    assert all(u["duration_seconds"] <= 15 for u in normalized)
    assert normalized[0]["generated_assets"]["video_clip"] is None


def test_normalize_splits_single_long_shot_into_independent_units():
    script = {
        "video_units": [
            {
                "unit_id": "E2U1",
                "shots": [{"duration": 17, "text": "长镜头动作"}],
                "references": [],
                "duration_seconds": 17,
            }
        ],
        "metadata": {},
    }

    normalized = normalize_reference_video_script(script, episode=2, project={"_supported_durations": list(range(4, 16))})

    assert [u["unit_id"] for u in normalized] == ["E2U1", "E2U2"]
    assert [u["duration_seconds"] for u in normalized] == [9, 8]
    assert all("自动拆分" in u["shots"][0]["text"] for u in normalized)
    assert script["duration_seconds"] == 17
    assert script["metadata"]["total_units"] == 2

from lib.reference_video.premium_prompt import apply_premium_prompt_to_unit
from lib.script_generator import (
    _hydrate_reference_video_unit_texts,
    _parse_reference_step1_shots,
)


STEP1 = """## 参考视频单元拆分结果

### 完整 shot 文本（供 Step 2 使用）

#### E1U1

Shot 1 (6s): @[中学走廊] 少年欧阳韬抱紧习题册退让。
Shot 2 (8s): @[中学走廊] 学生冉乐乐快步赶来。

#### E1U2

Shot 1 (5s): @[欧阳家客厅] 李卫红将成绩单拍在茶几上。
"""


def test_parse_reference_step1_shots_extracts_visual_text():
    parsed = _parse_reference_step1_shots(STEP1)

    assert parsed["E1U1"] == [
        {"duration": 6, "text": "@[中学走廊] 少年欧阳韬抱紧习题册退让。"},
        {"duration": 8, "text": "@[中学走廊] 学生冉乐乐快步赶来。"},
    ]
    assert parsed["E1U2"] == [
        {"duration": 5, "text": "@[欧阳家客厅] 李卫红将成绩单拍在茶几上。"},
    ]


def test_parse_reference_step1_shots_stops_before_statistics_section():
    step1 = """### 完整 shot 文本（供 Step 2 使用）

#### E1U12

Shot 1 (8s): @[轻奢私房菜馆包厢] 欧阳韬开口："久别重逢。"

---

### 拆分统计

- **总 unit 数**：12
"""

    parsed = _parse_reference_step1_shots(step1)

    assert parsed["E1U12"] == [
        {"duration": 8, "text": '@[轻奢私房菜馆包厢] 欧阳韬开口："久别重逢。"'}
    ]


def test_hydrate_reference_video_unit_texts_fills_blank_final_schema_output():
    script = {
        "video_units": [
            {
                "unit_id": "E1U1",
                "shots": [{"duration": 6, "text": ""}, {"duration": 8, "text": ""}],
            }
        ]
    }

    updated = _hydrate_reference_video_unit_texts(script, STEP1)

    assert updated == 2
    assert script["video_units"][0]["shots"][0]["text"] == "@[中学走廊] 少年欧阳韬抱紧习题册退让。"
    assert script["video_units"][0]["shots"][1]["text"] == "@[中学走廊] 学生冉乐乐快步赶来。"


def test_apply_premium_prompt_rejects_empty_visual_text():
    unit = {
        "unit_id": "E1U1",
        "shots": [{"duration": 6, "text": ""}],
        "references": [],
        "duration_seconds": 6,
    }

    try:
        apply_premium_prompt_to_unit(unit, {})
    except ValueError as exc:
        assert "缺少画面内容" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("empty visual text should be rejected")

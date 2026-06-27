from lib.reference_video.premium_prompt import render_unit_prompt_premium


def _project() -> dict:
    return {
        "characters": {
            "少年欧阳韬": {"character_sheet": "characters/ouyang.png"},
        },
        "scenes": {
            "中学走廊": {"description": "白天的中学走廊", "scene_sheet": "scenes/hallway.png"},
        },
        "props": {},
        "style": "真人电影风格",
        "aspect_ratio": "9:16",
    }


def test_premium_prompt_uses_structured_dialogue_without_changing_visual_text():
    visual_text = "中学走廊白天，少年欧阳韬抱紧习题册，侧身避让围堵他的学生。"
    unit = {
        "unit_id": "E1U01",
        "shots": [
            {
                "text": visual_text,
                "duration": 6,
                "dialogue": [
                    {"speaker": "混混甲", "line": "把身上零花钱全拿出来！"},
                    {"speaker": "少年欧阳韬", "line": "我没有多余零花钱。"},
                ],
            }
        ],
        "references": [
            {"type": "character", "name": "少年欧阳韬"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, _project())

    assert visual_text in prompt
    assert "混混甲「把身上零花钱全拿出来！」" in prompt
    assert "少年欧阳韬「我没有多余零花钱。」" in prompt
    assert "无对白" not in prompt


def test_premium_prompt_extracts_legacy_quoted_dialogue_from_visual_text():
    visual_text = (
        "中学走廊白天，混混甲推搡少年欧阳韬：「把钱拿出来！」"
        "少年欧阳韬抱紧习题册：「我没有多余零花钱。」"
    )
    unit = {
        "unit_id": "E1U01",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "少年欧阳韬"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, _project())

    assert visual_text in prompt
    assert "把钱拿出来！" in prompt
    assert "我没有多余零花钱。" in prompt
    assert "无对白" not in prompt


def test_premium_prompt_extracts_ascii_quoted_dialogue_without_rewriting_visual_text():
    visual_text = (
        '@[中学走廊] @[学生冉乐乐] 径直穿过人群，语气镇定:"校园聚众围堵，全部记大过！"'
        '@[学生水志远] 故作大方开口:"举手之劳，以后咱们就是朋友。"'
    )
    project = _project()
    project["characters"]["学生冉乐乐"] = {"character_sheet": "characters/ran.png"}
    project["characters"]["学生水志远"] = {"character_sheet": "characters/shui.png"}
    unit = {
        "unit_id": "E1U02",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "学生冉乐乐"},
            {"type": "character", "name": "学生水志远"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, project)

    assert visual_text in prompt
    assert "学生冉乐乐「校园聚众围堵，全部记大过！」" in prompt
    assert "学生水志远「举手之劳，以后咱们就是朋友。」" in prompt
    assert "无对白" not in prompt


def test_premium_prompt_uses_previous_mention_for_pronoun_dialogue():
    visual_text = (
        "@[中学走廊] @[学生水志远] 视线锁在两人身上，嘴角笑意一点点僵住。"
        '他故作大方开口:"举手之劳，以后咱们就是朋友。"'
    )
    project = _project()
    project["characters"]["学生水志远"] = {"character_sheet": "characters/shui.png"}
    unit = {
        "unit_id": "E1U02",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "学生水志远"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, project)

    assert visual_text in prompt
    assert "学生水志远「举手之劳，以后咱们就是朋友。」" in prompt


def test_premium_prompt_does_not_use_prop_mention_as_speaker():
    visual_text = (
        "@[老城巷口] 欧阳韬摸向口袋，指尖攥着那块染血的 @[白手帕]，"
        '低声:"已经脏了，等我之后赔你一块更好的。"'
    )
    project = _project()
    project["characters"]["欧阳韬"] = {"character_sheet": "characters/ouyang-adult.png"}
    project["scenes"]["老城巷口"] = {"description": "雨夜巷口", "scene_sheet": "scenes/alley.png"}
    project["props"]["白手帕"] = {"prop_sheet": "props/handkerchief.png"}
    unit = {
        "unit_id": "E1U07",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "欧阳韬"},
            {"type": "scene", "name": "老城巷口"},
            {"type": "prop", "name": "白手帕"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, project)

    assert "欧阳韬「已经脏了，等我之后赔你一块更好的。」" in prompt
    assert "白手帕「已经脏了" not in prompt


def test_premium_prompt_keeps_minor_speaker_and_skips_subtitle_quote():
    visual_text = (
        '字幕："十年后"。@[冉乐乐] 快步上前刚走到门口，电梯间冲出两名保安："没有预约不能靠近总经理办公室！"'
    )
    project = _project()
    project["characters"]["冉乐乐"] = {"character_sheet": "characters/ran-adult.png"}
    unit = {
        "unit_id": "E3U01",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "冉乐乐"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, project)

    assert "「十年后」" not in prompt
    assert "两名保安「没有预约不能靠近总经理办公室！」" in prompt
    assert "冉乐乐「没有预约不能靠近总经理办公室！」" not in prompt


def test_premium_prompt_removes_subtitle_directive_from_visual_text():
    visual_text = '字幕："十年后"。@[冉乐乐] 怀抱资料在走廊踱步。'
    project = _project()
    project["characters"]["冉乐乐"] = {"character_sheet": "characters/ran-adult.png"}
    unit = {
        "unit_id": "E3U01",
        "shots": [{"text": visual_text, "duration": 6}],
        "references": [
            {"type": "character", "name": "冉乐乐"},
            {"type": "scene", "name": "中学走廊"},
        ],
    }

    prompt = render_unit_prompt_premium(unit, project)

    assert "画面：@[冉乐乐] 怀抱资料在走廊踱步。" in prompt
    assert "字幕" not in "\n".join(line for line in prompt.splitlines() if line.startswith("画面："))

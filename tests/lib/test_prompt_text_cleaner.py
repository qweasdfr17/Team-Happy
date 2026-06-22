from lib.reference_video.prompt_text_cleaner import clean_cn_prompt_spacing


def test_clean_cn_prompt_spacing_removes_cjk_prose_spaces():
    text = "中学走廊 白天，少年欧阳韬 怀抱 习题册 缓步穿行，左胸 胸针 随步伐微晃。"

    assert clean_cn_prompt_spacing(text) == "中学走廊白天，少年欧阳韬怀抱习题册缓步穿行，左胸胸针随步伐微晃。"


def test_clean_cn_prompt_spacing_keeps_english_numbers_and_ratios():
    text = "Sundance 2.0 uses AI video prompt, Shot 1, 60fps, 9:16, 0s-0.15s。"

    assert clean_cn_prompt_spacing(text) == text


def test_clean_cn_prompt_spacing_preserves_at_mentions():
    text = "Shot 1 (3s): @张三 推门，@[中学走廊] 白天。"

    assert clean_cn_prompt_spacing(text) == "Shot 1 (3s): @张三 推门，@[中学走廊] 白天。"


def test_clean_cn_prompt_spacing_trims_punctuation_spaces():
    text = "少年欧阳韬 ： 「 藏书多不等于家财万贯 。 」"

    assert clean_cn_prompt_spacing(text) == "少年欧阳韬：「藏书多不等于家财万贯。」"

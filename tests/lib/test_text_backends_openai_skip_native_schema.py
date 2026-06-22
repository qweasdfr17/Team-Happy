"""OpenAI backend — skip native json_schema for DeepSeek/custom providers 测试。"""


from lib.text_backends.openai import _should_skip_native_schema


def test_official_openai_does_not_skip():
    assert not _should_skip_native_schema("openai", "https://api.openai.com/v1")


def test_custom_provider_skips():
    assert _should_skip_native_schema("dashscope", "https://dashscope.aliyuncs.com/compatible-mode/v1")


def test_deepseek_url_skips():
    assert _should_skip_native_schema("openai", "https://api.deepseek.com/v1")


def test_none_base_url_skips_for_non_openai():
    """provider_name 非 openai，无论 base_url 是什么都跳过。"""
    assert _should_skip_native_schema("my-custom-provider", "")


def test_empty_base_url_official_openai_does_not_skip():
    """仅 provider_name==openai 且 base_url 不含 deepseek → 不跳过。"""
    assert not _should_skip_native_schema("openai", "")

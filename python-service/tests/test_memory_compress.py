from memory.memory_system import build_compress_prompt


def test_compress_prompt_includes_laifu_perspective():
    conv_text = "用户: 今天加班好累\n来福: 汪，主人辛苦了"
    prompt = build_compress_prompt(conv_text)
    assert 'laifu_note' in prompt or '来福视角' in prompt
    assert 'summary' in prompt
    assert 'facts' in prompt

import pytest
from agent.dog_agent import parse_llm_response, MOOD_SHIFT_DELTAS

def test_parse_valid_json():
    raw = '{"think": "主人回来了", "reply": "汪！你回来啦！", "action": "happy_run", "mood_shift": "excited"}'
    result = parse_llm_response(raw)
    assert result['reply'] == '汪！你回来啦！'
    assert result['action'] == 'happy_run'
    assert result['mood_shift'] == 'excited'
    assert result['think'] == '主人回来了'

def test_parse_json_with_markdown_wrapper():
    raw = '```json\n{"think": "嗯", "reply": "好的", "action": null, "mood_shift": "neutral"}\n```'
    result = parse_llm_response(raw)
    assert result['reply'] == '好的'

def test_parse_invalid_json_fallback():
    raw = '汪汪！主人你好啊！来福好想你！今天过得怎么样？我好无聊啊！'
    result = parse_llm_response(raw)
    assert len(result['reply']) <= 60
    assert result['action'] is None
    assert result['mood_shift'] == 'neutral'

def test_parse_reply_too_long_truncated():
    raw = '{"think": "x", "reply": "' + '来福说了很多很多话，' * 20 + '", "action": null, "mood_shift": "happy"}'
    result = parse_llm_response(raw)
    assert len(result['reply']) <= 85

def test_mood_shift_deltas_defined():
    assert 'excited' in MOOD_SHIFT_DELTAS
    assert 'happy' in MOOD_SHIFT_DELTAS
    assert 'neutral' in MOOD_SHIFT_DELTAS
    assert 'sad' in MOOD_SHIFT_DELTAS
    assert MOOD_SHIFT_DELTAS['excited']['mood'] > 0
    assert MOOD_SHIFT_DELTAS['sad']['mood'] < 0

def test_parse_extracts_action_from_old_format():
    raw = '汪！主人好！[action:happy_run]'
    result = parse_llm_response(raw)
    assert result['action'] == 'happy_run'
    assert '[action:' not in result['reply']

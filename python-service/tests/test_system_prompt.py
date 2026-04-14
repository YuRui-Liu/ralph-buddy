import pytest
from unittest.mock import MagicMock
from agent.dog_agent import DogBuddyAgent

@pytest.fixture
def agent():
    a = DogBuddyAgent.__new__(DogBuddyAgent)
    a.config = {
        'llm': {'provider': 'openai', 'base_url': '', 'api_key': '', 'model': 'test'},
        'user': {'name': '小明'},
        'pet': {'name': '来福', 'personality': '活泼'},
    }
    a.pet_name = '来福'
    a.pet_personality = '活泼'
    a._cfg_obedience = 60
    a._cfg_snark = 30
    a.owner_emotion_context = None
    a.attr_manager = MagicMock()
    a.attr_manager.build_self_awareness.return_value = '你精神很好，想找主人玩。'
    a.attr_manager.attrs = {'obedience': 60, 'snark': 30}
    return a

def test_prompt_contains_identity(agent):
    prompt = agent._build_system_prompt([])
    assert '来福' in prompt
    assert '田园犬' in prompt

def test_prompt_contains_json_format_instruction(agent):
    prompt = agent._build_system_prompt([])
    assert 'think' in prompt
    assert 'reply' in prompt
    assert 'action' in prompt
    assert 'mood_shift' in prompt
    assert 'JSON' in prompt

def test_prompt_contains_self_awareness(agent):
    prompt = agent._build_system_prompt([])
    assert '你精神很好' in prompt

def test_prompt_contains_reply_length_constraint(agent):
    prompt = agent._build_system_prompt([])
    assert '30' in prompt or '两句' in prompt or '2句' in prompt

def test_prompt_no_corgi_reference(agent):
    prompt = agent._build_system_prompt([])
    assert '柯基' not in prompt

def test_prompt_with_memories(agent):
    memories = ['主人在做桌面宠物项目', '主人经常加班']
    prompt = agent._build_system_prompt(memories)
    assert '桌面宠物' in prompt
    assert '加班' in prompt

def test_prompt_with_emotion_context(agent):
    agent.owner_emotion_context = '主人皱着眉头看屏幕'
    prompt = agent._build_system_prompt([])
    assert '皱着眉头' in prompt

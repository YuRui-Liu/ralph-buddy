"""集成测试：验证完整对话管线（不需要真实 LLM）"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.dog_agent import DogBuddyAgent


@pytest.fixture
def agent_with_mocks():
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
    a.llm_ready = True

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"think": "主人回来了，好开心", '
        '"reply": "主人回来啦！今天累不累？", '
        '"action": "happy_run", '
        '"mood_shift": "excited"}'
    )
    a.llm_client = AsyncMock()
    a.llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

    a.memory = AsyncMock()
    a.memory.retrieve_relevant = AsyncMock(return_value=['主人经常加班'])
    a.memory.get_recent_history = MagicMock(return_value=[])
    a.memory.short_term = []
    a.memory.MAX_SHORT_TERM = 20
    a.memory.store = AsyncMock()

    a.attr_manager = MagicMock()
    a.attr_manager.build_self_awareness.return_value = '你精神很好。'
    a.attr_manager.attrs = {
        'health': 80, 'mood': 70, 'energy': 80,
        'affection': 50, 'obedience': 60, 'snark': 30,
    }
    a.attr_manager.save = MagicMock()

    return a


def test_chat_returns_structured_reply(agent_with_mocks):
    result = asyncio.get_event_loop().run_until_complete(
        agent_with_mocks.chat("我回来了")
    )
    assert result['reply'] == '主人回来啦！今天累不累？'
    assert result['action'] == 'happy_run'
    assert result['emotion'] == 'excited'


def test_chat_applies_mood_shift_to_attrs(agent_with_mocks):
    old_mood = agent_with_mocks.attr_manager.attrs['mood']
    asyncio.get_event_loop().run_until_complete(
        agent_with_mocks.chat("我回来了")
    )
    new_mood = agent_with_mocks.attr_manager.attrs['mood']
    # excited: mood +5
    assert new_mood == old_mood + 5


def test_chat_stores_reply_in_memory(agent_with_mocks):
    asyncio.get_event_loop().run_until_complete(
        agent_with_mocks.chat("我回来了")
    )
    agent_with_mocks.memory.store.assert_called_once_with(
        "我回来了", "主人回来啦！今天累不累？"
    )

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from plugins.plugin_manager import PluginManager

@pytest.fixture
def manager():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"replies": [{"text": "hi", "tip": "be cool"}]}'
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return PluginManager(mock_client)

def test_chat_returns_reply(manager):
    result = asyncio.get_event_loop().run_until_complete(
        manager.chat("test", "hello", "s1", {"model": "m", "temperature": 0.5, "system_prompt": "sp"})
    )
    assert 'reply' in result
    assert len(result['reply']) > 0

def test_session_accumulates_history(manager):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.chat("test", "msg1", "s1", {"model": "m", "temperature": 0.5, "system_prompt": "sp"}))
    loop.run_until_complete(manager.chat("test", "msg2", "s1", {"model": "m", "temperature": 0.5, "system_prompt": "sp"}))
    assert len(manager.sessions["s1"]) == 4

def test_clear_session(manager):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.chat("test", "msg1", "s1", {"model": "m", "temperature": 0.5, "system_prompt": "sp"}))
    manager.clear_session("s1")
    assert "s1" not in manager.sessions

def test_clear_nonexistent_session(manager):
    manager.clear_session("nope")

def test_structured_parse(manager):
    result = asyncio.get_event_loop().run_until_complete(
        manager.chat("test", "hello", "s2", {"model": "m", "temperature": 0.5, "system_prompt": "sp"})
    )
    assert result['structured'] is not None
    assert 'replies' in result['structured']

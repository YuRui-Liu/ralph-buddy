import pytest
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory.memory_system import MemorySystem, BASE_DIR


@pytest.fixture
def tmp_memory(tmp_path, monkeypatch):
    """使用临时目录隔离测试数据"""
    monkeypatch.setattr('memory.memory_system.BASE_DIR', str(tmp_path))
    monkeypatch.setattr('memory.memory_system.DB_PATH', str(tmp_path / 'memory.db'))
    monkeypatch.setattr('memory.memory_system.CHROMA_PATH', str(tmp_path / 'chromadb'))
    m = MemorySystem()
    asyncio.get_event_loop().run_until_complete(m.initialize())
    yield m
    asyncio.get_event_loop().run_until_complete(m.close())


def test_store_and_get_recent_history(tmp_memory):
    asyncio.get_event_loop().run_until_complete(
        tmp_memory.store("你好", "汪！主人好！")
    )
    history = tmp_memory.get_recent_history(n_turns=6)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "你好"}
    assert history[1] == {"role": "assistant", "content": "汪！主人好！"}


def test_max_short_term_not_exceeded_during_store(tmp_memory):
    """store 本身不裁剪 short_term，裁剪由 compress_and_extract 负责"""
    for i in range(12):
        asyncio.get_event_loop().run_until_complete(
            tmp_memory.store(f"msg{i}", f"reply{i}")
        )
    assert len(tmp_memory.short_term) == 24


def test_add_and_list_events(tmp_memory):
    asyncio.get_event_loop().run_until_complete(
        tmp_memory.add_manual_memory("主人喜欢打游戏", importance=3)
    )
    events = asyncio.get_event_loop().run_until_complete(tmp_memory.list_events())
    assert len(events) == 1
    assert events[0]["content"] == "主人喜欢打游戏"
    assert events[0]["importance"] == 3
    assert "id" in events[0]


def test_delete_event(tmp_memory):
    asyncio.get_event_loop().run_until_complete(
        tmp_memory.add_manual_memory("测试记忆")
    )
    events = asyncio.get_event_loop().run_until_complete(tmp_memory.list_events())
    event_id = events[0]["id"]

    ok = asyncio.get_event_loop().run_until_complete(
        tmp_memory.delete_event(event_id)
    )
    assert ok is True

    events_after = asyncio.get_event_loop().run_until_complete(tmp_memory.list_events())
    assert len(events_after) == 0


def test_delete_nonexistent_event(tmp_memory):
    ok = asyncio.get_event_loop().run_until_complete(
        tmp_memory.delete_event(99999)
    )
    assert ok is False


def test_get_user_profile_empty(tmp_memory):
    profile = asyncio.get_event_loop().run_until_complete(tmp_memory.get_user_profile())
    assert "total_conversations" in profile
    assert profile["total_conversations"] == 0


def test_pet_attributes_table_exists(tmp_memory):
    """pet_attributes table should be created during initialization."""
    c = tmp_memory.conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pet_attributes'")
    assert c.fetchone() is not None


def test_clear_all(tmp_memory):
    asyncio.get_event_loop().run_until_complete(tmp_memory.store("hi", "汪"))
    asyncio.get_event_loop().run_until_complete(tmp_memory.add_manual_memory("记住这个"))
    asyncio.get_event_loop().run_until_complete(tmp_memory.clear_all())

    assert tmp_memory.short_term == []
    events = asyncio.get_event_loop().run_until_complete(tmp_memory.list_events())
    assert events == []

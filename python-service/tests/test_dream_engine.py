#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for DreamEngine.

Uses in-memory SQLite and mocked memory/LLM to keep tests fast and isolated.
"""

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.pet_attributes import PetAttributeManager
from agent.dream_engine import DreamEngine, DREAM_COOLDOWN_HOURS


# ── Helpers ─────────────────────────────────────────────────────────────── #

def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with user_profile and events tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT,
            importance INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn


# ── Valid mock LLM response ──────────────────────────────────────────────── #

VALID_DREAM_RESPONSE = json.dumps({
    "dream_text": "来福梦到和主人一起散步",
    "profile_updates": [{"key": "favorite_activity", "value": "散步"}],
    "attribute_deltas": {"mood": 3, "affection": 5, "obedience": 2, "snark": -1},
    "reasoning": "主人经常带来福散步",
}, ensure_ascii=False)


# ── Fixtures ─────────────────────────────────────────────────────────────── #

@pytest.fixture
def db(tmp_path):
    """Temporary SQLite DB file with pet_attributes table."""
    db_path = str(tmp_path / "test_attrs.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pet_attributes (
            key        TEXT PRIMARY KEY,
            value      REAL NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def attr_mgr(db):
    """PetAttributeManager loaded from the temp db fixture."""
    m = PetAttributeManager(db_path=db)
    m.load()
    return m


@pytest.fixture
def mock_memory():
    """MagicMock simulating MemorySystem with an in-memory SQLite conn."""
    mem = MagicMock()
    mem.short_term = [
        {"role": "user",      "content": "我们去散步吧"},
        {"role": "assistant", "content": "汪！好呀好呀！"},
    ]
    mem._format_profile.return_value = "关于主人你记得：\n- 爱好: 散步"
    mem.conn = _make_conn()
    return mem


@pytest.fixture
def mock_llm_caller():
    """Async function that returns a valid JSON dream response."""
    async def _caller(prompt: str) -> str:
        return VALID_DREAM_RESPONSE
    return _caller


@pytest.fixture
def engine(mock_memory, attr_mgr, mock_llm_caller):
    """DreamEngine wired with all mocked dependencies."""
    return DreamEngine(mock_memory, attr_mgr, mock_llm_caller)


# ── Tests ────────────────────────────────────────────────────────────────── #

def test_can_dream_no_previous(engine):
    """can_dream returns True when the pet has never dreamed."""
    assert engine.attr_manager.get_last_dream_time() is None
    assert engine.can_dream() is True


def test_can_dream_too_recent(engine):
    """can_dream returns False when last dream was less than cooldown hours ago."""
    recent = datetime.now() - timedelta(hours=DREAM_COOLDOWN_HOURS - 1)
    engine.attr_manager.set_last_dream_time(recent)
    assert engine.can_dream() is False


def test_can_dream_after_cooldown(engine):
    """can_dream returns True once cooldown has passed (5 hours ago)."""
    old = datetime.now() - timedelta(hours=DREAM_COOLDOWN_HOURS + 1)
    engine.attr_manager.set_last_dream_time(old)
    assert engine.can_dream() is True


def test_dream_returns_result(engine):
    """dream() returns a dict containing dream_text."""
    result = asyncio.get_event_loop().run_until_complete(engine.dream())
    assert result is not None
    assert isinstance(result, dict)
    assert result["dream_text"] == "来福梦到和主人一起散步"


def test_dream_updates_attributes(attr_mgr, mock_memory, mock_llm_caller):
    """Attribute deltas from LLM response are applied correctly."""
    eng = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    before = attr_mgr.get_all()

    asyncio.get_event_loop().run_until_complete(eng.dream())

    after = attr_mgr.get_all()
    # mood +3, affection +5, obedience +2, snark -1
    assert after["mood"]      == pytest.approx(min(100.0, before["mood"]      + 3))
    assert after["affection"] == pytest.approx(min(100.0, before["affection"] + 5))
    assert after["obedience"] == pytest.approx(min(100.0, before["obedience"] + 2))
    assert after["snark"]     == pytest.approx(max(0.0,   before["snark"]     - 1))


def test_dream_updates_profile(engine):
    """profile_updates from LLM response are upserted into user_profile table."""
    asyncio.get_event_loop().run_until_complete(engine.dream())

    conn = engine.memory.conn
    row = conn.execute(
        "SELECT value FROM user_profile WHERE key = ?", ("favorite_activity",)
    ).fetchone()
    assert row is not None
    assert row["value"] == "散步"


def test_dream_records_event(engine):
    """Dream is recorded as an event with importance=3 prefixed with 【做梦】."""
    asyncio.get_event_loop().run_until_complete(engine.dream())

    conn = engine.memory.conn
    row = conn.execute(
        "SELECT content, importance FROM events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row["importance"] == 3
    assert row["content"].startswith("【做梦】")
    assert "来福梦到和主人一起散步" in row["content"]


def test_dream_sets_last_dream_time(engine):
    """last_dream_time is set (and is recent) after a successful dream."""
    assert engine.attr_manager.get_last_dream_time() is None

    before = datetime.now()
    asyncio.get_event_loop().run_until_complete(engine.dream())
    after = datetime.now()

    t = engine.attr_manager.get_last_dream_time()
    assert t is not None
    assert before <= t <= after


def test_dream_with_bad_llm_response(mock_memory, attr_mgr):
    """dream() returns None gracefully when LLM returns invalid JSON."""
    async def _bad_llm(prompt: str) -> str:
        return "这不是 JSON 格式的回复"

    eng = DreamEngine(mock_memory, attr_mgr, _bad_llm)
    result = asyncio.get_event_loop().run_until_complete(eng.dream())
    assert result is None

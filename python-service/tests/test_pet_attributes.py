#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for PetAttributeManager.

All tests are synchronous; PetAttributeManager has no async interface.
Uses tmp_path + monkeypatch to isolate the SQLite database.
"""

import os
import sys
import pytest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import agent.pet_attributes as pa_module
from agent.pet_attributes import PetAttributeManager, DEFAULTS, TICK_DELTAS


# ── Fixture ──────────────────────────────────────────────────────────────── #

@pytest.fixture
def mgr(tmp_path):
    """Return a PetAttributeManager backed by a fresh temporary database."""
    db = str(tmp_path / 'test_attrs.db')
    m = PetAttributeManager(db_path=db)
    m.load()
    return m


# ── Test 1: load defaults ────────────────────────────────────────────────── #

def test_load_defaults(mgr):
    """Freshly loaded manager should carry the DEFAULTS values."""
    attrs = mgr.get_all()
    for key, expected in DEFAULTS.items():
        assert attrs[key] == pytest.approx(expected), (
            f"{key}: expected {expected}, got {attrs[key]}"
        )


# ── Test 2: save / reload ────────────────────────────────────────────────── #

def test_save_and_reload(tmp_path):
    """Attributes mutated and saved must survive a fresh manager instance."""
    db = str(tmp_path / 'persist.db')

    m1 = PetAttributeManager(db_path=db)
    m1.load()
    m1.attrs['mood'] = 55.0
    m1.save()

    m2 = PetAttributeManager(db_path=db)
    m2.load()
    assert m2.get_all()['mood'] == pytest.approx(55.0)


# ── Test 3: tick deltas ──────────────────────────────────────────────────── #

def test_tick_deltas(mgr):
    """One tick should apply TICK_DELTAS to each attribute."""
    before = mgr.get_all()
    mgr.tick()
    after = mgr.get_all()

    for key, delta in TICK_DELTAS.items():
        expected = max(0.0, min(100.0, before[key] + delta))
        assert after[key] == pytest.approx(expected), (
            f"{key}: expected {expected}, got {after[key]}"
        )


# ── Test 4: tick clamping ────────────────────────────────────────────────── #

def test_tick_clamping(tmp_path):
    """Tick must not push any attribute below 0 or above 100."""
    db = str(tmp_path / 'clamp.db')
    m = PetAttributeManager(db_path=db)
    m.load()

    # Force attributes to boundaries
    for k in m.attrs:
        m.attrs[k] = 0.0
    m.tick()
    for k, v in m.get_all().items():
        assert v >= 0.0, f"{k} went below 0 after tick"
        assert v <= 100.0, f"{k} exceeded 100 after tick"


# ── Test 5: apply_offline ─────────────────────────────────────────────────── #

def test_apply_offline(mgr):
    """apply_offline(2) should apply 2× OFFLINE_DELTAS to each attribute."""
    from agent.pet_attributes import OFFLINE_DELTAS
    before = mgr.get_all()
    mgr.apply_offline(2)
    after = mgr.get_all()

    for key, delta_per_hour in OFFLINE_DELTAS.items():
        expected = max(0.0, min(100.0, before[key] + delta_per_hour * 2))
        assert after[key] == pytest.approx(expected), (
            f"{key}: expected {expected}, got {after[key]}"
        )


# ── Test 6: offline clamping ─────────────────────────────────────────────── #

def test_apply_offline_clamping(tmp_path):
    """apply_offline must not push values outside [0, 100]."""
    db = str(tmp_path / 'offline_clamp.db')
    m = PetAttributeManager(db_path=db)
    m.load()

    # Drain energy to 0 so energy gain is capped at 100
    m.attrs['energy'] = 0.0
    m.apply_offline(1000)
    for k, v in m.get_all().items():
        assert 0.0 <= v <= 100.0, f"{k}={v} out of [0,100] after offline"


# ── Test 7: apply_interaction chat ───────────────────────────────────────── #

def test_apply_interaction_chat(mgr):
    """apply_interaction('chat') should apply the correct deltas."""
    from agent.pet_attributes import INTERACTION_DELTAS
    before = mgr.get_all()
    mgr.apply_interaction('chat')
    after = mgr.get_all()

    for key, delta in INTERACTION_DELTAS['chat'].items():
        expected = max(0.0, min(100.0, before[key] + delta))
        assert after[key] == pytest.approx(expected), (
            f"chat / {key}: expected {expected}, got {after[key]}"
        )


# ── Test 8: unknown interaction type ─────────────────────────────────────── #

def test_apply_interaction_unknown(mgr):
    """apply_interaction with an unknown type should be a no-op."""
    before = mgr.get_all()
    mgr.apply_interaction('unknown_action')
    assert mgr.get_all() == before


# ── Test 9: apply_dream_delta ─────────────────────────────────────────────── #

def test_apply_dream_delta(mgr):
    """apply_dream_delta should add clamped deltas to the relevant attributes."""
    before = mgr.get_all()
    deltas = {'mood': 5.0, 'health': -3.0}
    mgr.apply_dream_delta(deltas)
    after = mgr.get_all()

    assert after['mood']   == pytest.approx(max(0.0, min(100.0, before['mood']   + 5.0)))
    assert after['health'] == pytest.approx(max(0.0, min(100.0, before['health'] + (-3.0))))
    # Unaffected attributes remain unchanged
    assert after['energy'] == pytest.approx(before['energy'])


# ── Test 10: dream delta clamping ────────────────────────────────────────── #

def test_apply_dream_delta_clamping(mgr):
    """Individual dream deltas exceeding ±10 should be clamped to ±10."""
    # A delta of +999 must be treated as +10
    before_mood = mgr.get_all()['mood']
    mgr.apply_dream_delta({'mood': 999.0})
    after_mood = mgr.get_all()['mood']

    expected = max(0.0, min(100.0, before_mood + 10.0))
    assert after_mood == pytest.approx(expected)

    # A delta of -999 must be treated as -10
    before_health = mgr.get_all()['health']
    mgr.apply_dream_delta({'health': -999.0})
    after_health = mgr.get_all()['health']

    expected_h = max(0.0, min(100.0, before_health - 10.0))
    assert after_health == pytest.approx(expected_h)


# ── Test 11: get_prompt_hints ─────────────────────────────────────────────── #

def test_get_prompt_hints(mgr):
    """get_prompt_hints should return a string with all six Chinese labels."""
    hints = mgr.get_prompt_hints()
    assert isinstance(hints, str)
    for label in ('健康值', '心情', '精力', '亲密度', '顺从度', '毒舌值'):
        assert label in hints, f"'{label}' not found in prompt hints: {hints!r}"
    # Each attribute section should include '/100'
    assert hints.count('/100') == 6


# ── Test 12: last_dream_time ──────────────────────────────────────────────── #

def test_last_dream_time(tmp_path):
    """set_last_dream_time should persist and be retrievable after reload."""
    db = str(tmp_path / 'dream_time.db')
    m1 = PetAttributeManager(db_path=db)
    m1.load()

    # Initially None
    assert m1.get_last_dream_time() is None

    dt = datetime(2026, 4, 14, 3, 0, 0)
    m1.set_last_dream_time(dt)
    assert m1.get_last_dream_time() == dt

    # Persist and reload
    m1.save()
    m2 = PetAttributeManager(db_path=db)
    m2.load()
    assert m2.get_last_dream_time() == dt

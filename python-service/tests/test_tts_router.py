# python-service/tests/test_tts_router.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from tts.router import TTSRouter


@pytest.fixture
def mock_clips():
    clips = MagicMock()
    clips.has.return_value = False
    clips.get.return_value = None
    return clips


@pytest.fixture
def mock_inference():
    engine = MagicMock()
    engine._ready = True
    engine.synthesize = AsyncMock(return_value=b"INFERENCE_AUDIO")
    return engine


@pytest.fixture
def mock_fallback():
    engine = MagicMock()
    engine.synthesize = AsyncMock(return_value=b"FALLBACK_AUDIO")
    return engine


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get.return_value = None
    return cache


@pytest.fixture
def router(mock_clips, mock_inference, mock_fallback, mock_cache):
    return TTSRouter(
        clips=mock_clips,
        inference=mock_inference,
        fallback=mock_fallback,
        cache=mock_cache,
        voice_id="test-voice",
    )


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_clip_hint_goes_to_clips_player(router, mock_clips):
    mock_clips.has.return_value = True
    mock_clips.get.return_value = b"CLIP_AUDIO"
    audio = run(router.synthesize("", hint="barks.short"))
    assert audio == b"CLIP_AUDIO"
    mock_clips.get.assert_called_once_with("barks.short")


def test_cache_hit_returns_cached(router, mock_cache):
    mock_cache.get.return_value = b"CACHED_AUDIO"
    audio = run(router.synthesize("hello", hint="llm"))
    assert audio == b"CACHED_AUDIO"


def test_inference_result_is_cached(router, mock_inference, mock_cache):
    audio = run(router.synthesize("hello", hint="llm"))
    assert audio == b"INFERENCE_AUDIO"
    mock_cache.put.assert_called_once_with("hello", "test-voice", b"INFERENCE_AUDIO")


def test_fallback_when_inference_not_ready(router, mock_inference, mock_fallback):
    mock_inference._ready = False
    audio = run(router.synthesize("hello", hint="llm"))
    assert audio == b"FALLBACK_AUDIO"


def test_fallback_when_inference_raises(router, mock_inference, mock_fallback):
    mock_inference.synthesize = AsyncMock(side_effect=RuntimeError("GPU OOM"))
    audio = run(router.synthesize("hello", hint="llm"))
    assert audio == b"FALLBACK_AUDIO"


def test_llm_hint_does_not_use_clips(router, mock_clips, mock_inference):
    audio = run(router.synthesize("hello", hint="llm"))
    mock_clips.has.assert_not_called()
    assert audio == b"INFERENCE_AUDIO"

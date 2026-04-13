# python-service/tests/test_tts_cache.py
import pytest
from tts.cache import TTSCache


@pytest.fixture
def cache(tmp_path):
    return TTSCache(str(tmp_path / "tts_cache"), limit_mb=1)


def test_get_miss(cache):
    assert cache.get("hello", "v1") is None


def test_put_then_get(cache):
    audio = b"RIFF" + b"\x00" * 100
    cache.put("hello", "v1", audio)
    assert cache.get("hello", "v1") == audio


def test_key_is_voice_scoped(cache):
    cache.put("hello", "v1", b"voice1")
    assert cache.get("hello", "v2") is None


def test_evicts_lru_when_over_limit(tmp_path):
    cache = TTSCache(str(tmp_path / "c"), limit_mb=1)
    big = b"\x00" * (600 * 1024)   # 600KB each, 2 × 600KB > 1MB limit
    cache.put("text1", "v1", big)
    cache.put("text2", "v1", big)  # should evict text1
    assert cache.get("text1", "v1") is None
    assert cache.get("text2", "v1") == big


def test_index_persists_across_instances(tmp_path):
    d = str(tmp_path / "c")
    cache1 = TTSCache(d, limit_mb=10)
    audio = b"RIFF" + b"\x00" * 50
    cache1.put("persist_test", "v1", audio)
    cache2 = TTSCache(d, limit_mb=10)   # new instance, same dir
    assert cache2.get("persist_test", "v1") == audio

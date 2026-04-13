# python-service/tests/test_clips_player.py
import json
import pytest
from tts.clips_player import ClipsPlayer


@pytest.fixture
def voice_dir(tmp_path):
    """构造一个最小语音包目录。"""
    clips = tmp_path / "clips"
    (clips / "barks").mkdir(parents=True)
    (clips / "emotions").mkdir(parents=True)
    (clips / "greetings").mkdir(parents=True)

    (clips / "barks" / "bark_short.wav").write_bytes(b"RIFF_short")
    (clips / "barks" / "bark_long.wav").write_bytes(b"RIFF_long")
    (clips / "emotions" / "happy_01.wav").write_bytes(b"RIFF_happy")
    (clips / "greetings" / "morning.wav").write_bytes(b"RIFF_morning")
    (clips / "greetings" / "return.wav").write_bytes(b"RIFF_return")

    config = {
        "id": "test-voice",
        "clips": {
            "barks": {
                "short": "clips/barks/bark_short.wav",
                "long":  "clips/barks/bark_long.wav",
            },
            "emotions": {
                "happy": ["clips/emotions/happy_01.wav"],
            },
            "greetings": [
                "clips/greetings/morning.wav",
                "clips/greetings/return.wav",
            ],
        },
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return str(tmp_path)


def test_get_bark_short(voice_dir):
    player = ClipsPlayer(voice_dir)
    assert player.get("barks.short") == b"RIFF_short"


def test_get_emotion_happy(voice_dir):
    player = ClipsPlayer(voice_dir)
    assert player.get("emotions.happy") == b"RIFF_happy"


def test_get_random_from_list(voice_dir):
    player = ClipsPlayer(voice_dir)
    audio = player.get("greetings")
    assert audio in (b"RIFF_morning", b"RIFF_return")


def test_missing_hint_returns_none(voice_dir):
    player = ClipsPlayer(voice_dir)
    assert player.get("nonexistent.key") is None


def test_has_existing(voice_dir):
    player = ClipsPlayer(voice_dir)
    assert player.has("barks.short") is True


def test_has_missing(voice_dir):
    player = ClipsPlayer(voice_dir)
    assert player.has("barks.roar") is False

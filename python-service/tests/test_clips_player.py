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


def test_missing_file_on_disk_returns_none(voice_dir, tmp_path):
    """File registered in config but deleted from disk → None."""
    import os
    player = ClipsPlayer(voice_dir)
    # delete the file after player is constructed
    os.remove(os.path.join(voice_dir, "clips", "barks", "bark_short.wav"))
    assert player.get("barks.short") is None


def test_bare_category_on_dict_node_returns_none(voice_dir):
    """get('barks') where barks is a dict (not a list/string) → None."""
    player = ClipsPlayer(voice_dir)
    assert player.get("barks") is None


def test_empty_list_returns_none(tmp_path):
    """Empty list entry in config → None."""
    (tmp_path / "clips" / "sounds").mkdir(parents=True)
    config = {"id": "t", "clips": {"sounds": []}}
    (tmp_path / "config.json").write_text(__import__("json").dumps(config), encoding="utf-8")
    player = ClipsPlayer(str(tmp_path))
    assert player.get("sounds") is None


def test_dot_notation_on_list_category_returns_none(voice_dir):
    """get('greetings.morning') where greetings is a list (no sub-key lookup) → None."""
    player = ClipsPlayer(voice_dir)
    assert player.get("greetings.morning") is None

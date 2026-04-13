# python-service/tests/test_embedded_engine.py
import asyncio
import io
import json
import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")

from unittest.mock import MagicMock


@pytest.fixture
def voice_dir(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "ref.wav").write_bytes(b"RIFF_ref")
    config = {
        "id": "test-clone",
        "models": {"gpt": "models/gpt.ckpt", "sovits": "models/sovits.pth"},
        "reference": {"audio": "reference/ref.wav", "text": "汪", "lang": "zh"},
        "inference": {"top_k": 20, "top_p": 0.85, "temperature": 0.6, "speed": 1.0},
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return str(tmp_path)


def make_mock_pipeline():
    """返回一个 mock TTS pipeline，yield 1 秒 24kHz 静音。"""
    pipeline = MagicMock()
    sr = 24000
    audio = np.zeros(sr, dtype=np.float32)
    pipeline.run.return_value = iter([(sr, audio)])
    return pipeline


def test_synthesize_returns_wav_bytes(voice_dir):
    from tts.embedded_engine import EmbeddedTTSEngine

    engine = EmbeddedTTSEngine(voice_dir, _pipeline_factory=make_mock_pipeline)
    engine._ready = True
    engine._pipeline = make_mock_pipeline()

    audio = asyncio.get_event_loop().run_until_complete(engine.synthesize("你好呀"))
    assert audio[:4] == b"RIFF"    # WAV 文件头
    assert len(audio) > 44         # 超出 WAV header 大小


def test_synthesize_raises_when_not_ready(voice_dir):
    from tts.embedded_engine import EmbeddedTTSEngine

    engine = EmbeddedTTSEngine(voice_dir)
    with pytest.raises(RuntimeError, match="尚未就绪"):
        asyncio.get_event_loop().run_until_complete(engine.synthesize("test"))


def test_warmup_calls_factory_and_sets_ready(voice_dir):
    from tts.embedded_engine import EmbeddedTTSEngine

    called = []

    def factory():
        called.append(True)
        return make_mock_pipeline()

    engine = EmbeddedTTSEngine(voice_dir, _pipeline_factory=factory)
    asyncio.get_event_loop().run_until_complete(engine.warmup())
    assert engine._ready is True
    assert len(called) == 1


def test_run_inference_concatenates_chunks(voice_dir):
    from tts.embedded_engine import EmbeddedTTSEngine

    # pipeline returns two chunks
    pipeline = MagicMock()
    sr = 16000
    chunk1 = np.zeros(sr // 2, dtype=np.float32)
    chunk2 = np.ones(sr // 2, dtype=np.float32) * 0.1
    pipeline.run.return_value = iter([(sr, chunk1), (sr, chunk2)])

    engine = EmbeddedTTSEngine(voice_dir, _pipeline_factory=lambda: pipeline)
    engine._ready = True
    engine._pipeline = pipeline

    wav_bytes = engine._run_inference("test")
    buf = io.BytesIO(wav_bytes)
    data, out_sr = sf.read(buf)
    assert out_sr == sr
    assert len(data) == sr   # 两段合并为 1 秒

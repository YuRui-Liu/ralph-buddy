import pytest
import asyncio
import numpy as np
from unittest.mock import patch, MagicMock
from emotion.detector import EmotionDetector


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def detector():
    return EmotionDetector(deep_llm_call=None)


# ── Layer 1: 本地检测 ─────────────────────────────

def test_detect_returns_result_with_face(detector):
    """正常图片应返回 has_face=True 和情绪分类"""
    from io import BytesIO
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    mock_result = [{
        "dominant_emotion": "happy",
        "emotion": {
            "happy": 85.0, "sad": 2.0, "angry": 1.0,
            "surprise": 5.0, "neutral": 5.0, "fear": 1.0, "disgust": 1.0
        }
    }]
    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.return_value = mock_result
        result = run(detector.detect(image_bytes))

    assert result["has_face"] is True
    assert result["local"]["emotion"] == "happy"
    assert result["local"]["confidence"] == pytest.approx(0.85, abs=0.01)
    assert "happy" in result["local"]["all_scores"]


def test_detect_no_face(detector):
    """无人脸时返回 has_face=False"""
    from io import BytesIO
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.side_effect = ValueError("Face could not be detected")
        result = run(detector.detect(image_bytes))

    assert result["has_face"] is False
    assert result["local"] is None


def test_detect_tracks_change(detector):
    """连续检测时 changed 字段应反映情绪变化"""
    from io import BytesIO
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    mock_happy = [{"dominant_emotion": "happy",
                   "emotion": {"happy": 90.0, "sad": 2.0, "angry": 1.0,
                               "surprise": 2.0, "neutral": 3.0, "fear": 1.0, "disgust": 1.0}}]
    mock_sad = [{"dominant_emotion": "sad",
                 "emotion": {"happy": 5.0, "sad": 80.0, "angry": 3.0,
                             "surprise": 2.0, "neutral": 8.0, "fear": 1.0, "disgust": 1.0}}]

    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.return_value = mock_happy
        r1 = run(detector.detect(image_bytes))

        mock_df.analyze.return_value = mock_happy
        r2 = run(detector.detect(image_bytes))

        mock_df.analyze.return_value = mock_sad
        r3 = run(detector.detect(image_bytes))

    assert r1["changed"] is True   # 首次检测，与 None 比较 → changed
    assert r2["changed"] is False  # happy → happy → 无变化
    assert r3["changed"] is True   # happy → sad → 有变化


# ── 深度分析触发判断 ─────────────────────────────

def test_should_trigger_deep_on_change():
    """情绪变化时应触发深度分析"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is True


def test_should_not_trigger_deep_without_change():
    """情绪无变化且无连续负面时不触发"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": True, "changed": False, "local": {"emotion": "happy"}}
    assert detector.should_trigger_deep(result) is False


def test_should_trigger_deep_on_consecutive_negative():
    """连续负面情绪 >= 2 次触发深度分析"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    detector._consecutive_neg = 2
    result = {"has_face": True, "changed": False, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is True


def test_should_not_trigger_deep_during_cooldown():
    """冷却期内不触发"""
    import time
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    detector._last_deep_time = time.time()
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is False


def test_should_not_trigger_deep_without_llm():
    """没有 deep_llm_call 时不触发"""
    detector = EmotionDetector(deep_llm_call=None)
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is False


def test_should_not_trigger_deep_without_face():
    """无人脸时不触发"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": False, "changed": False, "local": None}
    assert detector.should_trigger_deep(result) is False

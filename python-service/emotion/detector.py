#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmotionDetector — 混合情绪检测器
Layer 1: DeepFace 本地快速检测
Layer 2: 视觉 LLM 深度分析（由 should_trigger_deep 判断是否升级）
"""

import io
import time
import numpy as np
from typing import Optional, Callable, Awaitable

# 延迟导入 DeepFace（首次调用时加载模型）
DeepFace = None

NEGATIVE_EMOTIONS = {"sad", "angry", "fear", "disgust"}
DEEP_COOLDOWN_SEC = 180  # 深度分析冷却：3 分钟


def _ensure_deepface():
    global DeepFace
    if DeepFace is None:
        from deepface import DeepFace as _DF
        DeepFace = _DF


class EmotionDetector:

    def __init__(self, deep_llm_call: Optional[Callable] = None):
        """
        Args:
            deep_llm_call: async (image_bytes, local_emotion) -> DeepResult dict
                           如果为 None 则禁用深度分析
        """
        self._deep_llm_call = deep_llm_call
        self._last_emotion: Optional[str] = None
        self._consecutive_neg: int = 0
        self._last_deep_time: float = 0

    # ── Layer 1: 本地快速检测 ─────────────────────────

    async def detect(self, image_bytes: bytes) -> dict:
        _ensure_deepface()

        # DeepFace 需要 numpy 数组，不接受原始 JPEG bytes
        from PIL import Image
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(img)
        except Exception:
            return {"has_face": False, "local": None, "deep": None, "changed": False}

        try:
            results = DeepFace.analyze(
                img_path=img_array,
                actions=["emotion"],
                enforce_detection=True,
                detector_backend="opencv",
                silent=True,
            )
        except (ValueError, AttributeError):
            return {"has_face": False, "local": None, "deep": None, "changed": False}

        face = results[0] if isinstance(results, list) else results
        emotion = face["dominant_emotion"]
        scores = face["emotion"]

        confidence = scores[emotion] / 100.0
        all_scores = {k: round(v / 100.0, 4) for k, v in scores.items()}

        changed = (emotion != self._last_emotion)

        if emotion in NEGATIVE_EMOTIONS:
            self._consecutive_neg += 1
        else:
            self._consecutive_neg = 0

        self._last_emotion = emotion

        return {
            "has_face": True,
            "local": {
                "emotion": emotion,
                "confidence": round(confidence, 4),
                "all_scores": all_scores,
            },
            "deep": None,
            "changed": changed,
        }

    def should_trigger_deep(self, detect_result: dict) -> bool:
        if not detect_result["has_face"]:
            return False
        if not self._deep_llm_call:
            return False

        now = time.time()
        if now - self._last_deep_time < DEEP_COOLDOWN_SEC:
            return False

        if detect_result["changed"]:
            return True

        if self._consecutive_neg >= 2:
            return True

        return False

    async def analyze_deep(self, image_bytes: bytes, local_result: dict) -> Optional[dict]:
        if not self._deep_llm_call:
            return None
        try:
            self._last_deep_time = time.time()
            return await self._deep_llm_call(image_bytes, local_result["local"]["emotion"])
        except Exception as e:
            print(f"❌ 情绪深度分析失败: {e}")
            return None

"""
TTS 路由器：按 hint 分发请求。
优先级：预合成 clip → 磁盘缓存 → 内嵌推理 → Edge TTS 兜底。
"""


class TTSRouter:
    """
    调用方只与 TTSRouter 交互，内部三层完全透明。

    Args:
        clips:      ClipsPlayer 实例
        inference:  EmbeddedTTSEngine 实例
        fallback:   EdgeTTSEngine 实例
        cache:      TTSCache 实例
        voice_id:   用于缓存 key 的语音包 ID
    """

    def __init__(self, clips, inference, fallback, cache, voice_id: str = "default"):
        self._clips = clips
        self._inference = inference
        self._fallback = fallback
        self._cache = cache
        self._voice_id = voice_id

    async def synthesize(self, text: str, hint: str = "llm") -> bytes:
        """
        Args:
            text: 要合成的文本（hint 为 clip 时可为空字符串）
            hint: "llm" | "barks.short" | "emotions.happy" | ...

        Returns:
            WAV 或 MP3 音频字节
        """
        # 1. 预合成 clip（hint 不是 "llm" 时才查）
        if hint != "llm" and self._clips.has(hint):
            return self._clips.get(hint)

        # 2. 磁盘缓存
        cached = self._cache.get(text, self._voice_id)
        if cached is not None:
            return cached

        # 3. 内嵌推理
        if getattr(self._inference, "_ready", False):
            try:
                audio = await self._inference.synthesize(text)
                self._cache.put(text, self._voice_id, audio)
                return audio
            except Exception as e:
                print(f"⚠️ 内嵌推理失败，降级到 Edge TTS: {e}")

        # 4. 兜底
        return await self._fallback.synthesize(text)

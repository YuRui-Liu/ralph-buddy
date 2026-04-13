# TTS Offline Voice Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用内嵌 GPT-SoVITS 推理 + 预合成 clips 替换子进程调用，彻底消除 60s 启动开销。

**Architecture:** TTSRouter 按 hint 分发：预合成 clip → 磁盘缓存 → EmbeddedTTSEngine（直接 import TTS 类）→ EdgeTTS 兜底。应用启动时后台预热模型，用户无感知。

**Tech Stack:** Python 3.10, asyncio, soundfile, numpy, `GPT_SoVITS.TTS_infer_pack.TTS`（来自 tools/GPT-SoVITS），pytest

---

## File Map

| 文件 | 操作 | 职责 |
|---|---|---|
| `python-service/tts/cache.py` | CREATE | LRU 磁盘缓存，key=sha256(text:voice_id)[:8] |
| `python-service/tts/clips_player.py` | CREATE | 按 hint 读取预合成 WAV |
| `python-service/tts/embedded_engine.py` | CREATE | 直接调用 TTS 类推理，无子进程 |
| `python-service/tts/router.py` | CREATE | hint 分发：clips/cache/inference/fallback |
| `python-service/tts/voice_manager.py` | MODIFY | 新增 `register_gptsovits_v2()` 和 `get_router()` |
| `python-service/main.py` | MODIFY | 使用 TTSRouter，后台 warmup，新增 `/api/tts/status` |
| `python-service/tools/__init__.py` | CREATE | 使 tools 成为包（空文件） |
| `python-service/tools/prebake.py` | CREATE | 离线批量预合成 CLI |
| `python-service/tests/test_tts_cache.py` | CREATE | TTSCache 单元测试 |
| `python-service/tests/test_clips_player.py` | CREATE | ClipsPlayer 单元测试 |
| `python-service/tests/test_embedded_engine.py` | CREATE | EmbeddedTTSEngine 单元测试（mock pipeline） |
| `python-service/tests/test_tts_router.py` | CREATE | TTSRouter 路由逻辑单元测试 |
| `python-service/tests/test_voice_manager_v2.py` | CREATE | register_gptsovits_v2 单元测试 |

---

## Task 1: TTSCache

**Files:**
- Create: `python-service/tts/cache.py`
- Create: `python-service/tests/test_tts_cache.py`

- [ ] **Step 1: 写测试文件**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd python-service && python -m pytest tests/test_tts_cache.py -v
```
Expected: `ImportError: No module named 'tts.cache'`

- [ ] **Step 3: 实现 TTSCache**

```python
# python-service/tts/cache.py
import hashlib
import json
import time
from pathlib import Path
from typing import Optional


class TTSCache:
    """LRU 磁盘缓存：key=sha256(text:voice_id)[:8]，超限时淘汰最旧条目。"""

    def __init__(self, cache_dir: str, limit_mb: int = 500):
        self._dir = Path(cache_dir)
        self._limit = limit_mb * 1024 * 1024
        self._index_path = self._dir / "index.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index: dict = {}
        self._load()

    def _key(self, text: str, voice_id: str) -> str:
        return hashlib.sha256(f"{text}:{voice_id}".encode()).hexdigest()[:8]

    def _load(self):
        if self._index_path.exists():
            try:
                self._index = json.loads(
                    self._index_path.read_text(encoding="utf-8")
                )
            except Exception:
                self._index = {}

    def _save(self):
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False), encoding="utf-8"
        )

    def get(self, text: str, voice_id: str) -> Optional[bytes]:
        k = self._key(text, voice_id)
        entry = self._index.get(k)
        if not entry:
            return None
        fp = self._dir / entry["file"]
        if not fp.exists():
            del self._index[k]
            self._save()
            return None
        entry["atime"] = time.time()
        self._save()
        return fp.read_bytes()

    def put(self, text: str, voice_id: str, audio: bytes) -> None:
        k = self._key(text, voice_id)
        filename = f"{k}.wav"
        (self._dir / filename).write_bytes(audio)
        self._index[k] = {
            "file": filename,
            "size": len(audio),
            "atime": time.time(),
        }
        self._save()
        self._evict()

    def _total(self) -> int:
        return sum(e["size"] for e in self._index.values())

    def _evict(self):
        while self._index and self._total() > self._limit:
            oldest = min(self._index, key=lambda k: self._index[k]["atime"])
            fp = self._dir / self._index[oldest]["file"]
            if fp.exists():
                fp.unlink()
            del self._index[oldest]
        self._save()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd python-service && python -m pytest tests/test_tts_cache.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd python-service && git add tts/cache.py tests/test_tts_cache.py
git commit -m "feat: add TTSCache with LRU disk eviction"
```

---

## Task 2: ClipsPlayer

**Files:**
- Create: `python-service/tts/clips_player.py`
- Create: `python-service/tests/test_clips_player.py`

- [ ] **Step 1: 写测试文件**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd python-service && python -m pytest tests/test_clips_player.py -v
```
Expected: `ImportError: No module named 'tts.clips_player'`

- [ ] **Step 3: 实现 ClipsPlayer**

```python
# python-service/tts/clips_player.py
import json
import random
from pathlib import Path
from typing import Optional


class ClipsPlayer:
    """按 hint 从语音包 clips/ 目录读取预合成 WAV 片段。"""

    def __init__(self, voice_dir: str):
        self._root = Path(voice_dir)
        cfg = json.loads((self._root / "config.json").read_text(encoding="utf-8"))
        self._clips: dict = cfg.get("clips", {})

    def get(self, hint: str) -> Optional[bytes]:
        """
        hint 格式: "category" 或 "category.key"
        entry 为列表时随机选一条。返回 None 表示未找到。
        """
        parts = hint.split(".", 1)
        category = parts[0]
        sub_key = parts[1] if len(parts) > 1 else None

        node = self._clips.get(category)
        if node is None:
            return None

        if sub_key is not None:
            if not isinstance(node, dict):
                return None
            node = node.get(sub_key)
            if node is None:
                return None

        if isinstance(node, list):
            if not node:
                return None
            path_str = random.choice(node)
        else:
            path_str = node

        fp = self._root / path_str
        if not fp.exists():
            return None
        return fp.read_bytes()

    def has(self, hint: str) -> bool:
        return self.get(hint) is not None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd python-service && python -m pytest tests/test_clips_player.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd python-service && git add tts/clips_player.py tests/test_clips_player.py
git commit -m "feat: add ClipsPlayer for pre-baked voice pack WAV clips"
```

---

## Task 3: EmbeddedTTSEngine

**Files:**
- Create: `python-service/tts/embedded_engine.py`
- Create: `python-service/tests/test_embedded_engine.py`

- [ ] **Step 1: 写测试文件**

```python
# python-service/tests/test_embedded_engine.py
import asyncio
import io
import json
import pytest
import numpy as np
import soundfile as sf
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd python-service && python -m pytest tests/test_embedded_engine.py -v
```
Expected: `ImportError: No module named 'tts.embedded_engine'`

- [ ] **Step 3: 实现 EmbeddedTTSEngine**

```python
# python-service/tts/embedded_engine.py
"""
内嵌 GPT-SoVITS 推理引擎。
直接调用 TTS 类，无子进程、无 HTTP。
通过 warmup() 在后台线程预热，不阻塞 asyncio 事件循环。
"""
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf


class EmbeddedTTSEngine:
    """GPT-SoVITS 内嵌推理引擎（无子进程版本）。"""

    def __init__(self, voice_dir: str, _pipeline_factory: Optional[Callable] = None):
        """
        Args:
            voice_dir: 语音包目录（含 config.json）
            _pipeline_factory: 测试注入；callable() -> pipeline 对象。
                               生产环境传 None，_load_models 自动导入 TTS。
        """
        self._root = Path(voice_dir)
        cfg = json.loads((self._root / "config.json").read_text(encoding="utf-8"))

        self._gpt_path = str(self._root / cfg["models"]["gpt"])
        self._sovits_path = str(self._root / cfg["models"]["sovits"])

        ref = cfg["reference"]
        self._ref_wav = str(self._root / ref["audio"])
        self._prompt_text = ref["text"]
        self._prompt_lang = ref.get("lang", "zh")

        inf = cfg.get("inference", {})
        self._top_k = inf.get("top_k", 20)
        self._top_p = inf.get("top_p", 0.85)
        self._temperature = inf.get("temperature", 0.6)
        self._speed = inf.get("speed", 1.0)

        self._pipeline_factory = _pipeline_factory
        self._pipeline = None
        self._ready = False
        self._lock = asyncio.Lock()

    def _find_gsv_dir(self) -> str:
        """定位 tools/GPT-SoVITS 目录（相对于 python-service/）。"""
        here = Path(__file__).resolve().parent
        candidate = here.parent.parent / "tools" / "GPT-SoVITS"
        if not candidate.exists():
            raise FileNotFoundError(f"找不到 GPT-SoVITS 目录: {candidate}")
        return str(candidate)

    def _load_models(self):
        """在线程池中加载模型（阻塞操作）。"""
        if self._pipeline_factory is not None:
            self._pipeline = self._pipeline_factory()
        else:
            gsv_dir = self._find_gsv_dir()
            if gsv_dir not in sys.path:
                sys.path.insert(0, gsv_dir)
            from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: PLC0415

            cfg_yaml = os.path.join(
                gsv_dir, "GPT_SoVITS", "configs", "tts_infer.yaml"
            )
            tts_cfg = TTS_Config(cfg_yaml)
            pipeline = TTS(tts_cfg)
            pipeline.init_t2s_weights(self._gpt_path)
            pipeline.init_vits_weights(self._sovits_path)
            self._pipeline = pipeline

        self._ready = True

    async def warmup(self):
        """后台线程预热模型，不阻塞事件循环。完成后 _ready=True。"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_models)

    def _run_inference(self, text: str) -> bytes:
        """同步推理，运行在线程池中，返回 WAV 字节。"""
        req = {
            "text": text,
            "text_lang": "zh",
            "ref_audio_path": self._ref_wav,
            "prompt_text": self._prompt_text,
            "prompt_lang": self._prompt_lang,
            "top_k": self._top_k,
            "top_p": self._top_p,
            "temperature": self._temperature,
            "speed_factor": self._speed,
            "text_split_method": "cut5",
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": True,
            "fragment_interval": 0.3,
            "seed": -1,
            "parallel_infer": True,
            "repetition_penalty": 1.35,
            "streaming_mode": False,
            "return_fragment": False,
            "fixed_length_chunk": False,
            "media_type": "wav",
        }
        chunks = []
        sample_rate = None
        for sr, chunk in self._pipeline.run(req):
            if sample_rate is None:
                sample_rate = sr
            chunks.append(chunk)

        if not chunks:
            raise RuntimeError("GPT-SoVITS 推理返回空音频")

        audio_data = np.concatenate(chunks, axis=0)
        buf = io.BytesIO()
        sf.write(buf, audio_data, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    async def synthesize(self, text: str) -> bytes:
        """合成语音，返回 WAV 字节。未就绪时抛出 RuntimeError。"""
        if not self._ready:
            raise RuntimeError("模型尚未就绪，请等待 warmup() 完成")
        async with self._lock:   # 推理非线程安全，串行执行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._run_inference, text)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd python-service && python -m pytest tests/test_embedded_engine.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd python-service && git add tts/embedded_engine.py tests/test_embedded_engine.py
git commit -m "feat: add EmbeddedTTSEngine - direct GPT-SoVITS import, no subprocess"
```

---

## Task 4: TTSRouter

**Files:**
- Create: `python-service/tts/router.py`
- Create: `python-service/tests/test_tts_router.py`

- [ ] **Step 1: 写测试文件**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd python-service && python -m pytest tests/test_tts_router.py -v
```
Expected: `ImportError: No module named 'tts.router'`

- [ ] **Step 3: 实现 TTSRouter**

```python
# python-service/tts/router.py
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd python-service && python -m pytest tests/test_tts_router.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd python-service && git add tts/router.py tests/test_tts_router.py
git commit -m "feat: add TTSRouter with clip/cache/inference/fallback dispatch"
```

---

## Task 5: Update VoiceManager

**Files:**
- Modify: `python-service/tts/voice_manager.py`
- Create: `python-service/tests/test_voice_manager_v2.py`

- [ ] **Step 1: 写测试文件**

```python
# python-service/tests/test_voice_manager_v2.py
import json
import pytest
from tts.voice_manager import VoiceManager


@pytest.fixture
def manager(tmp_path):
    return VoiceManager(data_dir=str(tmp_path))


@pytest.fixture
def fake_voice_dir(tmp_path):
    """构造最小 gptsovits-v2 语音包目录（无真实模型）。"""
    d = tmp_path / "my-clone"
    (d / "models").mkdir(parents=True)
    (d / "reference").mkdir()
    (d / "clips").mkdir()
    (d / "reference" / "ref.wav").write_bytes(b"RIFF")
    config = {
        "id": "my-clone",
        "name": "测试克隆",
        "type": "gptsovits-v2",
        "models": {"gpt": "models/gpt.ckpt", "sovits": "models/sovits.pth"},
        "reference": {"audio": "reference/ref.wav", "text": "汪", "lang": "zh"},
        "clips": {},
        "inference": {},
    }
    (d / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return str(d)


def test_register_gptsovits_v2_returns_package(manager, fake_voice_dir):
    pkg = manager.register_gptsovits_v2(fake_voice_dir)
    assert pkg.type == "gptsovits-v2"
    assert pkg.id == "my-clone"
    assert pkg.name == "测试克隆"


def test_registered_package_appears_in_list(manager, fake_voice_dir):
    manager.register_gptsovits_v2(fake_voice_dir)
    pkgs = manager.list_packages()
    assert any(p.id == "my-clone" for p in pkgs)


def test_register_persists_to_index(manager, fake_voice_dir, tmp_path):
    manager.register_gptsovits_v2(fake_voice_dir)
    manager2 = VoiceManager(data_dir=str(tmp_path))
    assert any(p.id == "my-clone" for p in manager2.list_packages())
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd python-service && python -m pytest tests/test_voice_manager_v2.py -v
```
Expected: `AttributeError: 'VoiceManager' object has no attribute 'register_gptsovits_v2'`

- [ ] **Step 3: 在 voice_manager.py 末尾 `delete_package` 之后添加方法**

在 `python-service/tts/voice_manager.py` 中，`delete_package` 方法（约第 233 行）之后插入：

```python
    def register_gptsovits_v2(self, voice_dir: str) -> "VoicePackage":
        """
        注册已有目录的 gptsovits-v2 语音包（读取 config.json，不复制文件）。

        Args:
            voice_dir: 包含 config.json 的语音包目录绝对路径

        Returns:
            注册的 VoicePackage
        """
        cfg_path = os.path.join(voice_dir, "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        pkg_id = cfg["id"]
        pkg = VoicePackage(
            id=pkg_id,
            name=cfg.get("name", pkg_id),
            description=cfg.get("description", ""),
            type="gptsovits-v2",
            created_at=datetime.now().isoformat(),
            config_path=cfg_path,
            is_active=False,
        )
        self._packages[pkg_id] = pkg
        self._save_index()
        return pkg
```

- [ ] **Step 4: 在 voice_manager.py 最底部（`get_manager` 函数之后）添加 `get_router`**

```python
def get_router(voice_dir: str, cache_dir: Optional[str] = None) -> "object":
    """
    为 gptsovits-v2 语音包创建完整的 TTSRouter。
    内嵌引擎未预热，调用方需在后台调用 router.inference.warmup()。

    Args:
        voice_dir: 语音包目录（含 config.json）
        cache_dir: 磁盘缓存目录，默认 <python-service>/cache/tts

    Returns:
        TTSRouter 实例
    """
    import json as _json
    from .clips_player import ClipsPlayer
    from .embedded_engine import EmbeddedTTSEngine
    from .edge_engine import EdgeTTSEngine
    from .cache import TTSCache
    from .router import TTSRouter

    with open(os.path.join(voice_dir, "config.json"), "r", encoding="utf-8") as f:
        cfg = _json.load(f)

    voice_id = cfg["id"]

    if cache_dir is None:
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "cache", "tts"
        )

    return TTSRouter(
        clips=ClipsPlayer(voice_dir),
        inference=EmbeddedTTSEngine(voice_dir),
        fallback=EdgeTTSEngine("zh-CN-XiaoxiaoNeural"),
        cache=TTSCache(cache_dir),
        voice_id=voice_id,
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd python-service && python -m pytest tests/test_voice_manager_v2.py -v
```
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
cd python-service && git add tts/voice_manager.py tests/test_voice_manager_v2.py
git commit -m "feat: add register_gptsovits_v2 and get_router to VoiceManager"
```

---

## Task 6: Update main.py

**Files:**
- Modify: `python-service/main.py`

- [ ] **Step 1: 修改 import 区（第 27-28 行）**

将：
```python
from tts.gpt_sovits_engine import GptSoVITSEngine
from tts.voice_manager import VoiceManager, get_manager
```
改为：
```python
from tts.router import TTSRouter
from tts.voice_manager import VoiceManager, get_manager, get_router
```

- [ ] **Step 2: 修改全局变量（第 32-37 行）**

将：
```python
tts_engine = None          # EdgeTTSEngine | GptSoVITSEngine
...
gsv_engine: Optional[GptSoVITSEngine] = None  # 来福克隆引擎单例
```
改为：
```python
tts_engine = None          # EdgeTTSEngine | TTSRouter
tts_router: Optional[TTSRouter] = None
```

- [ ] **Step 3: 替换 lifespan 中 TTS 初始化块（第 66-83 行）**

将整个 `# TTS 引擎：优先使用来福克隆...` 块替换为：

```python
    # TTS 引擎：优先使用内嵌克隆推理，降级到 Edge TTS
    clone_dir = _laifu_clone_dir()
    if clone_dir:
        tts_router = get_router(clone_dir)
        asyncio.create_task(tts_router.inference.warmup())
        tts_engine = tts_router
        print("🎙️  TTS: 来福克隆 (内嵌推理，后台预热中...)")
    else:
        active_voice = voice_manager.get_active_package()
        voice_name = (
            active_voice.voice_name
            if active_voice and active_voice.type == "edge-tts"
            else "xiaoxiao"
        )
        tts_engine = EdgeTTSEngine(voice_name)
        print(f"🔊 TTS: Edge TTS ({voice_name})")
```

- [ ] **Step 4: 修改 lifespan 关闭块（第 98-102 行）**

删除：
```python
    if gsv_engine:
        gsv_engine.close()
```

- [ ] **Step 5: 在 `/api/status` 端点之后新增 `/api/tts/status` 端点**

```python
@app.get("/api/tts/status")
async def get_tts_status():
    """获取 TTS 内嵌推理引擎就绪状态"""
    if tts_router is None:
        return {"ready": False, "message": "使用 Edge TTS（无克隆语音包）"}
    ready = getattr(tts_router.inference, "_ready", False)
    return {
        "ready": ready,
        "message": "克隆音色就绪" if ready else "模型加载中，当前使用 Edge TTS 兜底",
    }
```

- [ ] **Step 6: 修改 `/api/tts` 端点中的合成调用**

在 `text_to_speech` 函数中，将 `# 合成语音` 后的代码块替换为：

```python
        # 合成语音
        if tts_router:
            audio_bytes = await tts_router.synthesize(text, hint="llm")
            media_type_val = "audio/wav"
            filename = "speech.wav"
        else:
            audio_bytes = await tts_engine.synthesize(text)
            media_type_val = "audio/mpeg"
            filename = "speech.mp3"

        print(f"✅ TTS 合成完成: {len(audio_bytes)} bytes")

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type_val,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
```

同时删除原来的 `is_gsv = isinstance(engine, GptSoVITSEngine)` 判断逻辑。

- [ ] **Step 7: 验证服务能正常启动**

```bash
cd python-service && python main.py
```
Expected: 启动日志出现 `TTS: 来福克隆 (内嵌推理，后台预热中...)` 或 `TTS: Edge TTS`，无 `GptSoVITSEngine` 相关报错

- [ ] **Step 8: 验证状态端点**

```bash
curl http://localhost:18765/api/tts/status
```
Expected: `{"ready":false,"message":"模型加载中，当前使用 Edge TTS 兜底"}`（预热期间）

- [ ] **Step 9: Commit**

```bash
git add python-service/main.py
git commit -m "feat: wire TTSRouter into main.py with background warmup and /api/tts/status"
```

---

## Task 7: prebake.py CLI 工具

**Files:**
- Create: `python-service/tools/__init__.py`（空文件）
- Create: `python-service/tools/prebake.py`

- [ ] **Step 1: 创建 tools 包**

```bash
touch python-service/tools/__init__.py
```

- [ ] **Step 2: 实现 prebake.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线预合成工具：使用 GPT-SoVITS 批量生成语音包 clips/ 目录。

用法:
  python tools/prebake.py --voice-dir data/voices/laifu-clone --phrases phrase_list.json
  python tools/prebake.py --voice-dir data/voices/laifu-clone --phrases phrase_list.json --group emotions
  python tools/prebake.py --voice-dir data/voices/laifu-clone --phrases phrase_list.json --skip-existing
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def _setup_gsv_path(voice_dir: Path) -> str:
    """将 tools/GPT-SoVITS 加入 sys.path，返回目录路径。"""
    # voice_dir = python-service/data/voices/laifu-clone
    # tools/GPT-SoVITS = project_root/tools/GPT-SoVITS
    gsv_dir = voice_dir.parent.parent.parent.parent / "tools" / "GPT-SoVITS"
    if not gsv_dir.exists():
        raise FileNotFoundError(f"找不到 GPT-SoVITS 目录: {gsv_dir}")
    gsv_str = str(gsv_dir)
    if gsv_str not in sys.path:
        sys.path.insert(0, gsv_str)
    return gsv_str


def _load_pipeline(voice_dir: Path, cfg: dict):
    gsv_dir = _setup_gsv_path(voice_dir)
    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: PLC0415

    cfg_yaml = os.path.join(gsv_dir, "GPT_SoVITS", "configs", "tts_infer.yaml")
    tts_cfg = TTS_Config(cfg_yaml)
    pipeline = TTS(tts_cfg)
    pipeline.init_t2s_weights(str(voice_dir / cfg["models"]["gpt"]))
    pipeline.init_vits_weights(str(voice_dir / cfg["models"]["sovits"]))
    return pipeline


def _synthesize_to_wav(pipeline, ref_wav: str, prompt_text: str,
                       prompt_lang: str, text: str, inf: dict) -> bytes:
    req = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref_wav,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "top_k": inf.get("top_k", 20),
        "top_p": inf.get("top_p", 0.85),
        "temperature": inf.get("temperature", 0.6),
        "speed_factor": inf.get("speed", 1.0),
        "text_split_method": "cut5",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "fragment_interval": 0.3,
        "seed": -1,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
        "streaming_mode": False,
        "return_fragment": False,
        "fixed_length_chunk": False,
        "media_type": "wav",
    }
    chunks, sr_out = [], None
    for sr, chunk in pipeline.run(req):
        if sr_out is None:
            sr_out = sr
        chunks.append(chunk)
    if not chunks:
        raise RuntimeError("推理返回空音频")
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(chunks), sr_out, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _quality_check(audio: bytes, rel_path: str) -> bool:
    """检查音频质量，返回 True 表示通过。"""
    try:
        data, sr = sf.read(io.BytesIO(audio))
    except Exception:
        print(f"  ⚠️  {rel_path}: 无法解析音频，跳过")
        return False
    duration = len(data) / sr
    if duration < 0.3:
        print(f"  ⚠️  {rel_path}: 时长 {duration:.2f}s < 0.3s，跳过")
        return False
    silence_ratio = float(np.mean(np.abs(data) < 0.01))
    if silence_ratio > 0.8:
        print(f"  ⚠️  {rel_path}: 静音占比 {silence_ratio:.0%} > 80%，标记异常")
        return False
    return True


def _flatten(phrases: dict, group_filter: str = None) -> list:
    """
    展开短语表为 [(clips相对路径, text)] 列表。

    规则：
      - top-level key = category → 文件存入 clips/{category}/
      - second-level key（dict）= 逻辑子分组（用于 hint），不构成目录
      - list entry → clips/{category}/{file}
    """
    items = []
    for category, content in phrases.items():
        if group_filter and category != group_filter:
            continue
        if isinstance(content, list):
            # greetings: [{file, text}, ...]
            for entry in content:
                items.append((f"clips/{category}/{entry['file']}", entry["text"]))
        elif isinstance(content, dict):
            # emotions: {happy: [{file,text}], sad: [...]}
            # sub_key 是 hint 的逻辑分组，不作为目录层级
            for sub_key, sub_content in content.items():
                if isinstance(sub_content, list):
                    for entry in sub_content:
                        items.append((f"clips/{category}/{entry['file']}", entry["text"]))
                elif isinstance(sub_content, dict) and "file" in sub_content:
                    items.append((f"clips/{category}/{sub_content['file']}", sub_content["text"]))
    return items


def main():
    parser = argparse.ArgumentParser(description="离线预合成语音包 clips/")
    parser.add_argument("--voice-dir", required=True, help="语音包目录路径")
    parser.add_argument("--phrases", required=True, help="phrase_list.json 路径")
    parser.add_argument("--group", default=None, help="只处理指定分组（如 emotions）")
    parser.add_argument("--skip-existing", action="store_true",
                        help="跳过 clips/ 中已存在的文件")
    args = parser.parse_args()

    voice_dir = Path(args.voice_dir).resolve()
    cfg_path = voice_dir / "config.json"
    if not cfg_path.exists():
        print(f"❌ 找不到 config.json: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(args.phrases, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    ref = cfg["reference"]
    ref_wav = str(voice_dir / ref["audio"])
    prompt_text = ref["text"]
    prompt_lang = ref.get("lang", "zh")
    inf = cfg.get("inference", {})

    print("🔧 加载 GPT-SoVITS 模型...")
    pipeline = _load_pipeline(voice_dir, cfg)
    print("✅ 模型加载完成\n")

    items = _flatten(phrases, group_filter=args.group)
    errors, success = [], 0

    for rel_path, text in items:
        out_path = voice_dir / rel_path
        if args.skip_existing and out_path.exists():
            print(f"  ⏭️  跳过: {rel_path}")
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"  🎤 合成: {rel_path}  ← 「{text}」")
        try:
            audio = _synthesize_to_wav(
                pipeline, ref_wav, prompt_text, prompt_lang, text, inf
            )
            if _quality_check(audio, rel_path):
                out_path.write_bytes(audio)
                print(f"     ✅ 已保存")
                success += 1
            else:
                errors.append({"file": rel_path, "text": text,
                               "reason": "quality_check_failed"})
        except Exception as e:
            print(f"     ❌ 失败: {e}")
            errors.append({"file": rel_path, "text": text, "reason": str(e)})

    print(f"\n📊 完成: {success}/{len(items)} 条，失败 {len(errors)} 条")
    if errors:
        err_path = voice_dir / "prebake_errors.json"
        err_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"⚠️  失败详情: {err_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 验证 CLI help 可用**

```bash
cd python-service && python tools/prebake.py --help
```
Expected: 显示 `--voice-dir`, `--phrases`, `--group`, `--skip-existing` 参数说明

- [ ] **Step 4: Commit**

```bash
git add python-service/tools/__init__.py python-service/tools/prebake.py
git commit -m "feat: add prebake.py CLI for offline voice clip pre-synthesis"
```

---

## Task 8: 创建示例 phrase_list.json

**Files:**
- Create: `python-service/data/voices/laifu-clone/phrase_list.json`

- [ ] **Step 1: 创建目录并写入文件**

先确保目录存在：
```bash
mkdir -p python-service/data/voices/laifu-clone
```

写入 `python-service/data/voices/laifu-clone/phrase_list.json`：

```json
{
  "greetings": [
    { "file": "morning.wav",   "text": "主人早上好！今天也要开心哦！" },
    { "file": "return.wav",    "text": "主人你回来啦！来福好想你！" },
    { "file": "goodnight.wav", "text": "主人晚安，做个好梦，来福明天还在！" }
  ],
  "emotions": {
    "happy": [
      { "file": "happy_01.wav", "text": "太棒了！来福好开心！" },
      { "file": "happy_02.wav", "text": "耶耶耶！" }
    ],
    "sad": [
      { "file": "sad_01.wav", "text": "呜呜...来福有点难过..." },
      { "file": "sad_02.wav", "text": "主人，你不理来福了吗..." }
    ],
    "excited": [
      { "file": "excited_01.wav", "text": "冲冲冲！来福超兴奋！" }
    ],
    "curious": [
      { "file": "curious_01.wav", "text": "咦？这是什么呀？" }
    ]
  },
  "barks": [
    { "file": "bark_short.wav", "text": "汪！" },
    { "file": "bark_long.wav",  "text": "汪汪汪！" },
    { "file": "bark_cute.wav",  "text": "汪呜～" }
  ]
}
```

- [ ] **Step 2: 运行全量测试确认无回归**

```bash
cd python-service && python -m pytest tests/ -v --ignore=tests/test_memory_system.py
```
Expected: 所有新测试通过（`test_tts_cache.py`, `test_clips_player.py`, `test_embedded_engine.py`, `test_tts_router.py`, `test_voice_manager_v2.py`）

- [ ] **Step 3: Commit**

```bash
git add python-service/data/voices/laifu-clone/phrase_list.json
git commit -m "docs: add reference phrase_list.json for laifu-clone voice pack prebake"
```

---

## 预合成使用流程（完成实现后）

模型训练完成，`laifu-clone/config.json` 就位后，执行一次预合成：

```bash
cd python-service
python tools/prebake.py \
  --voice-dir data/voices/laifu-clone \
  --phrases   data/voices/laifu-clone/phrase_list.json \
  --skip-existing
```

之后启动应用，`clips/` 目录中的音效立即可用，LLM 回复由内嵌推理处理。

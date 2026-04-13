"""
内嵌 GPT-SoVITS 推理引擎。
直接调用 TTS 类，无子进程、无 HTTP。
通过 warmup() 在后台线程预热，不阻塞 asyncio 事件循环。
"""
import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


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
        import io as _io
        import numpy as np
        import soundfile as sf

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
        buf = _io.BytesIO()
        sf.write(buf, audio_data, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    async def synthesize(self, text: str) -> bytes:
        """合成语音，返回 WAV 字节。未就绪时抛出 RuntimeError。"""
        if not self._ready:
            raise RuntimeError("模型尚未就绪，请等待 warmup() 完成")
        async with self._lock:   # 推理非线程安全，串行执行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._run_inference, text)

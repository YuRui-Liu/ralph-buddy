#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT-SoVITS TTS 引擎
通过 api_v2.py 子进程调用本地训练的来福克隆模型
"""

import os
import sys
import json
import asyncio
import subprocess
import time
import signal
from typing import Optional
import httpx


class GptSoVITSEngine:
    """GPT-SoVITS 语音合成引擎（通过 HTTP 调用本地 api_v2 子进程）"""

    STARTUP_TIMEOUT = 60  # 等待子进程就绪的最长秒数

    def __init__(self, voice_dir: str):
        """
        初始化引擎

        Args:
            voice_dir: 语音包目录，包含 config.json、models/、reference/
        """
        try:
            from core.config import get_config
            self.API_PORT = get_config()['paths'].get('gpt_sovits_port', 9880)
        except Exception:
            self.API_PORT = 9880
        self.API_BASE = f"http://127.0.0.1:{self.API_PORT}"

        self.voice_dir = os.path.abspath(voice_dir)
        self._process: Optional[subprocess.Popen] = None

        # 读取语音包配置
        cfg_path = os.path.join(self.voice_dir, "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            self._cfg = json.load(f)

        gsv = self._cfg["gpt_sovits_config"]
        # 绝对化模型/参考音频路径
        self.gpt_path = os.path.join(self.voice_dir, gsv["gpt_path"])
        self.sovits_path = os.path.join(self.voice_dir, gsv["sovits_path"])
        self.ref_wav = os.path.join(self.voice_dir, gsv["ref_wav_path"])
        self.prompt_text = gsv["prompt_text"]
        self.prompt_lang = gsv.get("prompt_lang", "zh")
        self.text_lang = gsv.get("text_language", "zh")

        inf = self._cfg.get("inference_params", {})
        self.top_k = inf.get("top_k", 20)
        self.top_p = inf.get("top_p", 0.85)
        self.temperature = inf.get("temperature", 0.6)
        self.speed = inf.get("speed", 1.0)

    # ------------------------------------------------------------------
    # 子进程管理
    # ------------------------------------------------------------------

    def _find_api_script(self) -> str:
        """定位 tools/GPT-SoVITS/api_v2.py"""
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(
            os.path.join(here, "..", "..", "tools", "GPT-SoVITS", "api_v2.py")
        )
        if not os.path.exists(candidate):
            raise FileNotFoundError(f"找不到 api_v2.py: {candidate}")
        return candidate

    def _api_alive(self) -> bool:
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.API_BASE}/", timeout=2)
            return True
        except Exception:
            return False

    async def start(self):
        """启动 GPT-SoVITS api_v2 子进程（若已有实例在运行则跳过）"""
        if self._api_alive():
            print("✅ GPT-SoVITS API 已在运行，跳过启动")
            await self._load_models()
            return

        api_script = self._find_api_script()
        cwd = os.path.dirname(api_script)

        print(f"🚀 启动 GPT-SoVITS API: {api_script}")
        self._process = subprocess.Popen(
            [sys.executable, api_script,
             "-p", str(self.API_PORT),
             "-a", "127.0.0.1"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # 等待就绪
        deadline = time.time() + self.STARTUP_TIMEOUT
        while time.time() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError("GPT-SoVITS 子进程意外退出")
            if self._api_alive():
                print("✅ GPT-SoVITS API 已就绪")
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError(f"GPT-SoVITS 启动超时（{self.STARTUP_TIMEOUT}s）")

        await self._load_models()

    async def _load_models(self):
        """向 API 加载来福克隆模型权重"""
        async with httpx.AsyncClient(timeout=30) as client:
            # 加载 GPT 权重
            r = await client.get(
                f"{self.API_BASE}/set_gpt_weights",
                params={"weights_path": self.gpt_path}
            )
            if r.status_code != 200:
                raise RuntimeError(f"加载 GPT 权重失败: {r.text}")
            print(f"✅ GPT 权重已加载: {os.path.basename(self.gpt_path)}")

            # 加载 SoVITS 权重
            r = await client.get(
                f"{self.API_BASE}/set_sovits_weights",
                params={"weights_path": self.sovits_path}
            )
            if r.status_code != 200:
                raise RuntimeError(f"加载 SoVITS 权重失败: {r.text}")
            print(f"✅ SoVITS 权重已加载: {os.path.basename(self.sovits_path)}")

    def close(self):
        """终止子进程"""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
            print("🛑 GPT-SoVITS 子进程已终止")

    # ------------------------------------------------------------------
    # 推理接口（与 EdgeTTSEngine 保持一致）
    # ------------------------------------------------------------------

    async def synthesize(self, text: str) -> bytes:
        """
        文字转语音

        Args:
            text: 要合成的文本

        Returns:
            WAV 音频字节
        """
        params = {
            "text": text,
            "text_lang": self.text_lang,
            "ref_audio_path": self.ref_wav,
            "prompt_text": self.prompt_text,
            "prompt_lang": self.prompt_lang,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "speed_factor": self.speed,
            "media_type": "wav",
            "text_split_method": "cut5",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(f"{self.API_BASE}/tts", params=params)

        if r.status_code != 200:
            raise RuntimeError(f"GPT-SoVITS 推理失败 ({r.status_code}): {r.text[:200]}")

        return r.content

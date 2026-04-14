#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper STT 引擎
使用 faster-whisper 进行本地语音转文字
"""

import os
import io
import tempfile
import numpy as np
from typing import Optional, Tuple
# pydub 已不再使用，改为直接调用 ffmpeg subprocess（解决 webm/opus 解码静音问题）

# 延迟导入 faster-whisper，避免启动时加载
_whisper_model = None

def get_whisper_model(model_size: str = "base", local_model_path: str = None):
    """获取或初始化 Whisper 模型（单例模式）"""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        
        # 自动检测设备
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        # 设置镜像
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        
        # 检查本地模型
        if local_model_path and os.path.exists(local_model_path):
            print(f"🎤 加载本地 Whisper 模型: {local_model_path}")
            model_path = local_model_path
        else:
            print(f"🎤 加载 Whisper 模型: {model_size} ({device})")
            model_path = model_size
        
        try:
            _whisper_model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type,
                download_root=os.path.join(os.path.dirname(__file__), "models"),
                local_files_only=(local_model_path is not None)
            )
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            print("💡 请运行: python download_whisper_model.py")
            raise
            
    return _whisper_model


class WhisperEngine:
    """Whisper 语音识别引擎"""
    
    def __init__(self, model_size: str = "base", local_model_path: str = None):
        """
        初始化 Whisper 引擎
        
        Args:
            model_size: 模型大小 (tiny, base, small, medium, large)
                       tiny=39M, base=74M, small=244M, medium=769M, large=1550M
            local_model_path: 本地模型路径（可选）
        """
        self.model_size = model_size
        self.local_model_path = local_model_path
        self.model = None
        self._initialized = False
    
    async def initialize(self):
        """异步初始化模型"""
        if not self._initialized:
            self.model = get_whisper_model(self.model_size, self.local_model_path)
            self._initialized = True
            print(f"✅ Whisper STT 已就绪 (模型: {self.model_size})")
    
    def _parse_wav_direct(self, audio_bytes: bytes) -> np.ndarray:
        """
        直接解析 WAV 数据为 float32 数组，跳过 ffmpeg。
        适用于 MicRecorder 输出的已标准化 WAV（16kHz mono 16-bit）。
        如果 WAV 格式不匹配则回退到 ffmpeg 转换。
        """
        import wave
        try:
            buf = io.BytesIO(audio_bytes)
            with wave.open(buf, "rb") as wf:
                sr = wf.getframerate()
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                raw = wf.readframes(wf.getnframes())

            print(f"🎵 WAV 直接解析: {sr}Hz, {ch}ch, {sw*8}bit, {len(raw)} bytes")

            if sw == 2:  # 16-bit
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sw == 4:  # 32-bit float
                samples = np.frombuffer(raw, dtype=np.float32)
            else:
                print(f"⚠️ WAV 位深 {sw*8} 不支持直接解析，回退 ffmpeg")
                return self._convert_audio(audio_bytes, "wav")

            # 如果是多声道，取第一个
            if ch > 1:
                samples = samples[::ch]

            # 如果不是 16kHz，重采样
            if sr != 16000:
                import librosa
                samples = librosa.resample(samples, orig_sr=sr, target_sr=16000)
                print(f"🎵 重采样 {sr}→16000")

            return samples
        except Exception as e:
            print(f"⚠️ WAV 直接解析失败: {e}，回退 ffmpeg")
            return self._convert_audio(audio_bytes, "wav")

    def _convert_audio(self, audio_bytes: bytes, source_format: str = "webm") -> np.ndarray:
        """
        将音频转换为 Whisper 需要的格式 (16kHz, mono, float32)

        直接调用 ffmpeg subprocess 进行转换，绕过 pydub：
        pydub 对浏览器 MediaRecorder 生成的 webm/opus 解码后会产生全零静音数据。

        Args:
            audio_bytes: 原始音频数据
            source_format: 源格式 (webm, wav, mp3, etc.)

        Returns:
            numpy array of audio samples
        """
        import subprocess, struct

        tmp_in = None
        tmp_out = None
        try:
            print(f"🎵 转换音频格式: {source_format}, 大小: {len(audio_bytes)} bytes")

            # 写入临时文件（ffmpeg 需要 seek 读取头信息）
            fd, tmp_in = tempfile.mkstemp(suffix=f".{source_format}")
            try:
                os.write(fd, audio_bytes)
            finally:
                os.close(fd)

            fd, tmp_out = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            # 直接调用 ffmpeg：输入自动检测格式，输出 16kHz mono 16-bit WAV
            cmd = [
                "ffmpeg", "-y",
                "-i", tmp_in,
                "-ar", "16000",
                "-ac", "1",
                "-sample_fmt", "s16",
                "-f", "wav",
                tmp_out,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                # 打印 ffmpeg 错误的最后几行（避免刷屏）
                stderr_lines = result.stderr.strip().splitlines()
                tail = "\n".join(stderr_lines[-10:])
                print(f"❌ ffmpeg 返回码 {result.returncode}:\n{tail}")
                raise RuntimeError(f"ffmpeg 转换失败 (code {result.returncode})")

            # 读取 WAV 输出
            with open(tmp_out, "rb") as f:
                wav_bytes = f.read()

            # 解析 WAV：跳过 44 字节标准头，读取 PCM s16le 数据
            # 用 wave 标准库更安全地解析
            import wave
            with wave.open(tmp_out, "rb") as wf:
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()

            print(f"🎵 音频信息: {sample_rate}Hz, {channels}ch, "
                  f"{n_frames / sample_rate * 1000:.0f}ms")

            # 转为 float32 [-1, 1]
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            print(f"🎵 转换完成: {len(samples)} samples")
            return samples

        except Exception as e:
            print(f"❌ 音频转换失败: {e}")
            raise RuntimeError(f"音频格式转换失败: {e}")
        finally:
            for p in (tmp_in, tmp_out):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
    
    async def transcribe(
        self,
        audio_bytes: bytes,
        source_format: str = "webm",
        language: Optional[str] = "zh",
        vad_filter: bool = False
    ) -> Tuple[str, float]:
        """
        将语音转换为文字

        Args:
            audio_bytes: 音频数据
            source_format: 音频格式
            language: 语言代码 (zh, en, ja, etc.)，None 为自动检测
            vad_filter: 是否启用服务端 VAD 过滤。
                       默认 False：客户端 (useSimpleVAD) 已截取好语音片段，
                       再做一次 VAD 容易把短促的中文词汇全部过滤掉导致识别结果为空。

        Returns:
            (转录文本, 置信度)
        """
        if not self._initialized:
            await self.initialize()

        try:
            # WAV 格式直接解析（MicRecorder 输出已经是 16kHz mono 16-bit）
            if source_format == "wav" and audio_bytes[:4] == b"RIFF":
                audio_data = self._parse_wav_direct(audio_bytes)
            else:
                audio_data = self._convert_audio(audio_bytes, source_format)

            # 音频质量诊断
            duration_sec = len(audio_data) / 16000
            rms = float(np.sqrt(np.mean(audio_data ** 2)))
            peak = float(np.max(np.abs(audio_data)))
            print(f"🎤 开始语音识别: {duration_sec:.2f}s, RMS={rms:.4f}, peak={peak:.4f}")

            # 太短的音频 Whisper 容易产生幻觉（如 "字幕by索兰娅"），直接跳过
            if duration_sec < 0.5:
                print(f"⚠️ 音频过短 ({duration_sec:.2f}s)，跳过识别")
                return "", 0.0

            # 几乎是静音的音频，跳过
            if rms < 0.001:
                print(f"⚠️ 音频几乎是静音 (RMS={rms:.6f})，跳过识别")
                return "", 0.0

            # 执行识别
            # no_speech_threshold 调高 → 更宽松，不容易把语音误判为 "无语音" 而丢弃
            segments, info = self.model.transcribe(
                audio_data,
                language=language,
                vad_filter=vad_filter,
                initial_prompt="以下是普通话的语音对话。",
                condition_on_previous_text=False,
                no_speech_threshold=0.9,
            )

            # 合并所有片段
            texts = []
            avg_probability = 0.0
            segment_count = 0

            for segment in segments:
                texts.append(segment.text.strip())
                avg_probability += segment.avg_logprob
                segment_count += 1
                print(f"📝 片段: {segment.text.strip()} "
                      f"(logprob={segment.avg_logprob:.2f}, "
                      f"no_speech={segment.no_speech_prob:.2f})")

            text = " ".join(texts).strip()

            if segment_count == 0:
                print(f"⚠️ Whisper 未返回任何片段 (language={info.language}, "
                      f"lang_prob={info.language_probability:.2f})")
            
            # 计算置信度 (将 logprob 转换为概率)
            confidence = np.exp(avg_probability / max(segment_count, 1)) if segment_count > 0 else 0.0
            confidence = max(0.0, min(1.0, confidence))  # 限制在 [0, 1]
            
            print(f"✅ 识别结果: {text} (置信度: {confidence:.2f})")
            
            return text, confidence
            
        except Exception as e:
            print(f"❌ STT 识别失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def transcribe_file(self, file_path: str, **kwargs) -> Tuple[str, float]:
        """从文件转录"""
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        
        # 从文件扩展名推断格式
        ext = os.path.splitext(file_path)[1].lower().replace(".", "")
        if ext in ["wav", "mp3", "webm", "ogg", "m4a", "flac"]:
            return await self.transcribe(audio_bytes, source_format=ext, **kwargs)
        else:
            return await self.transcribe(audio_bytes, **kwargs)


# 全局实例
_whisper_engine: Optional[WhisperEngine] = None

async def get_engine() -> WhisperEngine:
    """获取全局 STT 引擎实例"""
    global _whisper_engine
    if _whisper_engine is None:
        _whisper_engine = WhisperEngine()
        await _whisper_engine.initialize()
    return _whisper_engine

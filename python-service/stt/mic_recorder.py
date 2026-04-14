"""
麦克风录音模块 — 绕过 Electron/Chromium 的 getUserMedia 限制。
直接通过 Python sounddevice 访问系统麦克风。

自动探测可用设备：优先选择能产生非零音频数据的设备。
Intel SST 麦克风在 WASAPI 下可能静音，但 WDM-KS 后端通常能正常工作。
"""

import io
import threading
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None
    print("⚠️ sounddevice 未安装，请运行: pip install sounddevice")

try:
    import soundfile as sf
except ImportError:
    sf = None


class MicRecorder:
    CHANNELS = 1
    DTYPE = "float32"

    def __init__(self):
        self._lock = threading.Lock()
        self._recording = False
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._device = None       # 自动探测的设备索引
        self._sample_rate = 16000  # 将在 probe 后更新

    # ── 设备探测 ──

    def probe_best_device(self):
        """探测能产生真实音频的最佳麦克风设备。
        优先 WDM-KS 后端（绕过 WASAPI/Intel SST 限制）。
        """
        if sd is None:
            return
        devices = sd.query_devices()
        candidates = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] <= 0:
                continue
            sr = int(d["default_samplerate"])
            api_name = sd.query_hostapis(d["hostapi"])["name"]
            try:
                # 录 0.5 秒测试
                audio = sd.rec(max(sr // 2, 8000), samplerate=sr, channels=1,
                               dtype="float32", device=i)
                sd.wait()
                peak = float(np.max(np.abs(audio)))
                # 过滤 NaN 和异常值（正常音频 peak < 1.0）
                if np.isnan(peak) or peak > 1.0:
                    continue
                candidates.append((i, d["name"], api_name, sr, peak))
            except Exception:
                pass

        # 按 peak 排序，选最大的
        candidates.sort(key=lambda c: c[4], reverse=True)

        for idx, name, api, sr, peak in candidates[:8]:
            status = "*" if peak > 0.0005 else " "
            print(f"  {status} [{idx}] peak={peak:.6f} sr={sr} api={api}")

        # 选 peak 最高且 > 0.0003 的设备
        for c in candidates:
            if c[4] > 0.0003:
                self._device = c[0]
                self._sample_rate = c[3]
                print(f"[MicRecorder] selected device [{c[0]}] ({c[2]}, sr={c[3]})")
                return

        self._device = None
        self._sample_rate = 16000
        print("[MicRecorder] no working device found, using system default")

    @staticmethod
    def list_devices():
        if sd is None:
            return []
        devices = sd.query_devices()
        result = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                api = sd.query_hostapis(d["hostapi"])["name"]
                result.append({
                    "index": i,
                    "name": d["name"],
                    "api": api,
                    "channels": d["max_input_channels"],
                    "sample_rate": d["default_samplerate"],
                })
        return result

    # ── 录音控制 ──

    def start(self, device=None):
        """开始录音。device=None 使用自动探测的设备。"""
        if sd is None:
            raise RuntimeError("sounddevice 未安装")

        with self._lock:
            if self._recording:
                return
            self._chunks = []
            self._recording = True

        use_device = device if device is not None else self._device
        sr = self._sample_rate

        self._stream = sd.InputStream(
            samplerate=sr,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            device=use_device,
            blocksize=1024,
            callback=self._audio_callback,
        )
        self._stream.start()
        print(f"[MicRecorder] 录音开始 (sr={sr}, device={use_device})")

    def stop(self) -> bytes:
        """停止录音，返回 WAV 字节数据（16kHz mono 16-bit）。"""
        with self._lock:
            if not self._recording:
                return b""
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            print("[MicRecorder] 无录音数据")
            return b""

        audio = np.concatenate(self._chunks, axis=0).flatten()
        duration = len(audio) / self._sample_rate
        rms = float(np.sqrt(np.mean(audio ** 2)))
        peak = float(np.max(np.abs(audio)))
        print(f"[MicRecorder] 录音结束: {duration:.1f}s, RMS={rms:.6f}, peak={peak:.6f}, "
              f"device={self._device}, sr={self._sample_rate}, chunks={len(self._chunks)}")

        if peak < 0.001:
            print(f"⚠️ [MicRecorder] 录音几乎静音! 设备可能不工作。"
                  f"请检查麦克风权限或运行 probe_best_device() 重新探测。")

        # 如果录音采样率不是 16kHz，重采样（Whisper 需要 16kHz）
        if self._sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=self._sample_rate, target_sr=16000)
            print(f"[MicRecorder] 重采样 {self._sample_rate}→16000, {len(audio)} samples")

        # 编码为 WAV (16kHz mono 16-bit)
        buf = io.BytesIO()
        sf.write(buf, audio, 16000, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()
        print(f"[MicRecorder] WAV: {len(wav_bytes)} bytes")
        return wav_bytes

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[MicRecorder] 状态: {status}")
        if self._recording:
            self._chunks.append(indata.copy())

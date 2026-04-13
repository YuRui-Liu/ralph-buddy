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

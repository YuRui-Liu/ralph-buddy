import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional


class TTSCache:
    """LRU 磁盘缓存：key=sha256(text:voice_id)[:16]，超限时淘汰最旧条目。"""

    def __init__(self, cache_dir: str, limit_mb: int = 500):
        self._dir = Path(cache_dir)
        self._limit = limit_mb * 1024 * 1024
        self._index_path = self._dir / "index.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index: dict = {}
        self._lock = threading.Lock()
        self._load()

    def _key(self, text: str, voice_id: str) -> str:
        return hashlib.sha256(f"{text}:{voice_id}".encode()).hexdigest()[:16]

    def _load(self):
        if self._index_path.exists():
            try:
                self._index = json.loads(
                    self._index_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "TTSCache: corrupt index, resetting. %s", exc
                )
                self._index = {}

    def _save(self):
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._index, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._index_path)

    def get(self, text: str, voice_id: str) -> Optional[bytes]:
        with self._lock:
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
        with self._lock:
            k = self._key(text, voice_id)
            filename = f"{k}.wav"
            self._index[k] = {
                "file": filename,
                "size": len(audio),
                "atime": time.time(),
            }
            self._evict()
            (self._dir / filename).write_bytes(audio)
            self._save()

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

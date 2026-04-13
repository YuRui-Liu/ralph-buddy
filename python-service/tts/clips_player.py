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
        elif isinstance(node, str):
            path_str = node
        else:
            return None   # dict node with no sub_key, or unexpected type

        fp = self._root / path_str
        if not fp.exists():
            return None
        return fp.read_bytes()

    def has(self, hint: str) -> bool:
        return self.get(hint) is not None

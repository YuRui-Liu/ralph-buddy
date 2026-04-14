#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PetAttributeManager — 来福宠物属性管理器

管理 6 个核心属性（健康值、心情、精力、亲密度、顺从度、毒舌值），
持久化至 SQLite pet_attributes 表。
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional

# 数据库路径（与 MemorySystem 共用同一个 DB 文件）
_DEFAULT_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'memory', 'memory.db')
)

# ── 默认属性值 ──────────────────────────────────────────────────────────── #
DEFAULTS: dict[str, float] = {
    'health':    80.0,
    'mood':      70.0,
    'energy':    80.0,
    'affection': 50.0,
    'obedience': 60.0,
    'snark':     30.0,
}

# ── 每 tick（1 分钟）自然衰减/增长量 ────────────────────────────────────── #
TICK_DELTAS: dict[str, float] = {
    'health':    -1.0,
    'mood':      -2.0,
    'energy':    -3.0,
    'affection': -0.5,
    'obedience':  0.0,
    'snark':      0.0,
}

# ── 离线期间每小时变化量 ─────────────────────────────────────────────────── #
OFFLINE_DELTAS: dict[str, float] = {
    'health':    -0.5,
    'mood':      -1.0,
    'energy':    +5.0,
    'affection': -1.0,
    'obedience':  0.0,
    'snark':      0.0,
}

# ── 互动类型对应的属性变化量 ────────────────────────────────────────────── #
INTERACTION_DELTAS: dict[str, dict[str, float]] = {
    'chat':      {'mood': +3.0, 'energy': -2.0, 'affection': +2.0},
    'play':      {'mood': +5.0, 'energy': -5.0, 'affection': +1.0},
    'responded': {'mood': +2.0, 'affection': +3.0, 'obedience': +1.0},
    'ignored':   {'mood': -5.0, 'affection': -2.0},
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """将值限制在 [lo, hi] 范围内。"""
    return max(lo, min(hi, value))


class PetAttributeManager:
    """
    宠物属性管理器。

    所有属性存储于 SQLite pet_attributes 表中，
    支持 tick 衰减、离线补偿、互动更新、梦境调整等操作。
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._attrs: dict[str, float] = {}
        self._last_dream_time: Optional[datetime] = None

    # ── 初始化 / 持久化 ─────────────────────────────────────────────────── #

    def load(self) -> None:
        """从 SQLite 加载属性；若记录不存在则写入默认值。"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pet_attributes (
                    key        TEXT PRIMARY KEY,
                    value      REAL NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            ''')
            conn.commit()

            rows = conn.execute(
                'SELECT key, value FROM pet_attributes'
            ).fetchall()
            loaded = {k: v for k, v in rows}

        # 以 DEFAULTS 为基础，用已存储的值覆盖
        self._attrs = {k: loaded.get(k, v) for k, v in DEFAULTS.items()}

        # 处理 last_dream_time（作为特殊 key 存储）
        if '_last_dream_time' in loaded:
            raw = loaded['_last_dream_time']
            try:
                self._last_dream_time = datetime.fromisoformat(str(raw))
            except (ValueError, TypeError):
                self._last_dream_time = None
        else:
            self._last_dream_time = None

        # 若有缺失的属性（首次运行），持久化默认值
        missing = [k for k in DEFAULTS if k not in loaded]
        if missing:
            self._persist_keys(missing)

    def save(self) -> None:
        """将当前属性写入 SQLite。"""
        all_keys = list(self._attrs.keys())
        self._persist_keys(all_keys, include_dream_time=True)

    def _persist_keys(
        self,
        keys: list[str],
        include_dream_time: bool = False,
    ) -> None:
        now = datetime.now().isoformat()
        rows = [(k, self._attrs[k], now) for k in keys if k in self._attrs]

        if include_dream_time:
            dt_val = (
                self._last_dream_time.isoformat()
                if self._last_dream_time is not None
                else None
            )
            if dt_val is not None:
                rows.append(('_last_dream_time', dt_val, now))

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                'INSERT OR REPLACE INTO pet_attributes (key, value, updated_at) '
                'VALUES (?, ?, ?)',
                rows,
            )
            conn.commit()

    # ── 衰减 / 补偿 ─────────────────────────────────────────────────────── #

    def tick(self) -> None:
        """执行一次自然衰减 tick（约 1 分钟）。"""
        for k, delta in TICK_DELTAS.items():
            self._attrs[k] = _clamp(self._attrs[k] + delta)

    def apply_offline(self, hours: float) -> None:
        """根据离线小时数补偿属性变化。"""
        for k, delta_per_hour in OFFLINE_DELTAS.items():
            self._attrs[k] = _clamp(self._attrs[k] + delta_per_hour * hours)

    # ── 互动 ────────────────────────────────────────────────────────────── #

    def apply_interaction(self, interaction_type: str) -> None:
        """
        应用互动对属性的影响。

        :param interaction_type: 'chat' | 'play' | 'responded' | 'ignored'
        :raises ValueError: 若 interaction_type 未知。
        """
        if interaction_type not in INTERACTION_DELTAS:
            raise ValueError(
                f"未知互动类型: {interaction_type!r}，"
                f"支持的类型: {list(INTERACTION_DELTAS.keys())}"
            )
        for k, delta in INTERACTION_DELTAS[interaction_type].items():
            self._attrs[k] = _clamp(self._attrs[k] + delta)

    # ── 梦境 ────────────────────────────────────────────────────────────── #

    def apply_dream_delta(self, deltas: dict[str, float]) -> None:
        """
        应用梦境期间的属性调整。

        每个 delta 值会被限制在 [-10, +10] 之内，属性最终值限制在 [0, 100]。
        """
        for k, delta in deltas.items():
            if k in self._attrs:
                clamped_delta = _clamp(delta, -10.0, +10.0)
                self._attrs[k] = _clamp(self._attrs[k] + clamped_delta)

    # ── 查询 ────────────────────────────────────────────────────────────── #

    def get_all(self) -> dict[str, float]:
        """返回当前所有属性的副本。"""
        return dict(self._attrs)

    def get_prompt_hints(self) -> str:
        """
        返回用于注入系统提示词的中文状态描述。

        示例：
            健康值 80/100 | 心情 70/100 | 精力 80/100 |
            亲密度 50/100 | 顺从度 60/100 | 毒舌值 30/100
        """
        labels = {
            'health':    '健康值',
            'mood':      '心情',
            'energy':    '精力',
            'affection': '亲密度',
            'obedience': '顺从度',
            'snark':     '毒舌值',
        }
        parts = [
            f"{labels[k]} {int(round(self._attrs[k]))}/100"
            for k in labels
        ]
        return ' | '.join(parts)

    # ── 梦境时间 ────────────────────────────────────────────────────────── #

    def get_last_dream_time(self) -> Optional[datetime]:
        """返回上一次梦境触发时间（None 表示从未触发）。"""
        return self._last_dream_time

    def set_last_dream_time(self, dt: datetime) -> None:
        """设置上一次梦境触发时间。"""
        self._last_dream_time = dt

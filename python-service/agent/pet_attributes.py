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
    'play':      {'mood': +5.0, 'energy': -5.0, 'affection': +1.0, 'health': +2.0},
    'feed':      {'health': +10.0, 'mood': +3.0, 'energy': +5.0, 'affection': +1.0},
    'responded': {'mood': +2.0, 'affection': +3.0, 'obedience': +1.0},
    'ignored':   {'mood': -5.0, 'affection': -2.0},
}


# ── 属性键列表 ──────────────────────────────────────────────────────────── #
ATTR_KEYS: list[str] = list(DEFAULTS.keys())


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
        self.attrs: dict[str, float] = {}
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
        self.attrs = {k: loaded.get(k, v) for k, v in DEFAULTS.items()}

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
        all_keys = list(self.attrs.keys())
        self._persist_keys(all_keys, include_dream_time=True)

    def _persist_keys(
        self,
        keys: list[str],
        include_dream_time: bool = False,
    ) -> None:
        now = datetime.now().isoformat()
        rows = [(k, self.attrs[k], now) for k in keys if k in self.attrs]

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
            self.attrs[k] = _clamp(self.attrs[k] + delta)

    def apply_offline(self, hours: float) -> None:
        """根据离线小时数补偿属性变化。"""
        for k, delta_per_hour in OFFLINE_DELTAS.items():
            self.attrs[k] = _clamp(self.attrs[k] + delta_per_hour * hours)

    # ── 互动 ────────────────────────────────────────────────────────────── #

    def apply_interaction(self, interaction_type: str) -> None:
        """
        应用互动对属性的影响。

        :param interaction_type: 'chat' | 'play' | 'responded' | 'ignored'
        """
        deltas = INTERACTION_DELTAS.get(interaction_type)
        if deltas is None:
            return
        for k, delta in deltas.items():
            self.attrs[k] = _clamp(self.attrs[k] + delta)

    # ── 梦境 ────────────────────────────────────────────────────────────── #

    def apply_dream_delta(self, deltas: dict[str, float]) -> None:
        """
        应用梦境期间的属性调整。

        每个 delta 值会被限制在 [-10, +10] 之内，属性最终值限制在 [0, 100]。
        """
        for k, delta in deltas.items():
            if k in self.attrs:
                clamped_delta = _clamp(delta, -10.0, +10.0)
                self.attrs[k] = _clamp(self.attrs[k] + clamped_delta)

    # ── 查询 ────────────────────────────────────────────────────────────── #

    def get_all(self) -> dict[str, float]:
        """返回当前所有属性的副本。"""
        return dict(self.attrs)

    def get_prompt_hints(self) -> str:
        """返回用于注入系统提示词的中文状态描述（多行格式）。"""
        labels = {
            'health':    '健康值',
            'mood':      '心情',
            'energy':    '精力',
            'affection': '亲密度',
            'obedience': '顺从度',
            'snark':     '毒舌值',
        }
        lines = ['【来福当前状态】']
        for k, label in labels.items():
            val = self.attrs[k]
            desc = _describe(k, val)
            lines.append(f'{label}: {int(val)}/100 — {desc}')
        lines.append('')
        lines.append('请根据以上状态调整你的回应风格和行为。')
        return '\n'.join(lines)

    def build_self_awareness(self) -> str:
        """基于属性组合生成来福的第一人称感受文本（3-4句话）。"""
        energy = self.attrs['energy']
        mood = self.attrs['mood']
        affection = self.attrs['affection']
        snark = self.attrs['snark']
        health = self.attrs['health']
        obedience = self.attrs['obedience']

        lines: list[str] = []

        # ── 精力 x 心情 → 行为倾向 ──
        e_high, m_high = energy >= 60, mood >= 60
        if e_high and m_high:
            lines.append('你精神特别好，有点坐不住，想找主人玩点什么。')
        elif e_high and not m_high:
            lines.append('你浑身有劲但心里不太痛快，有点焦躁，想咬点什么东西。')
        elif not e_high and m_high:
            lines.append('你懒洋洋的但心里挺满足，想窝在主人脚边打个盹。')
        else:
            lines.append('你趴在地上不太想动，尾巴也懒得摇。')

        # ── 亲密度 x 毒舌值 → 说话风格 ──
        a_high, s_high = affection >= 60, snark >= 50
        if a_high and s_high:
            lines.append('你和主人很熟了，说话比较随意，偶尔调侃他几句也不怕他生气。')
        elif a_high and not s_high:
            lines.append('你和主人很亲，说话软软的，喜欢蹭他撒娇。')
        elif not a_high and s_high:
            lines.append('你对主人还有点防备，说话带刺，不太给面子。')
        else:
            lines.append('你对主人还不太熟，有点拘谨客气，不敢太放开。')

        # ── 顺从度 ──
        if obedience >= 70:
            lines.append('主人说什么你都愿意配合，是个乖狗。')
        elif obedience <= 35:
            lines.append('不过你有自己的主意，不一定听主人的指挥。')

        # ── 健康 叠加修饰 ──
        if health < 40:
            lines.append('而且你觉得身体不太舒服，有点蔫蔫的。')
        elif health < 60:
            lines.append('身体有一点点不舒服，但还扛得住。')

        return '\n'.join(lines)

    # ── 梦境时间 ────────────────────────────────────────────────────────── #

    def get_last_dream_time(self) -> Optional[datetime]:
        """返回上一次梦境触发时间（None 表示从未触发）。"""
        return self._last_dream_time

    def set_last_dream_time(self, dt: datetime) -> None:
        """设置上一次梦境触发时间。"""
        self._last_dream_time = dt


def _describe(key: str, val: float) -> str:
    """根据属性值生成简短描述"""
    v = int(val)
    descs = {
        'health':    ('状态不错', '有点虚弱', '很不舒服'),
        'mood':      ('心情很好', '有点低落', '情绪低迷'),
        'energy':    ('精力充沛', '有点累了', '筋疲力尽'),
        'affection': ('和主人很亲近', '和主人关系一般', '和主人还不太熟'),
        'obedience': ('很听话', '有时候会任性', '非常任性'),
        'snark':     ('嘴巴很毒', '偶尔调侃', '说话温柔'),
    }
    high, mid, low = descs.get(key, ('', '', ''))
    if v >= 70: return high
    if v >= 40: return mid
    return low

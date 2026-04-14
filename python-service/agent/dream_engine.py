#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamEngine — 来福梦境引擎

当来福进入睡眠状态且距离上次梦境 >= 4 小时时触发。
调用 LLM 生成梦境内容，巩固记忆，更新用户画像，并调整属性。
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from agent.pet_attributes import PetAttributeManager, ATTR_KEYS  # noqa: F401

DREAM_COOLDOWN_HOURS = 4


class DreamEngine:
    """
    梦境引擎。

    :param memory_system: MemorySystem 实例（使用 .short_term、._format_profile()、.conn）
    :param attr_manager:  PetAttributeManager 实例
    :param llm_caller:    异步函数  async (prompt: str) -> str
    """

    def __init__(self, memory_system, attr_manager: PetAttributeManager, llm_caller):
        self.memory = memory_system
        self.attr_manager = attr_manager
        self.llm_caller = llm_caller

    # ------------------------------------------------------------------ #
    #  公开接口                                                             #
    # ------------------------------------------------------------------ #

    def can_dream(self) -> bool:
        """若从未做过梦，或距上次梦境已超过 DREAM_COOLDOWN_HOURS 小时，返回 True。"""
        last = self.attr_manager.get_last_dream_time()
        if last is None:
            return True
        return datetime.now() - last >= timedelta(hours=DREAM_COOLDOWN_HOURS)

    async def dream(self) -> Optional[dict]:
        """
        执行一次完整的梦境流程：

        1. 构建提示词（近期记忆 + 用户画像 + 当前属性）
        2. 调用 LLM，获取 JSON 响应
        3. 解析响应：dream_text / profile_updates / attribute_deltas / reasoning
        4. 通过 attr_manager 应用属性 deltas
        5. 更新 last_dream_time 并保存属性
        6. 将 profile_updates 写入 memory.conn（SQLite user_profile 表）
        7. 将梦境记录为 events 表中 importance=3 的事件（前缀"【做梦】"）
        8. 返回结果 dict，失败时返回 None
        """
        prompt = self._build_dream_prompt()

        try:
            raw = await self.llm_caller(prompt)
        except Exception as exc:
            print(f"[DreamEngine] LLM 调用失败: {exc}")
            return None

        # 去除 markdown 代码块包裹
        raw = raw.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[DreamEngine] JSON 解析失败: {exc} — raw={raw!r}")
            return None

        dream_text       = data.get("dream_text", "")
        profile_updates  = data.get("profile_updates", [])
        attribute_deltas = data.get("attribute_deltas", {})
        reasoning        = data.get("reasoning", "")

        # 4. 应用属性 deltas
        if attribute_deltas:
            self.attr_manager.apply_dream_delta(attribute_deltas)

        # 5. 更新梦境时间 + 保存属性
        now = datetime.now()
        self.attr_manager.set_last_dream_time(now)
        self.attr_manager.save()

        # 6. 更新用户画像（SQLite user_profile）
        conn: sqlite3.Connection = self.memory.conn
        if conn and profile_updates:
            c = conn.cursor()
            for item in profile_updates:
                key   = item.get("key")
                value = item.get("value")
                if key and value is not None:
                    c.execute(
                        """INSERT INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)
                           ON CONFLICT(key) DO UPDATE SET
                               value=excluded.value,
                               updated_at=excluded.updated_at""",
                        (key, str(value), now.isoformat()),
                    )
            conn.commit()

        # 7. 将梦境写入 events 表
        if conn and dream_text:
            c = conn.cursor()
            c.execute(
                "INSERT INTO events (content, importance, created_at) VALUES (?, ?, ?)",
                (f"【做梦】{dream_text}", 3, now.isoformat()),
            )
            conn.commit()

        result = {
            "dream_text":       dream_text,
            "profile_updates":  profile_updates,
            "attribute_deltas": attribute_deltas,
            "reasoning":        reasoning,
        }
        return result

    # ------------------------------------------------------------------ #
    #  内部方法                                                             #
    # ------------------------------------------------------------------ #

    def _build_dream_prompt(self) -> str:
        """构建发送给 LLM 的梦境提示词。"""
        # 近期短期记忆（最多 10 条）
        recent = self.memory.short_term[-10:]
        conv_lines = []
        for msg in recent:
            role    = "用户" if msg.get("role") == "user" else "来福"
            content = msg.get("content", "")
            conv_lines.append(f"{role}: {content}")
        conv_text = "\n".join(conv_lines) if conv_lines else "（暂无近期对话）"

        # 用户画像
        profile_text = self.memory._format_profile() or "（暂无用户画像）"

        # 当前属性
        attrs = self.attr_manager.get_all()
        attr_lines = "\n".join(f"- {k}: {int(v)}/100" for k, v in attrs.items())

        prompt = (
            "你是来福的内心世界。来福正在睡觉，请根据以下信息为它生成一段梦境。\n\n"
            "【近期对话记录】\n"
            f"{conv_text}\n\n"
            "【用户画像】\n"
            f"{profile_text}\n\n"
            "【来福当前属性】\n"
            f"{attr_lines}\n\n"
            "请返回纯 JSON（不要包含 markdown 代码块），格式如下：\n"
            '{\n'
            '  "dream_text": "（简短描述来福梦到了什么，用第三人称）",\n'
            '  "profile_updates": [{"key": "...", "value": "..."}],\n'
            '  "attribute_deltas": {"mood": 0, "affection": 0, "energy": 0, '
            '"health": 0, "obedience": 0, "snark": 0},\n'
            '  "reasoning": "（为什么生成这个梦境）"\n'
            '}'
        )
        return prompt

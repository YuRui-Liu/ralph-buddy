#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DogBuddy AI Agent — 多轮历史 + RAG 版
"""

import os
import re
import json
import asyncio
from typing import Optional, Any
from datetime import datetime

from agent.pet_attributes import PetAttributeManager, _clamp


# ── mood_shift → 属性变化映射 ──
MOOD_SHIFT_DELTAS: dict[str, dict[str, float]] = {
    'excited':  {'mood': +5.0, 'energy': -3.0},
    'happy':    {'mood': +3.0, 'energy': -1.0},
    'neutral':  {},
    'bored':    {'mood': -2.0, 'energy': -1.0},
    'annoyed':  {'mood': -3.0, 'snark': +1.0},
    'sad':      {'mood': -5.0, 'affection': +2.0},
    'worried':  {'mood': -2.0, 'affection': +3.0},
}


def parse_llm_response(raw: str) -> dict:
    """Parse LLM JSON reply. Fallback to text truncation on failure."""
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n', 1)[-1] if '\n' in cleaned else cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    if cleaned.startswith('json'):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
        reply = str(data.get('reply', '')).strip()
        think = str(data.get('think', '')).strip()
        action = data.get('action')
        mood_shift = str(data.get('mood_shift', 'neutral')).strip()

        if action in (None, 'null', 'None', ''):
            action = None
        if mood_shift not in MOOD_SHIFT_DELTAS:
            mood_shift = 'neutral'

        if len(reply) > 80:
            for i in range(80, max(len(reply) // 2, 1), -1):
                if reply[i] in '。？！.?!':
                    reply = reply[:i + 1]
                    break
            else:
                reply = reply[:80]

        return {'think': think, 'reply': reply, 'action': action, 'mood_shift': mood_shift}
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    action = None
    match = re.search(r'\[action:(\w+)\]', raw)
    if match:
        action = match.group(1)
    reply = re.sub(r'\[action:\w+\]', '', raw).strip()
    if len(reply) > 60:
        reply = reply[:60]

    return {'think': '', 'reply': reply, 'action': action, 'mood_shift': 'neutral'}


class DogBuddyAgent:

    def __init__(self, memory_system=None, attr_manager=None):
        self.memory      = memory_system
        self.attr_manager: Optional[PetAttributeManager] = attr_manager
        self.llm_ready   = False
        self.llm_client  = None
        self.config      = self._load_config()
        pet_cfg = self.config.get('pet', {})
        self.pet_name        = pet_cfg.get('name', '来福')
        self.pet_personality = pet_cfg.get('personality', '活泼、忠诚、有点粘人、偶尔调皮')
        # Fallback ob/sn used when attr_manager is None (or for direct override via API)
        self._cfg_obedience  = pet_cfg.get('obedience', 60)   # 0-100 顺从度
        self._cfg_snark      = pet_cfg.get('snark', 30)       # 0-100 毒舌值
        self.owner_emotion_context: Optional[str] = None

    # ── Backward-compat properties so main.py can still write agent.obedience ──

    @property
    def obedience(self) -> int:
        if self.attr_manager:
            return int(self.attr_manager.attrs.get('obedience', self._cfg_obedience))
        return self._cfg_obedience

    @obedience.setter
    def obedience(self, value: int) -> None:
        self._cfg_obedience = value

    @property
    def snark(self) -> int:
        if self.attr_manager:
            return int(self.attr_manager.attrs.get('snark', self._cfg_snark))
        return self._cfg_snark

    @snark.setter
    def snark(self, value: int) -> None:
        self._cfg_snark = value

    def _load_config(self) -> dict:
        cfg = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        if os.path.exists(cfg):
            with open(cfg, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"llm": {"provider": "openai", "base_url": "https://api.openai.com/v1",
                        "api_key": "", "model": "gpt-3.5-turbo"},
                "user": {"name": "主人"}}

    async def initialize(self):
        try:
            await self._init_llm()
            self.llm_ready = True
            print(f"🤖 LLM 已连接: {self.config['llm']['provider']} / {self.config['llm']['model']}")
        except Exception as e:
            print(f"⚠️ LLM 初始化失败: {e}，将使用离线模式")

    async def _init_llm(self):
        provider = self.config['llm']['provider']
        if provider == 'openai':
            from openai import AsyncOpenAI
            self.llm_client = AsyncOpenAI(
                base_url=self.config['llm']['base_url'],
                api_key=self.config['llm']['api_key'],
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    # ------------------------------------------------------------------ #
    #  System Prompt                                                        #
    # ------------------------------------------------------------------ #

    def _build_system_prompt(self, memories: list[str]) -> str:
        user_name = self.config.get('user', {}).get('name', '主人')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        weekday = ["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()]

        # Block 1: 身份核心
        identity = (
            f'你是来福，一只中华田园犬。你的主人叫{user_name}。\n'
            '你不是AI助手，你是一个有血有肉的狗。\n'
            '你有自己的情绪、记忆和脾气。你会用人话和主人交流，但思维方式是狗的——'
            '关心吃饭睡觉玩耍，对主人的情绪很敏感，注意力容易被新鲜事吸引。\n'
            '你聪明，能听懂主人说的大部分事情，也能给出有用的建议，'
            '但你会用自己的方式表达，而不是像搜索引擎一样罗列答案。'
        )

        # Block 2: 自我感受（属性组合）
        if self.attr_manager:
            awareness = self.attr_manager.build_self_awareness()
        else:
            awareness = '你精神还不错，心情一般。'
        feeling_block = f'\n\n【你现在的感受】\n{awareness}'

        # Block 3: 记忆上下文
        memory_block = ''
        if memories:
            mem_lines = '\n'.join(f'- {m}' for m in memories if m)
            if mem_lines:
                memory_block = f'\n\n【你记得的事】\n{mem_lines}'

        # Block 4: 回复规则
        rules = (
            '\n\n【回复规则】\n'
            '用 JSON 格式回复，包含 4 个字段：\n'
            '{\n'
            '  "think": "你的内心想法（主人看不到）",\n'
            '  "reply": "你说出口的话",\n'
            '  "action": "动作标签或null",\n'
            '  "mood_shift": "情绪变化"\n'
            '}\n\n'
            '- reply 不超过 30 字，最多 2 句话。主人问具体问题时可到 80 字。\n'
            '- 不要在 reply 里重复主人的话。\n'
            '- 不要无意义地加"汪~"。只在真的兴奋或撒娇时才用语气词。\n'
            '- 如果主人问你问题，认真回答，给出你的看法。你是聪明的狗，不是傻狗。\n'
            '- 如果你不懂，说不懂，但可以猜或者问主人。\n'
            '- action 可选值：happy_run, cuddle, bark, sad, excited, sleep, null\n'
            '- mood_shift 可选值：excited, happy, neutral, bored, annoyed, sad, worried\n'
            '- 只返回 JSON，不要在 JSON 外写任何文字。'
        )

        # Block 5: 情绪上下文（可选）
        emotion_block = ''
        if self.owner_emotion_context:
            emotion_block = (
                f'\n\n【你刚偷看了主人一眼】\n{self.owner_emotion_context}'
            )

        # 时间上下文
        time_block = f'\n\n当前时间：{current_time}，{weekday}。'

        return identity + feeling_block + memory_block + rules + emotion_block + time_block

    # ------------------------------------------------------------------ #
    #  核心对话                                                             #
    # ------------------------------------------------------------------ #

    async def chat(self, user_msg: str) -> dict[str, Any]:
        """处理对话：RAG 检索 + 多轮历史 → LLM (JSON) → 后处理 → 存储"""
        memories = await self.memory.retrieve_relevant(user_msg) if self.memory else []
        history = self.memory.get_recent_history(n_turns=6) if self.memory else []

        messages = [
            {"role": "system", "content": self._build_system_prompt(memories)},
            *history,
            {"role": "user", "content": user_msg},
        ]

        if self.llm_client and self.llm_ready:
            try:
                raw_reply = await self._call_llm_with_messages(messages)
            except Exception as e:
                print(f"LLM call failed: {e}")
                raw_reply = self._fallback_reply(user_msg)
        else:
            raw_reply = self._fallback_reply(user_msg)

        parsed = parse_llm_response(raw_reply)
        reply = parsed['reply']
        action = parsed['action']
        mood_shift = parsed['mood_shift']

        if parsed['think']:
            print(f"[laifu-think] {parsed['think']}")

        if self.memory:
            await self.memory.store(user_msg, reply)
            if len(self.memory.short_term) >= self.memory.MAX_SHORT_TERM:
                asyncio.create_task(
                    self.memory.compress_and_extract(self._call_single_llm)
                )

        if self.attr_manager:
            deltas = MOOD_SHIFT_DELTAS.get(mood_shift, {})
            if deltas:
                for k, v in deltas.items():
                    if k in self.attr_manager.attrs:
                        self.attr_manager.attrs[k] = _clamp(self.attr_manager.attrs[k] + v)
            self.attr_manager.attrs['affection'] = _clamp(
                self.attr_manager.attrs.get('affection', 50) + 1.5
            )
            self.attr_manager.save()

        return {"reply": reply, "emotion": mood_shift, "action": action}

    # ------------------------------------------------------------------ #
    #  LLM 调用                                                             #
    # ------------------------------------------------------------------ #

    async def _call_llm_with_messages(self, messages: list[dict]) -> str:
        """使用完整消息列表调用 LLM（含历史）"""
        response = await self.llm_client.chat.completions.create(
            model=self.config['llm']['model'],
            messages=messages,
            temperature=0.75,
            max_tokens=300,
        )
        return response.choices[0].message.content

    async def _call_single_llm(self, prompt: str) -> str:
        """单轮调用 LLM，用于摘要/画像提取（无历史上下文）"""
        if not (self.llm_client and self.llm_ready):
            return '{"summary": "", "facts": []}'
        response = await self.llm_client.chat.completions.create(
            model=self.config['llm']['model'],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------ #
    #  工具方法                                                             #
    # ------------------------------------------------------------------ #

    def _parse_action(self, reply: str) -> Optional[str]:
        match = re.search(r'\[action:(\w+)\]', reply)
        return match.group(1) if match else None

    def _fallback_reply(self, user_message: str) -> str:
        import random
        kw_map = {
            "你好": [f"汪！主人好！{self.pet_name}好想你！", "嗷呜~ 主人回来啦！"],
            "吃饭": ["汪！我也饿了！", f"{self.pet_name}也想吃东西~"],
            "玩":   [f"好呀好呀！{self.pet_name}要玩！", "汪！玩什么？"],
            "睡":   [f"Zzz... {self.pet_name}困了...", "汪... 要睡觉了吗？"],
        }
        for kw, responses in kw_map.items():
            if kw in user_message:
                return random.choice(responses)
        return random.choice([
            f"汪？{self.pet_name}在听呢~", "嗷呜？主人说什么？",
            f"{self.pet_name}不太懂，但{self.pet_name}陪着你！", "汪！主人能再说一遍吗？",
        ])

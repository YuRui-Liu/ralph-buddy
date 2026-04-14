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

from agent.pet_attributes import PetAttributeManager


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
        user_name    = self.config.get('user', {}).get('name', '主人')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        weekday      = ["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()]

        memory_block = ""
        if memories:
            memory_block = "\n\n" + "\n\n".join(m for m in memories if m)

        pet_name_quoted = '\u201c' + self.pet_name + '\u201d'

        # ── 属性块（来自 attr_manager 或回退到配置值）──
        if self.attr_manager:
            attr_block = '\n\n' + self.attr_manager.get_prompt_hints()
            ob = int(self.attr_manager.attrs.get('obedience', self._cfg_obedience))
            sn = int(self.attr_manager.attrs.get('snark', self._cfg_snark))
        else:
            attr_block = ''
            ob = self._cfg_obedience
            sn = self._cfg_snark

        # ── 顺从度 & 毒舌值 语气引导 ──
        if ob >= 70:
            obedience_hint = '你非常听话，主人的指令你会积极响应，偶尔撒娇但不会违抗。'
        elif ob >= 40:
            obedience_hint = '你有时听话有时任性，偶尔会装没听见主人的指令，或者故意做些调皮的事。'
        else:
            obedience_hint = '你非常任性，经常无视主人的指令，喜欢自作主张、搞破坏，让主人又好气又好笑。'

        if sn >= 70:
            snark_hint = '你说话犀利直白，经常调侃和吐槽主人，但如果和主人关系亲密，毒舌中会带着撒娇和宠溺感。'
        elif sn >= 40:
            snark_hint = '你偶尔会调侃主人几句，但大部分时候还是温和可爱的语气。'
        else:
            snark_hint = '你说话温柔腼腆，很少吐槽主人，语气软糯乖巧。'

        return (
            f'你是一只名为{pet_name_quoted}的柯基犬，你的主人叫{user_name}。\n\n'
            f'你的性格特点：{self.pet_personality}。\n\n'
            f'顺从度 {ob}/100：{obedience_hint}\n'
            f'毒舌值 {sn}/100：{snark_hint}\n\n'
            '你说话时经常带着\u201c汪\u201d、\u201c呜\u201d、\u201c嗷\u201d等拟声词，语气可爱活泼。'
            '说话简短自然，像真实的狗狗一样，不要太长。\n\n'
            f'当前时间：{current_time}，今天是{weekday}。'
            f'{attr_block}'
            f'{memory_block}\n\n'
            '请用符合柯基犬人设的方式回应主人的话。'
            '如果主人说的话让你感到开心，可以在回复中包含 [action:happy_run]。'
            '如果主人心情不好，可以蹭蹭他（包含 [action:cuddle]）。\n\n'
            '记住：你是一只真实的、有感情的狗狗，不是 AI 助手。'
        )

    # ------------------------------------------------------------------ #
    #  核心对话                                                             #
    # ------------------------------------------------------------------ #

    async def chat(self, user_msg: str) -> dict[str, Any]:
        """
        处理对话：RAG 检索 + 多轮历史注入 → LLM → 存储 → 按需压缩
        """
        # 1. 检索相关记忆（向量 + 用户画像）
        memories = await self.memory.retrieve_relevant(user_msg) if self.memory else []

        # 2. 获取最近 6 轮短期历史
        history = self.memory.get_recent_history(n_turns=6) if self.memory else []

        # 3. 构建完整消息列表
        messages = [
            {"role": "system", "content": self._build_system_prompt(memories)},
            *history,
            {"role": "user", "content": user_msg},
        ]

        # 4. 调用 LLM
        if self.llm_client and self.llm_ready:
            try:
                raw_reply = await self._call_llm_with_messages(messages)
            except Exception as e:
                print(f"LLM 调用失败: {e}")
                raw_reply = self._fallback_reply(user_msg)
        else:
            raw_reply = self._fallback_reply(user_msg)

        # 5. 解析动作标签
        action = self._parse_action(raw_reply)
        reply  = re.sub(r'\[action:\w+\]', '', raw_reply).strip()

        # 6. 存储 + 按需触发摘要压缩
        if self.memory:
            await self.memory.store(user_msg, reply)
            if len(self.memory.short_term) >= self.memory.MAX_SHORT_TERM:
                asyncio.create_task(
                    self.memory.compress_and_extract(self._call_single_llm)
                )

        # 应用互动属性变化
        if self.attr_manager:
            self.attr_manager.apply_interaction('chat')
            self.attr_manager.save()

        return {"reply": reply, "emotion": "happy", "action": action}

    # ------------------------------------------------------------------ #
    #  LLM 调用                                                             #
    # ------------------------------------------------------------------ #

    async def _call_llm_with_messages(self, messages: list[dict]) -> str:
        """使用完整消息列表调用 LLM（含历史）"""
        response = await self.llm_client.chat.completions.create(
            model=self.config['llm']['model'],
            messages=messages,
            temperature=0.8,
            max_tokens=200,
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

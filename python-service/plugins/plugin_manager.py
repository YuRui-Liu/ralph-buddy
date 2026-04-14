"""
插件管理器 — 管理插件会话和 LLM 调用。
与来福对话系统完全隔离，不共享记忆、属性或人设。
"""
import json
from typing import Any, Optional


class PluginManager:

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.sessions: dict[str, list[dict]] = {}

    async def chat(self, plugin_id: str, message: str, session_id: str, llm_config: dict) -> dict[str, Any]:
        model = llm_config.get("model", "deepseek-chat")
        temperature = llm_config.get("temperature", 0.7)
        system_prompt = llm_config.get("system_prompt", "You are a helpful assistant.")

        if session_id not in self.sessions:
            self.sessions[session_id] = []
        history = self.sessions[session_id]

        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": message},
        ]

        response = await self.llm_client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=1000,
        )
        raw_reply = response.choices[0].message.content

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": raw_reply})

        if len(history) > 20:
            self.sessions[session_id] = history[-20:]

        structured = self._try_parse_json(raw_reply)
        return {"reply": raw_reply, "structured": structured}

    def clear_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

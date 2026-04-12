#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DogBuddy 记忆系统 — 重写版
- Chroma PersistentClient（修复重启清空 Bug）
- 数据统一存于 python-service/data/memory/
- 接口签名与旧版保持兼容
"""

import os
import json
import sqlite3
import asyncio
from typing import Optional
from datetime import datetime

# 数据目录（项目内统一管理）
BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'memory')
)
DB_PATH     = os.path.join(BASE_DIR, 'memory.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'chromadb')

# 本地 embedding 模型路径（找不到则用 Chroma 内置默认）
LOCAL_EMBED_MODEL = r'E:\LLM\backbone\embeddings\all-MiniLM-L6-v2'

COMPRESS_BATCH = 12   # 一次压缩的对话条数（6 轮），agent 在 short_term >= MAX_SHORT_TERM 时触发


class MemorySystem:
    """
    记忆系统主类

    短期记忆  : 内存列表 short_term（最近对话，不超过 MAX_SHORT_TERM 由外部触发压缩）
    中期记忆  : Chroma 向量数据库（语义检索，持久化）
    长期记忆  : SQLite user_profile（用户画像）+ events（手动记忆）
    """

    MAX_SHORT_TERM = 20   # 10 轮对话，超过后由 agent 触发压缩

    def __init__(self):
        os.makedirs(BASE_DIR, exist_ok=True)
        self.short_term: list[dict] = []
        self.conn: Optional[sqlite3.Connection] = None
        self.chroma_client = None
        self.collection = None

    # ------------------------------------------------------------------ #
    #  初始化                                                               #
    # ------------------------------------------------------------------ #

    async def initialize(self):
        """初始化 SQLite 和 Chroma（Chroma 失败时降级到纯 SQLite）"""
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        print(f"💾 SQLite: {DB_PATH}")

        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            ef = self._make_embedding_function()
            kwargs = {"embedding_function": ef} if ef else {}
            self.collection = self.chroma_client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"},
                **kwargs,
            )
            print(f"📚 Chroma: {CHROMA_PATH}")
        except Exception as e:
            print(f"⚠️ Chroma 初始化失败，降级到纯 SQLite: {e}")

    def _make_embedding_function(self):
        """构建本地 embedding 函数；找不到模型时返回 None（Chroma 用默认）"""
        try:
            from sentence_transformers import SentenceTransformer
            from chromadb import EmbeddingFunction

            class _LocalEF(EmbeddingFunction):
                def __init__(self, path):
                    self._path = path
                    self._model = None

                def __call__(self, input: list[str]) -> list[list[float]]:
                    if self._model is None:
                        self._model = SentenceTransformer(self._path)
                    return self._model.encode(input).tolist()

            if os.path.exists(LOCAL_EMBED_MODEL):
                return _LocalEF(LOCAL_EMBED_MODEL)
        except ImportError:
            pass
        return None

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT,
                content    TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_summary INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT,
                importance INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    # ------------------------------------------------------------------ #
    #  短期记忆                                                             #
    # ------------------------------------------------------------------ #

    def get_recent_history(self, n_turns: int = 6) -> list[dict]:
        """返回最近 n_turns 轮（n_turns*2 条）消息，注入 LLM"""
        return self.short_term[-(n_turns * 2):]

    # ------------------------------------------------------------------ #
    #  存储                                                                 #
    # ------------------------------------------------------------------ #

    async def store(self, user_msg: str, ai_msg: str):
        """存储一轮对话到短期记忆、SQLite 和向量库（向量库后台写入）"""
        self.short_term.append({"role": "user",      "content": user_msg})
        self.short_term.append({"role": "assistant", "content": ai_msg})

        c = self.conn.cursor()
        c.execute("INSERT INTO conversations (role, content) VALUES (?, ?)", ("user",      user_msg))
        c.execute("INSERT INTO conversations (role, content) VALUES (?, ?)", ("assistant", ai_msg))
        self.conn.commit()

        if self.collection:
            asyncio.create_task(self._embed_and_store(user_msg, ai_msg))

    async def _embed_and_store(self, user_msg: str, ai_msg: str):
        doc_id  = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        content = f"用户: {user_msg}\n来福: {ai_msg}"
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[{"date": datetime.now().isoformat(), "type": "conversation"}],
            )
        except Exception as e:
            print(f"⚠️ 向量存储失败: {e}")

    # ------------------------------------------------------------------ #
    #  检索                                                                 #
    # ------------------------------------------------------------------ #

    async def retrieve_relevant(self, query: str, top_k: int = 3) -> list[str]:
        """向量检索相关对话片段 + 用户画像，返回供 LLM 使用的文本列表"""
        results: list[str] = []

        if self.collection:
            try:
                count = self.collection.count()
                if count > 0:
                    actual_k = min(top_k, count)
                    hits = self.collection.query(query_texts=[query], n_results=actual_k)
                    if hits.get("documents"):
                        results.extend(hits["documents"][0])
            except Exception as e:
                print(f"⚠️ 向量检索失败: {e}")

        profile = self._format_profile()
        if profile:
            results.append(profile)

        return results

    def _format_profile(self) -> str:
        c = self.conn.cursor()
        c.execute("SELECT key, value FROM user_profile ORDER BY updated_at DESC LIMIT 20")
        rows = c.fetchall()
        if not rows:
            return ""
        facts = "\n".join(f"- {r['key']}: {r['value']}" for r in rows)
        return f"关于主人你记得：\n{facts}"

    # ------------------------------------------------------------------ #
    #  摘要压缩 + 用户画像提取（由 agent 在对话轮数达阈值时触发）              #
    # ------------------------------------------------------------------ #

    async def compress_and_extract(self, llm_caller):
        """
        取最旧 12 条短期记忆（6 轮），单次 LLM 调用完成：
          1. 生成对话摘要 → 存 SQLite conversations (is_summary=1)
          2. 提取用户画像事实 → upsert SQLite user_profile
          3. 摘要向量化 → Chroma（后台）

        llm_caller: async (prompt: str) -> str
        """
        if len(self.short_term) < COMPRESS_BATCH:
            return

        to_compress     = self.short_term[:COMPRESS_BATCH]
        self.short_term = self.short_term[COMPRESS_BATCH:]

        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '来福'}: {m['content']}"
            for m in to_compress
        )

        prompt = (
            "请对以下对话做两件事，返回纯 JSON（不要包含 markdown 代码块）：\n"
            "1. summary: 用2-3句话概括对话内容\n"
            "2. facts: 提取用户关键信息（姓名、爱好、情绪、重要事件等，key用中文）\n\n"
            f"对话内容：\n{conv_text}\n\n"
            '返回格式：{"summary": "...", "facts": [{"key": "...", "value": "..."}]}'
        )

        try:
            raw  = await llm_caller(prompt)
            raw  = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)

            summary = data.get("summary", "")
            facts   = data.get("facts", [])

            c = self.conn.cursor()
            c.execute(
                "INSERT INTO conversations (role, content, is_summary) VALUES (?, ?, 1)",
                ("summary", summary),
            )
            for fact in facts:
                if fact.get("key") and fact.get("value"):
                    c.execute(
                        """INSERT INTO user_profile (key, value, updated_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(key) DO UPDATE SET
                               value=excluded.value,
                               updated_at=excluded.updated_at""",
                        (fact["key"], fact["value"], datetime.now().isoformat()),
                    )
            self.conn.commit()

            if self.collection and summary:
                asyncio.create_task(self._embed_summary(summary))

            print(f"✅ 记忆压缩完成，提取 {len(facts)} 条画像")
        except Exception as e:
            print(f"⚠️ 记忆压缩失败: {e}")
            self.short_term = to_compress + self.short_term   # 回滚

    async def _embed_summary(self, summary: str):
        doc_id = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[summary],
                metadatas=[{"date": datetime.now().isoformat(), "type": "summary"}],
            )
        except Exception as e:
            print(f"⚠️ 摘要向量化失败: {e}")

    # ------------------------------------------------------------------ #
    #  重要记忆（events）                                                   #
    # ------------------------------------------------------------------ #

    async def add_manual_memory(self, content: str, importance: int = 3):
        c = self.conn.cursor()
        c.execute("INSERT INTO events (content, importance) VALUES (?, ?)", (content, importance))
        self.conn.commit()

        if self.collection:
            doc_id = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            try:
                self.collection.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[{"type": "event", "importance": str(importance)}],
                )
            except Exception as e:
                print(f"⚠️ 事件向量化失败: {e}")

    async def list_events(self) -> list[dict]:
        """列出所有手动添加的重要记忆（供 UI 展示）"""
        c = self.conn.cursor()
        c.execute(
            "SELECT id, content, importance, created_at FROM events ORDER BY created_at DESC"
        )
        return [
            {
                "id":         r["id"],
                "content":    r["content"],
                "importance": r["importance"],
                "created_at": r["created_at"],
            }
            for r in c.fetchall()
        ]

    async def delete_event(self, event_id: int) -> bool:
        """删除单条重要记忆，返回是否成功"""
        c = self.conn.cursor()
        c.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self.conn.commit()
        return c.rowcount > 0

    # ------------------------------------------------------------------ #
    #  用户画像                                                             #
    # ------------------------------------------------------------------ #

    async def get_user_profile(self) -> dict:
        c = self.conn.cursor()
        c.execute("SELECT key, value FROM user_profile")
        profile = {r["key"]: r["value"] for r in c.fetchall()}
        c.execute("SELECT COUNT(*) as cnt FROM conversations WHERE is_summary = 0")
        profile["total_conversations"] = c.fetchone()["cnt"] // 2
        return profile

    async def update_user_profile(self, key: str, value: str):
        c = self.conn.cursor()
        c.execute(
            """INSERT INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, datetime.now().isoformat()),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    #  搜索 / 清除                                                          #
    # ------------------------------------------------------------------ #

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        c = self.conn.cursor()
        c.execute(
            """SELECT id, content, importance, created_at FROM events
               WHERE content LIKE ?
               ORDER BY importance DESC, created_at DESC LIMIT ?""",
            (f"%{query}%", top_k),
        )
        return [
            {"type": "event", "content": r["content"],
             "importance": r["importance"], "date": r["created_at"]}
            for r in c.fetchall()
        ]

    async def clear_all(self):
        self.conn.executescript(
            "DELETE FROM conversations; DELETE FROM events; DELETE FROM user_profile;"
        )
        self.conn.commit()

        if self.chroma_client:
            try:
                self.chroma_client.delete_collection("conversations")
                ef = self._make_embedding_function()
                kwargs = {"embedding_function": ef} if ef else {}
                self.collection = self.chroma_client.get_or_create_collection(
                    name="conversations",
                    metadata={"hnsw:space": "cosine"},
                    **kwargs,
                )
            except Exception as e:
                print(f"⚠️ 清空向量库失败: {e}")

        self.short_term = []
        print("✅ 所有记忆已清除")

    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # ------------------------------------------------------------------ #
    #  旧接口兼容（main.py 中直接调用的方法）                                #
    # ------------------------------------------------------------------ #

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """兼容旧接口，内部调用 retrieve_relevant"""
        return await self.retrieve_relevant(query, top_k)

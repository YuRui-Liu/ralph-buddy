# M3-A 记忆系统实现设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 补全长期记忆系统并新增记忆管理 UI，让来福真正"记住"主人，对话体验质的提升。

**Architecture:** 重写 `memory_system.py`（接口不变），修复 Chroma 非持久化 Bug，实现 LLM 驱动的对话摘要 + 用户画像提取；改造 `dog_agent.py` 注入 RAG 检索结果和最近 6 轮历史；新增前端 `MemoryPanel.vue` 浮动面板通过右键菜单访问。

**Tech Stack:** Python FastAPI · ChromaDB PersistentClient · sentence-transformers · SQLite · Vue 3 Composition API · Pinia

---

## 一、当前状态评估

| 文件 | 问题 |
|------|------|
| `memory_system.py` | Chroma 使用内存模式（重启清空）；`_compress_to_summary()` 是占位代码；用户画像无自动提取 |
| `dog_agent.py` | `_call_llm()` 只传单轮消息，无历史注入；RAG 结果未真正用于 LLM |
| 前端 | 无记忆管理 UI；右键菜单无入口 |

---

## 二、文件结构

### 修改文件
- `python-service/memory/memory_system.py` — 核心重写，接口签名不变
- `python-service/agent/dog_agent.py` — 注入多轮历史 + RAG 上下文
- `python-service/main.py` — 新增 `/api/memory/events` 和 `DELETE /api/memory/events/:id` 端点
- `electron/main.js` — 右键菜单增加"记忆管理"入口
- `electron/preload.js` — 暴露 `onOpenMemory` IPC 监听
- `renderer/src/App.vue` — 注册 MemoryPanel 显示逻辑
- `renderer/src/stores/ui.js` — 新增 `showMemoryPanel` 状态

### 新增文件
- `renderer/src/components/MemoryPanel.vue` — 记忆管理浮动面板

### 数据目录（统一在项目内）
- `python-service/data/memory/memory.db` — SQLite
- `python-service/data/memory/chromadb/` — Chroma 持久化目录

---

## 三、后端设计

### 3.1 memory_system.py 重写

**初始化（修复 Chroma 持久化）**

```python
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'memory')
DB_PATH  = os.path.join(BASE_DIR, 'memory.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'chromadb')

# 持久化（修复 Bug）
self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
self.collection = self.chroma_client.get_or_create_collection(
    name="conversations",
    metadata={"hnsw:space": "cosine"},
    embedding_function=LocalEmbeddingFunction(model_path)
)
```

**短期记忆管理**

```python
# 短期记忆：最近 20 条（10 轮对话）
self.short_term: list[dict] = []
self.MAX_SHORT_TERM = 20

def get_recent_history(self, n_turns: int = 6) -> list[dict]:
    """返回最近 n 轮（n_turns*2 条）消息，用于注入 LLM"""
    return self.short_term[-(n_turns * 2):]
```

**摘要 + 画像提取（C 方案：合并为单次 LLM 调用）**

当 `short_term` 超过 `MAX_SHORT_TERM` 时，取最旧的 12 条（6 轮）调用 LLM：

```python
COMPRESS_PROMPT = """请对以下对话做两件事，返回 JSON：
1. summary: 用2-3句话概括对话内容
2. facts: 从对话中提取用户关键信息（姓名、爱好、情绪、重要事件等）

返回格式：{"summary": "...", "facts": [{"key": "...", "value": "..."}]}

对话内容：
{conversation}"""
```

提取结果处理：
- `summary` → 写入 `conversations` 表（`is_summary=1`）
- `facts` → upsert `user_profile` 表（`key/value`）
- 同时将摘要文本向量化存入 Chroma

**retrieve_relevant()**

```python
async def retrieve_relevant(self, query: str, top_k: int = 3) -> list[str]:
    results = []
    
    # 1. 向量检索相关对话片段
    if self.collection:
        hits = self.collection.query(query_texts=[query], n_results=top_k)
        results.extend(hits['documents'][0] if hits['documents'] else [])
    
    # 2. 追加格式化的用户画像
    profile_str = self._format_profile()
    if profile_str:
        results.append(profile_str)
    
    return results

def _format_profile(self) -> str:
    """将 user_profile 格式化为 LLM 可读文本"""
    cursor = self.conn.cursor()
    cursor.execute("SELECT key, value FROM user_profile ORDER BY updated_at DESC LIMIT 20")
    rows = cursor.fetchall()
    if not rows:
        return ""
    facts = "\n".join(f"- {r['key']}: {r['value']}" for r in rows)
    return f"关于主人你记得：\n{facts}"
```

**新增接口方法**

```python
async def list_events(self) -> list[dict]:
    """列出所有手动添加的重要记忆（用于 UI 展示）"""

async def delete_event(self, event_id: int) -> bool:
    """删除单条重要记忆"""
```

### 3.2 dog_agent.py 改动

**chat() 注入历史 + 记忆**

```python
async def chat(self, user_msg: str) -> dict:
    # 1. 检索相关记忆
    memories = await self.memory.retrieve_relevant(user_msg) if self.memory else []
    
    # 2. 获取短期历史（最近 6 轮）
    history = self.memory.get_recent_history(n_turns=6) if self.memory else []
    
    # 3. 构建消息列表
    system_prompt = self._build_system_prompt(memories)
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_msg}
    ]
    
    # 4. 调用 LLM（支持完整 messages）
    reply = await self._call_llm_with_messages(messages)
    
    # 5. 存储 + 异步压缩
    if self.memory:
        await self.memory.store(user_msg, reply)
        if len(self.memory.short_term) >= self.memory.MAX_SHORT_TERM:
            asyncio.create_task(
                self.memory.compress_and_extract(self._call_single_llm)
            )
    
    return {"reply": reply, "emotion": "happy", "action": self._parse_action(reply)}
```

**新增 `_call_llm_with_messages()`**（支持完整 messages 列表，替代旧的单轮调用）

**新增 `_call_single_llm(prompt, context_msgs)`**（专用于摘要/画像提取，不含历史）

### 3.3 main.py 新增端点

```python
@app.get("/api/memory/events")
async def list_memory_events():
    """列出所有手动添加的重要记忆"""
    events = await memory.list_events()
    return {"events": events}

@app.delete("/api/memory/events/{event_id}")
async def delete_memory_event(event_id: int):
    """删除单条重要记忆"""
    success = await memory.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"status": "success"}
```

---

## 四、前端设计

### 4.1 MemoryPanel.vue

浮动面板，风格与 `VoiceManager.vue` 一致（绝对定位、毛玻璃背景）。

**布局区域：**
1. **用户画像区** — 展示 `GET /api/memory/summary` 中 `user_profile` 字段
2. **重要记忆区** — 列表展示 `GET /api/memory/events`，每条可点 🗑 删除
3. **添加记忆** — 文本输入 + 确认按钮 → `POST /api/memory/add`
4. **搜索记忆** — 搜索框 → `GET /api/memory/search?query=` → 结果列表
5. **危险区** — "清除全部记忆"确认按钮 → `DELETE /api/memory/clear`

**状态：**
```js
const profile = ref({})          // 用户画像
const events = ref([])           // 重要记忆列表
const searchQuery = ref('')      // 搜索关键词
const searchResults = ref([])    // 搜索结果
const newMemoryText = ref('')    // 新增记忆输入
const isLoading = ref(false)
```

### 4.2 ui.js 新增状态

```js
const showMemoryPanel = ref(false)
function openMemoryPanel() { showMemoryPanel.value = true }
function closeMemoryPanel() { showMemoryPanel.value = false }
```

### 4.3 IPC 链路

```
electron/main.js
  contextMenu → "🧠 记忆管理" → mainWindow.webContents.send('open-memory')

electron/preload.js
  onOpenMemory: (cb) => ipcRenderer.on('open-memory', cb)

renderer/src/App.vue
  window.electronAPI.onOpenMemory(() => uiStore.openMemoryPanel())
  <MemoryPanel v-if="uiStore.showMemoryPanel" />
```

---

## 五、错误处理

| 场景 | 处理方式 |
|------|---------|
| Chroma 初始化失败 | 降级到纯 SQLite 模式，不影响对话 |
| LLM 摘要/画像提取失败 | 静默失败，短期记忆仍保留，不阻塞对话 |
| 向量检索失败 | 跳过，仅注入用户画像文本 |
| 前端 API 请求失败 | 面板内显示错误提示，不影响主窗口 |

---

## 六、不在本次范围内

- 记忆导出/导入（T9.4、T9.5 — P2，M3-B 后考虑）
- 插件系统（M3-B 单独设计）
- 口型同步（M2 遗留，独立任务）

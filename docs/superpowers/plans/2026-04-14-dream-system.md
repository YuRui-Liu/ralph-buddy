# 做梦系统完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 来福睡觉时做梦，梦境通过 AI 绘图可视化，醒来后用专属云朵气泡展示，所有梦境存入可浏览的梦境日记。

**Architecture:** 后端 dream_engine 增加 image_prompt 输出 + 新建 DreamImageGenerator 调用硅基流动绘图 API。前端重写睡眠/做梦/醒来流程（usePetAttributeTicker），新建 DreamBubble 和 DreamDiary 组件。

**Tech Stack:** SiliconFlow Images API (FLUX.1-schnell), Vue 3 组件, FastAPI 静态文件路由

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `python-service/dream/__init__.py` | Package init |
| `python-service/dream/image_generator.py` | DreamImageGenerator: 硅基流动绘图 API 封装 |
| `renderer/src/components/DreamBubble.vue` | 梦境气泡（云朵样式 + 图片 + 文字） |
| `renderer/src/components/DreamDiary.vue` | 梦境日记面板（卡片列表） |

### Modified Files
| File | Changes |
|------|---------|
| `python-service/config.json` | 新增 `image` 配置块 |
| `python-service/agent/dream_engine.py` | LLM prompt 增加 image_prompt，存储格式改为 JSON |
| `python-service/main.py` | 新增 3 个 dream API 端点 + 返回 image_prompt |
| `renderer/src/composables/useBehaviorSequencer.js` | 修复 bedtime 脚本 + 新增 wakeup 脚本 |
| `renderer/src/composables/usePetAttributeTicker.js` | 重写睡眠/做梦/醒来逻辑 |
| `renderer/src/stores/pet.js` | 新增 dreamResult / showDreamBubble |
| `renderer/src/stores/ui.js` | 新增 showDreamDiary |
| `renderer/src/App.vue` | 挂载 DreamBubble + DreamDiary |
| `electron/main.js` | 右键菜单新增"梦境日记" |

---

### Task 1: DreamImageGenerator — 硅基流动绘图 API

**Files:**
- Create: `python-service/dream/__init__.py`
- Create: `python-service/dream/image_generator.py`
- Modify: `python-service/config.json`

- [ ] **Step 1: 添加 image 配置到 config.json**

在 `python-service/config.json` 的 `stt` 块之后添加 `image` 块：

```json
{
  "llm": { ... },
  "user": { ... },
  "pet": { ... },
  "tts": { ... },
  "stt": { ... },
  "image": {
    "provider": "siliconflow",
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "sk-xxx",
    "model": "black-forest-labs/FLUX.1-schnell"
  }
}
```

- [ ] **Step 2: 创建 dream 包**

创建空文件 `python-service/dream/__init__.py`。

- [ ] **Step 3: 创建 DreamImageGenerator**

创建 `python-service/dream/image_generator.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamImageGenerator — 梦境图片生成器
调用硅基流动 (SiliconFlow) Images API 生成梦境可视化图片。
"""

import os
import base64
import httpx
from datetime import datetime
from typing import Optional

DREAMS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'dreams')
)


class DreamImageGenerator:

    def __init__(self, config: dict):
        """
        Args:
            config: config.json 中的 image 配置块
                    { "base_url": "...", "api_key": "...", "model": "..." }
        """
        self.base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "black-forest-labs/FLUX.1-schnell")
        os.makedirs(DREAMS_DIR, exist_ok=True)

    async def generate(self, prompt: str) -> Optional[dict]:
        """
        生成梦境图片。

        Args:
            prompt: 英文绘图提示词

        Returns:
            {"image_path": "data/dreams/20260414-195200.png", "image_base64": "..."}
            失败返回 None
        """
        if not self.api_key or self.api_key == "sk-xxx":
            print("[DreamImage] 未配置 image.api_key，跳过图片生成")
            return None

        url = f"{self.base_url.rstrip('/')}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "prompt": prompt,
            "image_size": "512x512",
            "batch_size": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # 解析返回（兼容 OpenAI 和 SiliconFlow 格式）
            images = data.get("images") or data.get("data") or []
            if not images:
                print(f"[DreamImage] API 返回无图片: {data}")
                return None

            img_item = images[0]
            # SiliconFlow 返回 url 字段（base64 data URI 或 HTTP URL）
            img_url = img_item.get("url") or img_item.get("b64_json") or ""

            if img_url.startswith("data:"):
                # data:image/png;base64,xxx
                b64_data = img_url.split(",", 1)[1] if "," in img_url else img_url
                img_bytes = base64.b64decode(b64_data)
            elif img_url.startswith("http"):
                # HTTP URL，需要下载
                async with httpx.AsyncClient(timeout=30) as client:
                    dl = await client.get(img_url)
                    dl.raise_for_status()
                    img_bytes = dl.content
                b64_data = base64.b64encode(img_bytes).decode()
            elif img_item.get("b64_json"):
                b64_data = img_item["b64_json"]
                img_bytes = base64.b64decode(b64_data)
            else:
                print(f"[DreamImage] 无法解析图片格式: {img_item.keys()}")
                return None

            # 保存到文件
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}.png"
            filepath = os.path.join(DREAMS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)

            print(f"[DreamImage] 已保存: {filepath} ({len(img_bytes)} bytes)")
            return {
                "image_path": f"data/dreams/{filename}",
                "image_base64": b64_data,
            }

        except Exception as e:
            print(f"[DreamImage] 图片生成失败: {e}")
            return None
```

- [ ] **Step 4: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/dream/ python-service/config.json
git commit -m "feat(dream): add DreamImageGenerator with SiliconFlow API"
```

---

### Task 2: dream_engine 增加 image_prompt + 存储格式变更

**Files:**
- Modify: `python-service/agent/dream_engine.py`

- [ ] **Step 1: 修改 LLM prompt 增加 image_prompt 字段**

在 `python-service/agent/dream_engine.py` 的 `_build_dream_prompt` 方法中，将 JSON 格式说明部分改为：

```python
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
            '  "dream_text": "（简短描述来福梦到了什么，用第三人称，2-3句话）",\n'
            '  "image_prompt": "（英文，用于AI绘图的提示词，描述梦境画面，'
            '加上 dreamy watercolor style, soft lighting, cute corgi）",\n'
            '  "profile_updates": [{"key": "...", "value": "..."}],\n'
            '  "attribute_deltas": {"mood": 0, "affection": 0, "energy": 0, '
            '"health": 0, "obedience": 0, "snark": 0},\n'
            '  "reasoning": "（为什么生成这个梦境）"\n'
            '}'
        )
```

- [ ] **Step 2: 修改 dream() 方法 — 解析 image_prompt + 新存储格式**

在 `dream_engine.py` 的 `dream()` 方法中，在 `reasoning = data.get("reasoning", "")` 之后添加：

```python
        image_prompt    = data.get("image_prompt", "")
```

修改步骤 7（写入 events 表），将原来的：

```python
        # 7. 将梦境写入 events 表
        if conn and dream_text:
            c = conn.cursor()
            c.execute(
                "INSERT INTO events (content, importance, created_at) VALUES (?, ?, ?)",
                (f"【做梦】{dream_text}", 3, now.isoformat()),
            )
            conn.commit()
```

改为：

```python
        # 7. 将梦境写入 events 表（JSON 格式，兼容日记查询）
        if conn and dream_text:
            dream_record = json.dumps({
                "type": "dream",
                "text": dream_text,
                "image_prompt": image_prompt,
                "image_path": None,  # 由调用方填充
                "attribute_deltas": attribute_deltas,
            }, ensure_ascii=False)
            c = conn.cursor()
            c.execute(
                "INSERT INTO events (content, importance, created_at) VALUES (?, ?, ?)",
                (dream_record, 3, now.isoformat()),
            )
            conn.commit()
            self._last_event_id = c.lastrowid
```

在 `__init__` 方法末尾添加：

```python
        self._last_event_id: Optional[int] = None
```

修改返回结果，加入 image_prompt 和 event_id：

```python
        result = {
            "dream_text":       dream_text,
            "image_prompt":     image_prompt,
            "profile_updates":  profile_updates,
            "attribute_deltas": attribute_deltas,
            "reasoning":        reasoning,
            "event_id":         self._last_event_id,
        }
```

- [ ] **Step 3: 添加 update_dream_image 方法**

在 `dream_engine.py` 的 class 中添加方法：

```python
    def update_dream_image(self, event_id: int, image_path: str) -> None:
        """将生成的梦境图片路径回写到 events 表记录中。"""
        conn = self.memory.conn
        if not conn or not event_id:
            return
        try:
            c = conn.cursor()
            row = c.execute("SELECT content FROM events WHERE id=?", (event_id,)).fetchone()
            if row:
                data = json.loads(row[0])
                data["image_path"] = image_path
                c.execute(
                    "UPDATE events SET content=? WHERE id=?",
                    (json.dumps(data, ensure_ascii=False), event_id),
                )
                conn.commit()
        except Exception as e:
            print(f"[DreamEngine] 更新梦境图片路径失败: {e}")
```

- [ ] **Step 4: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/agent/dream_engine.py
git commit -m "feat(dream): add image_prompt to dream output, JSON storage format"
```

---

### Task 3: 后端 API — dream/image + dream/history + 图片路由

**Files:**
- Modify: `python-service/main.py`

- [ ] **Step 1: 在 lifespan 中初始化 DreamImageGenerator**

在 `python-service/main.py` 的 import 区域添加：

```python
from dream.image_generator import DreamImageGenerator
```

在全局变量区域添加：

```python
dream_image_gen: Optional[DreamImageGenerator] = None
```

在 lifespan 函数中，`dream_engine = DreamEngine(...)` 之后添加：

```python
    # 梦境图片生成器
    img_cfg = agent.config.get("image", {})
    if img_cfg.get("api_key"):
        dream_image_gen = DreamImageGenerator(img_cfg)
        print(f"🎨 梦境绘图: {img_cfg.get('provider', 'siliconflow')} / {img_cfg.get('model', 'FLUX')}")
    else:
        print("🎨 梦境绘图: 未配置 (跳过图片生成)")
```

在 lifespan 的 `global` 声明中追加 `dream_image_gen`。

- [ ] **Step 2: 修改 /api/pet/dream 端点返回 image_prompt**

修改现有的 `trigger_dream` 函数返回值：

```python
@app.post("/api/pet/dream")
async def trigger_dream():
    """触发做梦（来福进入 sleep 状态时前端调用）"""
    if not dream_engine:
        raise HTTPException(status_code=503, detail="做梦引擎未初始化")
    if not dream_engine.can_dream():
        return {"status": "cooldown", "message": "做梦冷却中"}

    result = await dream_engine.dream()
    if result is None:
        raise HTTPException(status_code=500, detail="做梦失败")

    return {
        "status": "success",
        "dream_text": result["dream_text"],
        "image_prompt": result.get("image_prompt", ""),
        "attribute_deltas": result["attribute_deltas"],
        "attributes": attr_manager.get_all(),
        "event_id": result.get("event_id"),
    }
```

- [ ] **Step 3: 添加 POST /api/dream/image 端点**

在 `/api/pet/dream` 端点之后添加：

```python
@app.post("/api/dream/image")
async def generate_dream_image(request: Request):
    """
    生成梦境图片

    Body JSON: { "prompt": "...", "event_id": 123 }
    """
    if not dream_image_gen:
        raise HTTPException(status_code=503, detail="梦境绘图未配置")

    body = await request.json()
    prompt = body.get("prompt", "")
    event_id = body.get("event_id")

    if not prompt:
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    result = await dream_image_gen.generate(prompt)
    if result is None:
        return {"status": "failed", "image_path": None}

    # 回写图片路径到 events 表
    if event_id and dream_engine:
        dream_engine.update_dream_image(event_id, result["image_path"])

    return {
        "status": "success",
        "image_path": result["image_path"],
        "image_base64": result["image_base64"],
    }
```

- [ ] **Step 4: 添加 GET /api/dream/history 端点**

```python
@app.get("/api/dream/history")
async def get_dream_history():
    """获取梦境日记列表"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")

    conn = memory.conn
    rows = conn.execute(
        "SELECT id, content, importance, created_at FROM events ORDER BY created_at DESC"
    ).fetchall()

    dreams = []
    for row in rows:
        eid, content, importance, created_at = row
        # 兼容新 JSON 格式和旧 "【做梦】" 前缀格式
        try:
            data = json.loads(content)
            if data.get("type") != "dream":
                continue
            dreams.append({
                "id": eid,
                "text": data.get("text", ""),
                "image_path": data.get("image_path"),
                "attribute_deltas": data.get("attribute_deltas", {}),
                "created_at": created_at,
            })
        except (json.JSONDecodeError, TypeError):
            if content.startswith("【做梦】"):
                dreams.append({
                    "id": eid,
                    "text": content.replace("【做梦】", "", 1),
                    "image_path": None,
                    "attribute_deltas": {},
                    "created_at": created_at,
                })

    return {"dreams": dreams}
```

- [ ] **Step 5: 添加梦境图片静态文件路由**

```python
from fastapi.responses import FileResponse

@app.get("/api/dream/image/{filename}")
async def serve_dream_image(filename: str):
    """提供梦境图片文件访问"""
    filepath = os.path.join(os.path.dirname(__file__), "data", "dreams", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath, media_type="image/png")
```

- [ ] **Step 6: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/main.py
git commit -m "feat(dream): add dream/image, dream/history API endpoints"
```

---

### Task 4: 修复 bedtime 脚本 + 新增 wakeup 脚本

**Files:**
- Modify: `renderer/src/composables/useBehaviorSequencer.js`

- [ ] **Step 1: 修复 bedtime 脚本末尾**

在 `renderer/src/composables/useBehaviorSequencer.js` 中，将 bedtime 脚本的 steps 改为：

```javascript
  bedtime: {
    id: 'bedtime',
    label: '睡前仪式',
    cooldown: 3600000,
    weight: 10,
    trigger: { timeRange: [22, 6], idleMinMs: 600000 },
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'bubble', text: '好困……' },
      { type: 'wait',  duration: 2000 },
      { type: 'pose',  value: 'sleep',      duration: 800 },
      { type: 'prop',  value: 'zzzs',       op: 'add' },
      { type: 'bubble', text: '（呼呼……）' },
      { type: 'wait',  duration: 3000 },
      // 保持 sleep 姿态 + zzzs，由醒来流程统一清理
    ],
  },
```

关键变化：移除末尾的 `{ type: 'prop', value: 'zzzs', op: 'remove' }`，缩短 wait 从 8000 到 3000（进入睡眠后由 ticker 接管）。

- [ ] **Step 2: 添加 wakeup 脚本**

在 bedtime 之后（情绪观察脚本之前）添加：

```javascript
  // 醒来动画（由 usePetAttributeTicker 调用，不参与随机触发）
  wakeup: {
    id: 'wakeup',
    label: '醒来',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'prop',  value: 'zzzs',       op: 'remove' },
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'wait',  duration: 800 },
      { type: 'pose',  value: 'bark',       duration: 300 },
      { type: 'wait',  duration: 500 },
      { type: 'pose',  value: 'idle' },
    ],
  },
```

- [ ] **Step 3: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/composables/useBehaviorSequencer.js
git commit -m "fix(dream): fix bedtime to stay in sleep, add wakeup script"
```

---

### Task 5: petStore + uiStore 扩展

**Files:**
- Modify: `renderer/src/stores/pet.js`
- Modify: `renderer/src/stores/ui.js`

- [ ] **Step 1: petStore 添加梦境状态**

在 `renderer/src/stores/pet.js` 中，在 `emotionObserver` ref 之后添加：

```javascript
  // 梦境状态
  const dreamResult = ref(null)       // { text, imageSrc, attributeDeltas }
  const showDreamBubble = ref(false)
```

在 return 对象中追加：

```javascript
    dreamResult,
    showDreamBubble,
```

- [ ] **Step 2: uiStore 添加梦境日记状态**

在 `renderer/src/stores/ui.js` 中，在 `showAttributesPanel` ref 之后添加：

```javascript
  const showDreamDiary = ref(false)
```

添加方法：

```javascript
  function openDreamDiary() {
    showDreamDiary.value = true
  }

  function closeDreamDiary() {
    showDreamDiary.value = false
  }
```

在 return 对象中追加：

```javascript
    showDreamDiary,
    openDreamDiary,
    closeDreamDiary,
```

- [ ] **Step 3: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/stores/pet.js renderer/src/stores/ui.js
git commit -m "feat(dream): add dreamResult/showDreamBubble to petStore, showDreamDiary to uiStore"
```

---

### Task 6: 重写 usePetAttributeTicker — 睡眠/做梦/醒来流程

**Files:**
- Modify: `renderer/src/composables/usePetAttributeTicker.js`

- [ ] **Step 1: 重写完整文件**

替换 `renderer/src/composables/usePetAttributeTicker.js` 全部内容为：

```javascript
/**
 * usePetAttributeTicker — 宠物属性定时同步 + 睡眠/做梦/醒来流程
 */
import { watch } from 'vue'
import { usePetStore } from '../stores/pet'
import { useChatStore } from '../stores/chat'

const TICK_INTERVAL = 10 * 60 * 1000  // 10 minutes
const DREAM_DELAY = 30 * 1000         // 进入睡眠 30 秒后触发做梦
const MAX_SLEEP = 5 * 60 * 1000       // 最长睡眠 5 分钟
const API_BASE = 'http://127.0.0.1'

let tickTimer = null
let sleepDreamTimer = null
let sleepMaxTimer = null
let port = 18765
let behaviorSequencer = null  // 由外部注入

async function getPort() {
  if (window.electronAPI) {
    port = await window.electronAPI.getPythonPort()
  }
  return port
}

async function fetchAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes`)
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性拉取失败:', e)
  }
}

async function tickAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes/tick`, { method: 'POST' })
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性 tick 失败:', e)
  }
}

// ── 做梦 + 图片生成 ──

async function tryDream(petStore) {
  try {
    const p = await getPort()

    // Step 1: 触发做梦
    const res = await fetch(`${API_BASE}:${p}/api/pet/dream`, { method: 'POST' })
    if (!res.ok) return
    const data = await res.json()
    if (data.status !== 'success' || !data.dream_text) return

    if (data.attributes) petStore.applyAttributes(data.attributes)

    // 暂存梦境文字结果
    const dreamData = {
      text: data.dream_text,
      imageSrc: null,
      attributeDeltas: data.attribute_deltas || {},
    }

    // Step 2: 生成梦境图片（不阻塞，失败也无所谓）
    if (data.image_prompt) {
      try {
        const imgRes = await fetch(`${API_BASE}:${p}/api/dream/image`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: data.image_prompt,
            event_id: data.event_id,
          }),
        })
        if (imgRes.ok) {
          const imgData = await imgRes.json()
          if (imgData.status === 'success' && imgData.image_base64) {
            dreamData.imageSrc = `data:image/png;base64,${imgData.image_base64}`
          }
        }
      } catch (e) {
        console.warn('[Dream] 图片生成失败:', e)
      }
    }

    // 暂存结果，醒来时展示
    petStore.dreamResult = dreamData
    console.log('[Dream] 梦境已生成，等待醒来展示')

  } catch (e) {
    console.warn('做梦请求失败:', e)
  }
}

// ── 醒来流程 ──

function wakeUp(petStore) {
  // 清理定时器
  if (sleepDreamTimer) { clearTimeout(sleepDreamTimer); sleepDreamTimer = null }
  if (sleepMaxTimer) { clearTimeout(sleepMaxTimer); sleepMaxTimer = null }

  // 播放醒来动画
  if (behaviorSequencer) {
    behaviorSequencer.trigger('wakeup')
  } else {
    petStore.setState('idle')
  }

  // 醒来后展示梦境气泡（延迟 2.5 秒，等 wakeup 动画播完）
  if (petStore.dreamResult) {
    setTimeout(() => {
      petStore.showDreamBubble = true
    }, 2500)
  }
}

// ── 进入睡眠 ──

function onSleepStart(petStore) {
  console.log('[Sleep] 进入睡眠')

  // 30 秒后做梦
  sleepDreamTimer = setTimeout(() => {
    tryDream(petStore)
  }, DREAM_DELAY)

  // 最长 5 分钟后自动醒来
  sleepMaxTimer = setTimeout(() => {
    console.log('[Sleep] 最长睡眠时间到，自动醒来')
    wakeUp(petStore)
  }, MAX_SLEEP)
}

function onSleepEnd(petStore) {
  console.log('[Sleep] 离开睡眠')
  // 如果是被外部唤醒（点击/互动），执行醒来流程
  wakeUp(petStore)
}

export function usePetAttributeTicker() {
  const petStore = usePetStore()
  const chatStore = useChatStore()

  function init() {
    fetchAttributes(petStore)
    tickTimer = setInterval(() => tickAttributes(petStore), TICK_INTERVAL)

    watch(() => petStore.currentState, (newState, oldState) => {
      if (newState === 'sleep' && oldState !== 'sleep') {
        onSleepStart(petStore)
      } else if (newState !== 'sleep' && oldState === 'sleep') {
        onSleepEnd(petStore)
      }
    })
  }

  function destroy() {
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
    if (sleepDreamTimer) { clearTimeout(sleepDreamTimer); sleepDreamTimer = null }
    if (sleepMaxTimer) { clearTimeout(sleepMaxTimer); sleepMaxTimer = null }
  }

  function setBehaviorSequencer(seq) {
    behaviorSequencer = seq
  }

  return { init, destroy, setBehaviorSequencer }
}
```

- [ ] **Step 2: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/composables/usePetAttributeTicker.js
git commit -m "feat(dream): rewrite sleep/dream/wakeup flow with delayed trigger + image generation"
```

---

### Task 7: DreamBubble 组件

**Files:**
- Create: `renderer/src/components/DreamBubble.vue`

- [ ] **Step 1: 创建 DreamBubble.vue**

创建 `renderer/src/components/DreamBubble.vue`：

```vue
<template>
  <Transition name="dream-fade">
    <div v-if="visible" class="dream-bubble">
      <div class="dream-cloud">
        <img
          v-if="imageSrc"
          :src="imageSrc"
          class="dream-image"
          alt="梦境"
        />
        <p class="dream-text">来福梦到了...{{ text }}</p>
      </div>
      <div class="cloud-tail"></div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  imageSrc: { type: String, default: null },
  duration: { type: Number, default: 8000 },
})

const emit = defineEmits(['dismiss'])

const visible = ref(true)
let dismissTimer = null

onMounted(() => {
  dismissTimer = setTimeout(() => {
    visible.value = false
    setTimeout(() => emit('dismiss'), 1000)  // 等淡出动画结束
  }, props.duration)
})

onUnmounted(() => {
  if (dismissTimer) clearTimeout(dismissTimer)
})
</script>

<style scoped>
.dream-bubble {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dream-cloud {
  background: linear-gradient(135deg, #e8d5f5 0%, #c5cae9 100%);
  border-radius: 24px;
  padding: 16px;
  max-width: 240px;
  box-shadow:
    0 8px 32px rgba(100, 80, 160, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.4);
  text-align: center;
}

.dream-image {
  width: 100%;
  max-width: 200px;
  max-height: 200px;
  border-radius: 16px;
  object-fit: cover;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.dream-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3f6b;
}

.cloud-tail {
  width: 20px;
  height: 20px;
  background: #d5c8e8;
  border-radius: 50%;
  margin-top: -4px;
  margin-left: 30px;
  box-shadow: 0 2px 6px rgba(100, 80, 160, 0.15);
}

.cloud-tail::after {
  content: '';
  display: block;
  width: 12px;
  height: 12px;
  background: #d5c8e8;
  border-radius: 50%;
  position: relative;
  top: 12px;
  left: 10px;
}

/* 淡入淡出 */
.dream-fade-enter-active {
  transition: opacity 0.5s ease-in, transform 0.5s ease-in;
}

.dream-fade-leave-active {
  transition: opacity 1s ease-out, transform 1s ease-out;
}

.dream-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}

.dream-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/components/DreamBubble.vue
git commit -m "feat(dream): add DreamBubble component with cloud style"
```

---

### Task 8: DreamDiary 面板

**Files:**
- Create: `renderer/src/components/DreamDiary.vue`

- [ ] **Step 1: 创建 DreamDiary.vue**

创建 `renderer/src/components/DreamDiary.vue`：

```vue
<template>
  <div class="diary-overlay" @click.self="$emit('close')">
    <div class="diary-panel">
      <div class="diary-header">
        <h2>来福的梦境日记</h2>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="diary-content">
        <div v-if="loading" class="diary-loading">加载中...</div>

        <div v-else-if="dreams.length === 0" class="diary-empty">
          <p>来福还没做过梦哦</p>
          <p class="hint">让来福睡一觉试试？</p>
        </div>

        <div v-else class="dream-list">
          <div v-for="dream in dreams" :key="dream.id" class="dream-card">
            <img
              v-if="dream.image_url"
              :src="dream.image_url"
              class="card-image"
              alt="梦境"
            />
            <div class="card-body">
              <p class="card-text">{{ dream.text }}</p>
              <div class="card-deltas" v-if="Object.keys(dream.attribute_deltas || {}).length">
                <span
                  v-for="(val, key) in dream.attribute_deltas"
                  :key="key"
                  class="delta-badge"
                  :class="val > 0 ? 'positive' : 'negative'"
                >
                  {{ deltaLabel[key] || key }} {{ val > 0 ? '+' : '' }}{{ val }}
                </span>
              </div>
              <p class="card-date">{{ formatDate(dream.created_at) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

defineEmits(['close'])

const dreams = ref([])
const loading = ref(true)

const deltaLabel = {
  mood: '心情', energy: '精力', health: '健康',
  affection: '亲密', obedience: '顺从', snark: '毒舌',
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(async () => {
  try {
    const port = await window.electronAPI?.getPythonPort?.() || 18765
    const res = await fetch(`http://127.0.0.1:${port}/api/dream/history`)
    if (res.ok) {
      const data = await res.json()
      dreams.value = (data.dreams || []).map(d => ({
        ...d,
        image_url: d.image_path
          ? `http://127.0.0.1:${port}/api/dream/image/${d.image_path.split('/').pop()}`
          : null,
      }))
    }
  } catch (e) {
    console.error('[DreamDiary] 加载失败:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.diary-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.diary-panel {
  width: 360px;
  max-height: 80vh;
  background: var(--bg-panel, #fff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.diary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: linear-gradient(135deg, #7c4dff 0%, #536dfe 100%);
  color: white;
}

.diary-header h2 {
  margin: 0;
  font-size: 16px;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 13px;
}

.diary-content {
  padding: 14px;
  overflow-y: auto;
  flex: 1;
}

.diary-loading, .diary-empty {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.diary-empty .hint {
  font-size: 12px;
  margin-top: 8px;
}

.dream-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dream-card {
  background: linear-gradient(135deg, #f5f0ff 0%, #ede7f6 100%);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(100, 80, 160, 0.1);
}

.card-image {
  width: 100%;
  height: 150px;
  object-fit: cover;
}

.card-body {
  padding: 12px 14px;
}

.card-text {
  margin: 0 0 8px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3f6b;
}

.card-deltas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.delta-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.delta-badge.positive {
  background: rgba(67, 233, 123, 0.15);
  color: #2e7d32;
}

.delta-badge.negative {
  background: rgba(245, 87, 108, 0.15);
  color: #c62828;
}

.card-date {
  margin: 0;
  font-size: 11px;
  color: #999;
}

[data-theme="dark"] .diary-panel {
  --bg-panel: #2a2a2a;
}

[data-theme="dark"] .dream-card {
  background: linear-gradient(135deg, #3a3050 0%, #2d2845 100%);
}

[data-theme="dark"] .card-text {
  color: #d4c8f0;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/components/DreamDiary.vue
git commit -m "feat(dream): add DreamDiary panel with card layout"
```

---

### Task 9: App.vue 挂载 + Electron 菜单

**Files:**
- Modify: `renderer/src/App.vue`
- Modify: `electron/main.js`

- [ ] **Step 1: App.vue 挂载 DreamBubble + DreamDiary**

在 `renderer/src/App.vue` 的 template 中，在 `<SettingsPanel>` 之前添加：

```html
    <!-- 梦境气泡 -->
    <DreamBubble
      v-if="petStore.showDreamBubble"
      :text="petStore.dreamResult?.text || ''"
      :image-src="petStore.dreamResult?.imageSrc"
      :duration="8000"
      @dismiss="petStore.showDreamBubble = false; petStore.dreamResult = null"
    />

    <!-- 梦境日记 -->
    <DreamDiary
      v-if="uiStore.showDreamDiary"
      @close="uiStore.closeDreamDiary()"
    />
```

在 script import 区域添加：

```javascript
import DreamBubble from './components/DreamBubble.vue'
import DreamDiary from './components/DreamDiary.vue'
```

- [ ] **Step 2: App.vue 添加 onOpenDreamDiary 监听**

在 `onMounted` 的 Electron 事件监听区域添加：

```javascript
    window.electronAPI.onOpenDreamDiary(() => {
      uiStore.openDreamDiary()
    })
```

- [ ] **Step 3: Electron preload.js 添加 IPC**

在 `renderer/src/App.vue` 中需要的 IPC，检查 preload.js 是否已有 `onOpenDreamDiary`。如果没有，在 `electron/preload.js` 的 contextBridge.exposeInMainWorld 中添加：

```javascript
    onOpenDreamDiary: (callback) => ipcRenderer.on('open-dream-diary', () => callback()),
```

- [ ] **Step 4: Electron main.js 添加菜单项**

在 `electron/main.js` 的右键菜单中，在 `{ label: '记忆管理', click: openMemoryPanel },` 之前添加：

```javascript
      { label: '梦境日记', click: () => mainWindow.webContents.send('open-dream-diary') },
```

- [ ] **Step 5: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/App.vue renderer/src/components/DreamBubble.vue renderer/src/components/DreamDiary.vue electron/main.js electron/preload.js
git commit -m "feat(dream): mount DreamBubble + DreamDiary in App, add tray menu entry"
```

---

### Task 10: 集成验证

- [ ] **Step 1: 验证后端 API**

```bash
cd E:/Proj/pet_buddy/python-service
python -c "from dream.image_generator import DreamImageGenerator; print('DreamImageGenerator OK')"
python -c "from main import app; routes=[r.path for r in app.routes if hasattr(r,'path')]; print([r for r in routes if 'dream' in r])"
```

Expected: 输出包含 `/api/dream/image`, `/api/dream/history`, `/api/dream/image/{filename}`

- [ ] **Step 2: 验证 dream_engine 返回 image_prompt**

```bash
cd E:/Proj/pet_buddy/python-service
python -c "
from agent.dream_engine import DreamEngine
de = DreamEngine.__new__(DreamEngine)
prompt = de._build_dream_prompt.__code__.co_consts
print('image_prompt' in str(prompt))
"
```

Expected: `True`

- [ ] **Step 3: Commit**

```bash
cd E:/Proj/pet_buddy
git add -A
git commit -m "feat(dream): complete dream system enhancement"
```

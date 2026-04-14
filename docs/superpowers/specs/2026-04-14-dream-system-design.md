# 做梦系统完善设计

> 来福睡觉时会做梦，梦境通过 AI 绘图可视化，醒来后用专属梦境气泡展示，所有梦境记录在梦境日记中。

## 核心方案

**睡眠微动画 + 延迟做梦 + AI 绘图 + 醒来回忆气泡 + 梦境日记**

## 完整流程

```
睡前仪式/闲置5分钟 → 进入睡眠
    ↓
睡眠微动画（呼吸起伏 + zzzs 持续 + 深蓝遮罩）
    ↓ 睡眠 30 秒后
触发做梦 API → LLM 生成梦境文字 + image_prompt → AI 绘图生成梦境图
    ↓ 生成完成，结果暂存
继续睡眠（最长 5 分钟 或 用户点击/说话/喂食唤醒）
    ↓
醒来动画（移除 zzzs → 伸懒腰 → 打哈欠）
    ↓
梦境气泡展示（云朵样式 + 梦境图 + "来福梦到了..."，8 秒后淡出）
    ↓
回到 idle，梦境存入日记
```

## 睡眠微动画

### 修复 bedtime 脚本

当前 bedtime 脚本末尾移除 zzzs 后没有后续状态。修改为：末尾保持 sleep 姿态，zzzs 持续显示，由醒来流程统一清理。

### 睡眠期间效果

- **呼吸起伏**：Y 轴 sin 波动，周期 3 秒，幅度 2px
- **zzzs 道具**：从进入 sleep 到醒来全程持续显示
- **深蓝遮罩**：画面叠加半透明深蓝色（opacity 0.15），营造夜晚氛围

## 做梦触发与生成

### 触发时机

进入 sleep 状态后**延迟 30 秒**触发做梦（而非现在的立即触发）。使用 `setTimeout` 在 `usePetAttributeTicker` 的 sleep watch 中延迟调用。如果在 30 秒内被唤醒则取消做梦。

### 后端变更

#### dream_engine.py

LLM prompt 新增要求：在返回 JSON 中增加 `image_prompt` 字段（英文，用于绘图 API）。

返回结构变为：
```python
{
    "dream_text": "来福梦到在大草原上追蝴蝶...",
    "image_prompt": "a cute corgi puppy chasing butterflies in a vast green meadow, dreamy soft lighting, watercolor style",
    "attribute_deltas": {"mood": +5, "energy": +3},
    "profile_updates": [...],
    "reasoning": "..."
}
```

#### 新增 POST /api/dream/image

接收 `image_prompt`，调用硅基流动 API 生成图片：

```
Request: { "prompt": "a cute corgi..." }
Response: { "image_base64": "...", "image_path": "data/dreams/20260414-195200.png" }
```

图片保存到 `data/dreams/` 目录，文件名为时间戳。

#### 新增 GET /api/dream/history

从 SQLite events 表查询 `【做梦】` 前缀的记录，关联梦境图片：

```
Response: {
  "dreams": [
    {
      "id": 1,
      "text": "来福梦到在大草原上追蝴蝶...",
      "image_path": "data/dreams/20260414-195200.png",
      "attribute_deltas": {"mood": +5},
      "created_at": "2026-04-14T19:52:00"
    },
    ...
  ]
}
```

### AI 绘图配置

config.json 新增 `image` 配置块：

```json
{
  "image": {
    "provider": "siliconflow",
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "sk-xxx",
    "model": "black-forest-labs/FLUX.1-schnell"
  }
}
```

### 图片生成封装

新建 `dream/image_generator.py`，封装硅基流动 Images API 调用：

```python
class DreamImageGenerator:
    async def generate(self, prompt: str) -> tuple[str, bytes]:
        """
        调用绘图 API 生成梦境图片。
        Returns: (saved_file_path, image_bytes)
        """
```

- 使用 OpenAI-compatible Images API 格式（`POST /images/generations`）
- 图片尺寸：512x512
- 保存到 `data/dreams/{timestamp}.png`
- 生成失败时返回 None，不阻塞做梦流程（梦境文字仍然展示）

## 醒来流程

### 触发条件（满足任一）

1. 睡眠达到最长时间（默认 5 分钟）
2. 用户点击来福
3. 用户说话（VAD 检测到语音）
4. 用户喂食/玩耍

### 醒来动画序列

新增 `wakeup` 行为脚本：

```javascript
wakeup: {
  id: 'wakeup',
  cooldown: 0,
  weight: 0,
  steps: [
    { type: 'prop',  value: 'zzzs', op: 'remove' },
    { type: 'pose',  value: 'cute_pose', duration: 400 },  // 伸懒腰
    { type: 'wait',  duration: 800 },
    { type: 'pose',  value: 'bark', duration: 300 },       // 打哈欠
    { type: 'wait',  duration: 500 },
    { type: 'pose',  value: 'idle' },
  ],
}
```

醒来时：
1. 取消深蓝遮罩（前端 CSS 过渡移除）
2. 执行 wakeup 行为脚本
3. 脚本完成后，如果有梦境结果，展示 DreamBubble
4. DreamBubble 8 秒后淡出

## 梦境气泡 (DreamBubble)

### 视觉设计

区别于普通 ChatBubble 的专属样式：

- **形状**：云朵形状边框（大圆角 + 底部小云朵尾巴）
- **背景**：淡紫色到深蓝渐变（`linear-gradient(135deg, #e8d5f5, #c5cae9)`）
- **图片区**：顶部展示梦境图片，圆角，最大 200x200px
- **文字区**：下方显示 "来福梦到了...{dream_text}"，字体稍小，白色/浅色
- **动画**：淡入（0.5s ease-in），8 秒后淡出（1s ease-out）
- **装饰**：可选的小星星/萤火虫 CSS 粒子

### 组件接口

```vue
<DreamBubble
  v-if="showDreamBubble"
  :text="dreamText"
  :image-src="dreamImageSrc"
  :duration="8000"
  @dismiss="showDreamBubble = false"
/>
```

### 无图片降级

如果 AI 绘图失败，DreamBubble 只显示文字部分，不显示图片区域。气泡仍然使用梦境专属样式。

## 梦境日记面板 (DreamDiary)

### 入口

- 系统托盘右键菜单新增"梦境日记"选项
- 点击后打开 DreamDiary 面板（覆盖式，类似 MemoryPanel）

### 布局

卡片式纵向滚动列表：

```
┌─────────────────────────────┐
│ 📖 来福的梦境日记      [✕]  │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ [梦境图片 200x150]      │ │
│ │                         │ │
│ │ "来福梦到在草原追蝴蝶…" │ │
│ │                         │ │
│ │ 😊 mood+5  ⚡ energy+3  │ │
│ │ 2026-04-14 19:52        │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │ [梦境图片]              │ │
│ │ "来福梦到和主人去海边…" │ │
│ │ ❤️ affection+3          │ │
│ │ 2026-04-13 23:15        │ │
│ └─────────────────────────┘ │
│                             │
│  （没有更多梦境了）          │
└─────────────────────────────┘
```

每张卡片包含：
- 梦境图片（如果有），圆角，点击可放大
- 梦境文字
- 属性变化标签（彩色小 badge）
- 日期时间

### 无梦境状态

如果来福还没做过梦，显示空状态：
> "来福还没做过梦哦，让来福睡一觉试试？"

### 数据来源

调用 `GET /api/dream/history`，返回所有历史梦境记录。

## 梦境图片存储

### 存储位置

```
python-service/data/dreams/
├── 20260414-195200.png
├── 20260413-231500.png
└── ...
```

### 前端访问

新增静态文件路由，让前端可以通过 URL 访问梦境图片：
```
GET /api/dream/image/{filename}
→ 返回图片文件
```

### dream_engine 存储变更

dreams 相关数据存储在 SQLite events 表中，扩展 content 格式：

```
content: "【做梦】{dream_text}"
metadata: 新增字段存储 image_path 和 attribute_deltas（JSON 序列化到 content 或新增列）
```

考虑到 events 表结构简单（只有 content + importance），将完整梦境数据 JSON 序列化存入 content：

```
content: JSON.dumps({
    "type": "dream",
    "text": "来福梦到...",
    "image_prompt": "a cute corgi...",
    "image_path": "data/dreams/20260414-195200.png",
    "attribute_deltas": {"mood": +5, "energy": +3}
})

注意：旧版梦境记录的 content 是 `"【做梦】{text}"` 纯文本格式。`GET /api/dream/history` 端点需要兼容两种格式：尝试 JSON 解析，失败则按旧格式提取文本（去掉 `【做梦】` 前缀），image_path 为 null。
```

## 前端状态管理

### usePetAttributeTicker 重写做梦逻辑

```javascript
watch(() => petStore.currentState, (newState) => {
  if (newState === 'sleep') {
    // 延迟 30 秒后触发做梦
    sleepDreamTimer = setTimeout(() => tryDream(), 30000)
    // 最长 5 分钟后自动醒来
    sleepMaxTimer = setTimeout(() => wakeUp(), 5 * 60 * 1000)
  } else if (oldState === 'sleep') {
    // 被提前唤醒，取消定时器
    clearTimeout(sleepDreamTimer)
    clearTimeout(sleepMaxTimer)
  }
})
```

### 新增 dream 状态到 petStore

```javascript
dreamResult: ref(null),      // { text, imageSrc, attributeDeltas }
showDreamBubble: ref(false),
```

### ui store 扩展

```javascript
showDreamDiary: ref(false),
openDreamDiary() { this.showDreamDiary = true },
closeDreamDiary() { this.showDreamDiary = false },
```

## 新增/修改文件清单

### 新增文件

- `python-service/dream/__init__.py`
- `python-service/dream/image_generator.py` — 硅基流动绘图 API 封装
- `renderer/src/components/DreamBubble.vue` — 梦境气泡组件
- `renderer/src/components/DreamDiary.vue` — 梦境日记面板

### 修改文件

- `python-service/config.json` — 新增 `image` 配置块
- `python-service/agent/dream_engine.py` — LLM prompt 增加 image_prompt，存储格式变更
- `python-service/main.py` — 新增 `/api/dream/image`、`/api/dream/history`、图片静态路由
- `renderer/src/composables/useBehaviorSequencer.js` — 修复 bedtime 脚本 + 新增 wakeup 脚本
- `renderer/src/composables/usePetAttributeTicker.js` — 重写做梦触发（延迟 30s + 图片 + 醒来）
- `renderer/src/stores/pet.js` — 新增 dreamResult / showDreamBubble
- `renderer/src/stores/ui.js` — 新增 showDreamDiary
- `renderer/src/App.vue` — 挂载 DreamBubble + DreamDiary
- `electron/main.js` — 托盘菜单新增"梦境日记"

# 来福情绪识别系统设计

> 来福通过摄像头"偷偷观察"主人，识别情绪并做出自然反应。

## 核心方案

**混合检测 + 分层反应 + 微妙暗示**

- Layer 1 本地轻量模型做快速表情分类（< 200ms，离线可用）
- Layer 2 视觉 LLM 做深度情绪 + 场景理解（仅在情绪显著变化时触发）
- 来福偷看时通过微妙动作暗示（歪头、竖耳），不做显式 UI 提示

## 触发机制

三种触发方式并存：

| 方式 | 时机 | 说明 |
|------|------|------|
| 定时轮询 | 每 5-30 分钟（默认 10 分钟） | 设置中可调，仅检测到人脸时计入间隔 |
| 事件驱动 | 用户发送消息前（截帧后再发 /api/chat）、闲置 > 5 分钟、用户 > 20 分钟无互动 | 自动在关键节点插入观察 |
| 手动触发 | 设置面板"让来福看看你"按钮 | 即时返回完整结果（含深度分析） |

用户正在说话或打字时延迟偷看，避免打断交互。

## API 设计

### POST /api/emotion

**Request** (multipart/form-data):
```
image: File       # JPEG 截帧
deep:  bool=false # 是否强制深度分析
```

**Response**:
```json
{
  "has_face": true,
  "local": {
    "emotion": "sad",
    "confidence": 0.82,
    "all_scores": {
      "happy": 0.05, "sad": 0.82, "angry": 0.03,
      "surprise": 0.01, "neutral": 0.07, "fear": 0.02
    }
  },
  "deep": {
    "description": "主人趴在桌上，看起来很疲惫",
    "suggested_action": "comfort",
    "suggested_speech": "主人...要不要休息一下？来福给你暖脚！"
  },
  "changed": true
}
```

- `deep` 字段仅在触发深度分析时返回，否则为 null。
- `changed` 表示相比后端缓存的上一次检测结果，情绪类别是否发生变化。

## 深度分析触发条件

Layer 1 → Layer 2 升级逻辑（满足任一即触发）：

1. **情绪类别跳变** — neutral → sad, happy → angry 等跨类别变化
2. **负面情绪持续** — sad/angry/fear 连续检测到 2 次以上（防误判）
3. **手动触发** — 设置面板按钮或 `deep=true` 参数
4. **冷却机制** — 深度分析至少间隔 3 分钟，防频繁调用 API

## 分层反应

### Layer 1 快速反应（本地检测后立即执行）

触发来福姿态变化，不发起对话：

| 检测结果 | 来福反应 |
|----------|----------|
| happy | 轻摇尾巴，回到正常待机 |
| sad | 慢慢走近，低头蹭主人 |
| angry | 缩一下身子，小心翼翼地看着 |
| surprise | 耳朵竖起，歪头好奇 |
| neutral | 小呵欠，继续待机 |
| fear | 贴近主人，做保护姿态 |
| disgust | 同 angry，缩一下身子 |

### Layer 2 深度反应（LLM 返回后执行）

- LLM 自然语言描述注入 `DogAgent.owner_emotion_context`
- 来福主动发起对话（通过 TTS 语音输出）
- 触发专用 behavior script（如 `emotion_comfort`）
- system prompt 注入方式：

```python
if self.owner_emotion_context:
    prompt += f"""
【主人当前状态】
你刚刚偷偷看了主人一眼，观察到：{self.owner_emotion_context}
请根据观察到的情绪自然地调整你的语气和行为，
但不要直接说"我检测到你很难过"这种机械的话。
像一只敏感的狗狗那样，用行动和关心来回应。
"""
```

## "偷看"动画序列

来福偷看时的行为脚本（总时长 < 1.5 秒）：

1. **竖耳** — 暂停当前动作，耳朵微微竖起（300ms）
2. **歪头看向摄像头** — 头部微转 + 眼神朝上偏移（400ms，缓动）
3. **等待检测** — 保持歪头姿势，可加一次眨眼（~200ms 等后端返回）
4. **情绪反应** — 根据 Layer 1 结果切换到对应姿态

设计原则：
- 不是每次都做完整偷看动画，有时只是耳朵动一下（随机化）
- 动画幅度轻微随机，避免机械感
- 敏感的用户能察觉，但不显式提醒

对应 behavior script：
```javascript
peek_observe: {
  cooldown: 0,    // 由 observer 调度控制
  weight: 0,      // 不参与随机触发
  steps: [
    { type: 'pose', value: 'alert', duration: 300 },
    { type: 'pose', value: 'peek_up', duration: 400 },
    { type: 'wait', duration: 600 },
    // 后续步骤由检测结果动态注入
  ]
}
```

## 首次引导流程

### Step 1: 设置面板触发
用户在设置面板看到"让来福观察你"开关（默认关闭），附带说明文字："来福会偷偷看你，根据你的心情做出反应"。点击开关进入引导。

### Step 2: 来福请求权限
来福做出好奇动作（歪头 + 竖耳 + 看向上方），气泡弹出：
> "汪？主人，来福想看看你的样子！可以让来福偷偷看你吗？"

展示"好呀！"和"不要"两个按钮。

### Step 3: 授权完成
点击"好呀"→ 浏览器弹出摄像头权限弹窗。用户允许后：
- 来福开心摇尾巴
- 气泡："嘿嘿，来福以后会偷偷看你的！才不会让你发现呢！"
- 设置开关变为已启用，开始首次情绪检测

### 拒绝路径
用户点"不要"或取消权限弹窗：
- 来福"委屈"表情 → 气泡："呜...好吧，来福不看了..."
- 开关保持关闭，不再自动弹出
- 可在设置中随时重新开启

## 设置面板

在设置面板新增"情绪观察"区域：

- **开关**："让来福观察你" — 主开关，控制整个功能
- **频率滑杆**：偷看频率 5-30 分钟，默认 10 分钟
- **手动触发按钮**："让来福看看你" — 即时执行一次完整检测

## 前端状态

### petStore 扩展

```javascript
emotionObserver: {
  enabled: false,        // 是否已授权启用
  lastEmotion: null,     // 'happy' | 'sad' | 'angry' | 'surprise' | 'neutral' | 'fear'
  lastConfidence: 0,     // 0-1
  lastDeepDesc: '',      // LLM 深度描述文本
  lastDetectTime: 0,     // 上次检测时间戳
  isObserving: false,    // 当前是否正在"偷看"（控制动画）
  consecutiveNeg: 0,     // 连续负面情绪计数（用于触发深度分析）
}
```

### settings store 扩展

```javascript
emotionEnabled: false,          // 主开关
emotionInterval: 10,            // 轮询间隔（分钟）
```

## 后端组件

### EmotionDetector 类 (emotion/detector.py)

职责：
- 封装 DeepFace 人脸检测 + 表情分类
- 管理模型加载（延迟加载，首次调用时初始化）
- 维护上一次检测结果用于变化比较
- 调用视觉 LLM 做深度分析（当触发条件满足时）

关键方法：
- `detect(image_bytes) → LocalResult` — Layer 1 快速检测
- `analyze_deep(image_bytes, local_result) → DeepResult` — Layer 2 LLM 分析
- `should_trigger_deep(current, previous) → bool` — 判断是否升级到深度分析

本地模型选型：DeepFace 默认使用 VGG-Face 后端，可配置为更轻量的 `opencv` 或 `ssd` 人脸检测器。表情分类使用 FER-2013 预训练权重。

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 摄像头被占用/不可用 | 来福"捂眼"动作 + 气泡"来福看不到主人了..."，暂停定时观察，摄像头恢复后自动重试 |
| 未检测到人脸 | 静默忽略，不触发反应。连续 3 次未检测到 → 轮询间隔翻倍，检测到人脸后恢复 |
| LLM 深度分析失败 | 仅使用 Layer 1 结果做轻量反应，下次触发时重试 |
| 本地模型加载失败 | 设置面板提示"来福还在学习观察..."，提供安装引导，功能降级不崩溃 |

## 隐私保护

**图像生命周期**：截帧 → 发送检测 → 本地分析 → **立即销毁图像**

**保存的数据**：情绪标签、置信度、检测时间戳、LLM 文字描述
**绝不保存的**：原始图像、base64 数据、人脸特征向量、任何可还原面部的数据

**LLM 深度分析**：图像通过 API 发送给视觉模型，遵循该模型提供商的数据政策。设置面板中注明此点。

## 性能约束

| 指标 | 目标值 |
|------|--------|
| Layer 1 本地检测 | < 200ms |
| Layer 2 LLM 深度分析 | 2-5s |
| 截帧分辨率 | 640x480 JPEG |
| 深度分析冷却 | >= 3 分钟 |
| 摄像头流 | 每次截帧时打开 → 拍一帧 → 立即关闭，不保持常开 |

## 文件清单

### 新增文件
- `python-service/emotion/__init__.py`
- `python-service/emotion/detector.py` — EmotionDetector 类
- `renderer/src/composables/useEmotionObserver.js` — 摄像头管理 + 调度 + 截帧
- `python-service/tests/test_emotion.py` — 检测器单元测试

### 修改文件
- `python-service/main.py` — 新增 `POST /api/emotion` 端点
- `python-service/agent/dog_agent.py` — `owner_emotion_context` 注入 system prompt
- `python-service/requirements.txt` — 添加 deepface 依赖
- `renderer/src/stores/pet.js` — 新增 `emotionObserver` 状态
- `renderer/src/stores/settings.js` — 新增情绪观察设置项
- `renderer/src/components/SettingsPanel.vue` — 情绪观察 UI 区域
- `renderer/src/App.vue` — 挂载引导流程
- `renderer/src/composables/useBehaviorSequencer.js` — 新增 `peek_observe` + 情绪反应脚本

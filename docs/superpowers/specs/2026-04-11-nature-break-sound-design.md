# 设计文档：天性模式调度器 + 休息提醒 + 音效联动

**日期：** 2026-04-11  
**状态：** 已审批  
**对应任务：** T7.2、T7.3、T7.4、T7.6

---

## 一、背景与目标

M2 阶段剩余三个未完成功能：

| 功能 | 任务ID | 当前状态 |
|------|--------|---------|
| 天性模式调度器（随机行为触发） | T7.3 | 仅有状态变量，无调度逻辑 |
| 天性模式 AI 互动文案 | T7.4 | 未实现 |
| 动作与音效联动 | T7.2 | 无任何 Audio 代码 |
| 休息提醒系统 | T7.6 | 完全未实现 |

**目标：** 在现有代码基础上，以最小改动量实现上述四个功能，不引入新的主进程依赖。

---

## 二、架构方案

**选型：Vue Composables（纯 Renderer）**

理由：桌面宠物窗口常驻透明置顶，不会被系统挂起，`setInterval` 可靠运行。无需改动 Electron 主进程或 preload，改动面最小。

---

## 三、文件结构

```
renderer/src/
├── composables/
│   ├── useNatureMode.js         # 天性模式调度器（新建）
│   ├── useBreakReminder.js      # 休息提醒系统（新建）
│   └── useSoundManager.js       # 音效管理器（新建）
├── stores/
│   └── ui.js                    # 新增 showBreakReminder 状态（改动）
├── components/
│   └── BreakReminderBubble.vue  # 休息提醒气泡（新建）
└── App.vue                      # 组合三个 composable（改动）

renderer/public/sounds/          # 占位音效文件（新建目录）
├── bark_short.wav
├── bark_happy.wav
├── whine.wav
└── notification.wav
```

---

## 四、模块详细设计

### 4.1 `useSoundManager.js`

**职责：** 统一管理音效播放，对外暴露简单接口。

**接口：**
```js
const { playSound } = useSoundManager()
playSound('bark_short')   // 播放 bark_short.wav
playSound('notification') // 播放 notification.wav
```

**实现要点：**
- 维护 `Map<name, HTMLAudioElement>` 缓存，首次调用时懒加载对应 WAV 文件
- 若同名音效正在播放，先 `pause()` 再重置 `currentTime = 0` 后重播
- 音量固定 0.7（后续可从配置读取）
- 文件路径：`/sounds/{name}.wav`（对应 `renderer/public/sounds/`）

**音效名称映射：**
| 动作 | 音效文件 |
|------|---------|
| BARK | bark_short.wav |
| HAPPY_RUN | bark_happy.wav |
| CUDDLE | whine.wav |
| CUTE | whine.wav |
| 休息提醒 | notification.wav |

---

### 4.2 `useNatureMode.js`

**职责：** 当天性模式开启时，定时随机触发宠物行为。

**参数：** `petCanvasRef` — PetCanvas 组件的 ref，用于调用 `transitionTo()`

**触发逻辑：**
1. 启动后设置首次间隔（5-15 分钟随机）
2. 触发条件：`uiStore.natureMode === true` 且 `uiStore.focusMode === false`
3. 每次触发执行：
   - 调用 `petStore.getRandomBehavior()` 抽取动作
   - 调用 `petCanvas.transitionTo(action)` 切换动画
   - 调用 `playSound()` 播放对应音效
   - 30% 概率从预置文案池随机抽一句，调用 `chatStore` 显示气泡（2秒后自动关闭）
4. 触发完成后，重新随机下一次间隔（5-15 分钟）

**预置文案池（10条）：**
```js
const phrases = [
  '汪！主人在干嘛呀～',
  '呜…来福想你了！',
  '主人，陪我玩嘛～',
  '汪汪！我刚才梦到骨头了！',
  '主人你有没有在偷偷看我？',
  '来福今天表现怎么样？',
  '汪！外面好像有动静！',
  '主人，摸摸我嘛～',
  '呜呜，来福饿了…',
  '汪！我爱你主人！'
]
```

**生命周期：**
- `init()` 启动调度器
- `destroy()` 清除定时器（`onUnmounted` 时调用）

---

### 4.3 `useBreakReminder.js`

**职责：** 每 45 分钟提醒用户休息。

**触发流程：**
1. 固定 45 分钟 `setTimeout`（可从 `python-service/config.json` 读取，默认 45）
2. 触发时：
   - 调用 `playSound('notification')`
   - 宠物切换 `CUDDLE` 动画（通过 `petCanvasRef`）
   - 设置 `uiStore.showBreakReminder = true`，显示提醒气泡
3. 用户点击"好的去休息" → 关闭气泡，重置 45 分钟计时器
4. 用户点击"再等 10 分钟" → 关闭气泡，10 分钟后再次触发（最多推迟 2 次，之后直接等 45 分钟）

**生命周期：** 同 `useNatureMode`，`init()` / `destroy()`

---

### 4.4 `BreakReminderBubble.vue`

**职责：** 显示休息提醒的气泡 UI。

**样式：** 复用 `ChatBubble.vue` 的样式变量，固定显示在屏幕中央，`z-index: 200`

**内容：**
```
🐾 主人，你已经工作 45 分钟了，起来活动一下吧！

[好的去休息]  [再等 10 分钟]
```

**状态控制：** 通过 `uiStore.showBreakReminder`（布尔值）控制显示/隐藏

---

### 4.5 `ui.js` 改动

新增两个状态和方法：
```js
const showBreakReminder = ref(false)
const breakReminderSnoozeCount = ref(0)

function showBreakReminderDialog() { showBreakReminder.value = true }
function hideBreakReminderDialog() { showBreakReminder.value = false }
```

---

### 4.6 `App.vue` 改动

```js
import { useNatureMode } from './composables/useNatureMode'
import { useBreakReminder } from './composables/useBreakReminder'

const petCanvasRef = ref(null)  // 绑定到 <PetCanvas ref="petCanvasRef" />
const { init: initNature, destroy: destroyNature } = useNatureMode(petCanvasRef)
const { init: initBreak, destroy: destroyBreak } = useBreakReminder(petCanvasRef)
// useSoundManager 由各 composable 内部直接 import 调用，无需 provide/inject

onMounted(() => {
  initNature()
  initBreak()
})

onUnmounted(() => {
  destroyNature()
  destroyBreak()
})
```

---

### 4.7 占位音效文件

用 Python 脚本（`tools/gen_placeholder_sounds.py`）生成 4 个 WAV 文件：
- 格式：44100 Hz，单声道，16-bit PCM
- 内容：短促的 440Hz 正弦波音调（可区分，非静音）
- 放入 `renderer/public/sounds/`

---

## 五、不在本次范围内

- LLM 实时生成文案（T7.4 的 LLM 部分）：预置文案已满足当前需求，后续 M3 扩展
- 云端 TTS 备选（T6.6）：P2 优先级，跳过
- 专注模式番茄钟 UI（T7.7）：P2 优先级，跳过
- 口型同步（T5.6）：独立功能，本次不涉及

---

## 六、成功标准

- [ ] 天性模式开启时，5-15 分钟内宠物自动触发随机动作
- [ ] 触发动作时同步播放对应音效
- [ ] 30% 概率显示预置文案气泡
- [ ] 专注模式开启时，天性模式不触发
- [ ] 45 分钟后显示休息提醒气泡，两个按钮功能正常
- [ ] 推迟功能最多 2 次有效

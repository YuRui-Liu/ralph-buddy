# 天性模式调度器 + 休息提醒 + 音效联动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现天性模式随机行为调度器、45分钟休息提醒系统、动作与音效联动，均通过 Vue Composables 在 Renderer 进程中运行。

**Architecture:** 三个独立 composable（`useNatureMode`、`useBreakReminder`、`useSoundManager`）在 `App.vue` 中组合，通过现有 `petStore`/`uiStore`/`chatStore` 联动动画与气泡。定时器使用 `setTimeout` 递归调度，`BreakReminderBubble` 通过 Vue provide/inject 获取 `confirm`/`snooze` 回调。

**Tech Stack:** Vue 3 Composition API, Pinia, Web Audio API（`new Audio()`），Python stdlib（`wave` 模块生成占位 WAV）

---

## 文件清单

| 操作 | 路径 | 职责 |
|------|------|------|
| 新建 | `tools/gen_placeholder_sounds.py` | 生成 4 个占位 WAV 文件 |
| 新建 | `renderer/public/sounds/bark_short.wav` | 汪叫短音（800Hz 0.3s） |
| 新建 | `renderer/public/sounds/bark_happy.wav` | 开心叫（600Hz 0.6s） |
| 新建 | `renderer/public/sounds/whine.wav` | 撒娇声（400Hz 0.8s） |
| 新建 | `renderer/public/sounds/notification.wav` | 提醒音（523Hz C5 0.5s） |
| 新建 | `renderer/src/composables/useSoundManager.js` | 音效播放，懒加载缓存 |
| 新建 | `renderer/src/composables/useNatureMode.js` | 天性模式随机调度器 |
| 新建 | `renderer/src/composables/useBreakReminder.js` | 45分钟休息提醒定时器 |
| 修改 | `renderer/src/stores/ui.js` | 新增 showBreakReminder + snoozeCount 状态 |
| 新建 | `renderer/src/components/BreakReminderBubble.vue` | 休息提醒气泡 UI |
| 修改 | `renderer/src/App.vue` | 组合三个 composable，注册 BreakReminderBubble |

---

## Task 1: 生成占位音效文件

**Files:**
- Create: `tools/gen_placeholder_sounds.py`
- Creates: `renderer/public/sounds/bark_short.wav`, `bark_happy.wav`, `whine.wav`, `notification.wav`

- [ ] **Step 1: 创建生成脚本**

新建 `tools/gen_placeholder_sounds.py`，内容如下：

```python
#!/usr/bin/env python3
"""Generate placeholder WAV sound files for DogBuddy. Run from project root."""

import os
import math
import struct
import wave

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'renderer', 'public', 'sounds')

def generate_sine_wave(freq=440, duration=0.5, sample_rate=44100, amplitude=0.4):
    num_samples = int(sample_rate * duration)
    samples = [int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate) * 32767)
               for i in range(num_samples)]
    return struct.pack(f'<{num_samples}h', *samples)

def write_wav(filename, freq=440, duration=0.5, sample_rate=44100):
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(generate_sine_wave(freq, duration, sample_rate))
    print(f'Generated: {path}')

os.makedirs(OUTPUT_DIR, exist_ok=True)
write_wav('bark_short.wav',    freq=800, duration=0.3)
write_wav('bark_happy.wav',    freq=600, duration=0.6)
write_wav('whine.wav',         freq=400, duration=0.8)
write_wav('notification.wav',  freq=523, duration=0.5)
print('Done.')
```

- [ ] **Step 2: 运行脚本生成 WAV 文件**

在项目根目录运行：
```bash
python tools/gen_placeholder_sounds.py
```

预期输出：
```
Generated: .../renderer/public/sounds/bark_short.wav
Generated: .../renderer/public/sounds/bark_happy.wav
Generated: .../renderer/public/sounds/whine.wav
Generated: .../renderer/public/sounds/notification.wav
Done.
```

- [ ] **Step 3: 验证文件存在**

```bash
ls renderer/public/sounds/
```

预期输出：`bark_happy.wav  bark_short.wav  notification.wav  whine.wav`

- [ ] **Step 4: 提交**

```bash
git add tools/gen_placeholder_sounds.py renderer/public/sounds/
git commit -m "feat: add placeholder WAV sound files and generator script"
```

---

## Task 2: 实现 `useSoundManager.js`

**Files:**
- Create: `renderer/src/composables/useSoundManager.js`

- [ ] **Step 1: 创建 composables 目录并新建文件**

新建 `renderer/src/composables/useSoundManager.js`，内容如下：

```js
/**
 * useSoundManager
 * 统一管理音效播放。使用模块级缓存（Map），首次调用时懒加载 Audio 实例。
 * 
 * 用法：
 *   const { playSound } = useSoundManager()
 *   playSound('bark_short')   // 播放 /sounds/bark_short.wav
 */

// 模块级缓存，所有 composable 实例共享同一批 Audio 对象
const audioCache = new Map()

function getAudio(name) {
  if (!audioCache.has(name)) {
    const audio = new Audio(`/sounds/${name}.wav`)
    audio.volume = 0.7
    audioCache.set(name, audio)
  }
  return audioCache.get(name)
}

export function useSoundManager() {
  /**
   * 播放指定音效。若上次同名音效仍在播放，先暂停再重播。
   * @param {string} name - 音效名称，对应 /sounds/{name}.wav
   */
  function playSound(name) {
    const audio = getAudio(name)
    if (!audio.paused) {
      audio.pause()
      audio.currentTime = 0
    }
    audio.play().catch(() => {
      // 忽略浏览器自动播放限制（用户未交互时可能被阻止）
    })
  }

  return { playSound }
}
```

- [ ] **Step 2: 手动验证（在 Vite dev 环境）**

启动开发服务器后，在浏览器控制台执行：
```js
// 打开 http://localhost:5173，在 DevTools Console 中：
const audio = new Audio('/sounds/bark_short.wav')
audio.play()
```
预期：听到一声短促的 800Hz 音调。若听不到，检查 `renderer/public/sounds/bark_short.wav` 是否存在且非空。

- [ ] **Step 3: 提交**

```bash
git add renderer/src/composables/useSoundManager.js
git commit -m "feat: add useSoundManager composable with lazy-loaded audio cache"
```

---

## Task 3: 修改 `ui.js`，新增休息提醒状态

**Files:**
- Modify: `renderer/src/stores/ui.js`

- [ ] **Step 1: 在 `ui.js` 的 state 区域新增两个 ref**

打开 `renderer/src/stores/ui.js`，在 `const petScale = ref(1)` 后面添加：

```js
  const showBreakReminder = ref(false)
  const breakReminderSnoozeCount = ref(0)
```

- [ ] **Step 2: 新增三个方法**

在 `function setPetScale(scale)` 后面添加：

```js
  function showBreakReminderDialog() {
    showBreakReminder.value = true
  }

  function hideBreakReminderDialog() {
    showBreakReminder.value = false
  }

  function incrementBreakSnooze() {
    breakReminderSnoozeCount.value++
  }

  function resetBreakSnooze() {
    breakReminderSnoozeCount.value = 0
  }
```

- [ ] **Step 3: 在 return 中暴露新增内容**

在 `return { ... }` 中添加（紧接 `setPetScale` 后面）：

```js
    showBreakReminder,
    breakReminderSnoozeCount,
    showBreakReminderDialog,
    hideBreakReminderDialog,
    incrementBreakSnooze,
    resetBreakSnooze,
```

完整 `return` 语句应为：

```js
  return {
    showInput,
    showSettings,
    showVoiceManager,
    focusMode,
    natureMode,
    petScale,
    showBreakReminder,
    breakReminderSnoozeCount,
    toggleInput,
    openSettings,
    closeSettings,
    openVoiceManager,
    closeVoiceManager,
    toggleFocusMode,
    setNatureMode,
    setPetScale,
    showBreakReminderDialog,
    hideBreakReminderDialog,
    incrementBreakSnooze,
    resetBreakSnooze,
  }
```

- [ ] **Step 4: 提交**

```bash
git add renderer/src/stores/ui.js
git commit -m "feat: add break reminder state to uiStore"
```

---

## Task 4: 实现 `useNatureMode.js`

**Files:**
- Create: `renderer/src/composables/useNatureMode.js`

- [ ] **Step 1: 新建文件**

新建 `renderer/src/composables/useNatureMode.js`，内容如下：

```js
/**
 * useNatureMode
 * 天性模式调度器。当天性模式开启且非专注模式时，每 5-15 分钟随机触发一次宠物行为。
 * 
 * 用法（在 App.vue 中）：
 *   const petCanvasRef = ref(null)
 *   const { init, destroy } = useNatureMode(petCanvasRef)
 *   onMounted(() => init())
 *   onUnmounted(() => destroy())
 */

import { usePetStore, PetState } from '../stores/pet'
import { useUiStore } from '../stores/ui'
import { useChatStore } from '../stores/chat'
import { useSoundManager } from './useSoundManager'

// 预置互动文案池
const NATURE_PHRASES = [
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

// 动作 → 音效映射
const ACTION_SOUNDS = {
  [PetState.BARK]:      'bark_short',
  [PetState.HAPPY_RUN]: 'bark_happy',
  [PetState.CUDDLE]:    'whine',
  [PetState.CUTE]:      'whine',
  [PetState.LICK]:      null,
  [PetState.PEE]:       null,
}

// 随机间隔：5-15 分钟（ms）
function randomInterval() {
  return (5 + Math.random() * 10) * 60 * 1000
}

export function useNatureMode(petCanvasRef) {
  const petStore = usePetStore()
  const uiStore = useUiStore()
  const chatStore = useChatStore()
  const { playSound } = useSoundManager()

  let timer = null

  function scheduleNext() {
    timer = setTimeout(triggerBehavior, randomInterval())
  }

  function triggerBehavior() {
    // 条件检查：天性模式开启且非专注模式
    if (uiStore.natureMode && !uiStore.focusMode) {
      const action = petStore.getRandomBehavior()

      // 1. 触发动画
      if (petCanvasRef.value && petCanvasRef.value.transitionTo) {
        petCanvasRef.value.transitionTo(action)
      }

      // 2. 播放音效
      const soundName = ACTION_SOUNDS[action]
      if (soundName) {
        playSound(soundName)
      }

      // 3. 30% 概率显示预置文案气泡（3秒后自动关闭）
      if (Math.random() < 0.3) {
        const phrase = NATURE_PHRASES[Math.floor(Math.random() * NATURE_PHRASES.length)]
        chatStore.showMessage(phrase, 3000)
      }
    }

    // 无论是否触发，都继续调度下一次
    scheduleNext()
  }

  function init() {
    scheduleNext()
  }

  function destroy() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return { init, destroy }
}
```

- [ ] **Step 2: 提交**

```bash
git add renderer/src/composables/useNatureMode.js
git commit -m "feat: add useNatureMode composable for random behavior scheduling"
```

---

## Task 5: 实现 `useBreakReminder.js`

**Files:**
- Create: `renderer/src/composables/useBreakReminder.js`

- [ ] **Step 1: 新建文件**

新建 `renderer/src/composables/useBreakReminder.js`，内容如下：

```js
/**
 * useBreakReminder
 * 每 45 分钟触发一次休息提醒。用户可推迟最多 2 次（每次推迟 10 分钟）。
 * 
 * 用法（在 App.vue 中）：
 *   const petCanvasRef = ref(null)
 *   const { init, destroy, confirm, snooze } = useBreakReminder(petCanvasRef)
 *   provide('breakReminder', { confirm, snooze })
 *   onMounted(() => init())
 *   onUnmounted(() => destroy())
 */

import { useUiStore } from '../stores/ui'
import { useSoundManager } from './useSoundManager'
import { usePetStore, PetState } from '../stores/pet'

const BREAK_INTERVAL_MS  = 45 * 60 * 1000  // 45 分钟
const SNOOZE_INTERVAL_MS = 10 * 60 * 1000  // 推迟 10 分钟
const MAX_SNOOZES = 2

export function useBreakReminder(petCanvasRef) {
  const uiStore = useUiStore()
  const petStore = usePetStore()
  const { playSound } = useSoundManager()

  let timer = null

  function schedule(delayMs) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(trigger, delayMs)
  }

  function trigger() {
    // 播放提醒音效
    playSound('notification')

    // 宠物切换撒娇动画
    if (petCanvasRef.value && petCanvasRef.value.transitionTo) {
      petCanvasRef.value.transitionTo(PetState.CUDDLE)
    }

    // 显示提醒气泡
    uiStore.showBreakReminderDialog()
  }

  /** 用户点击"好的去休息"：关闭气泡，重置计时器 */
  function confirm() {
    uiStore.hideBreakReminderDialog()
    uiStore.resetBreakSnooze()
    schedule(BREAK_INTERVAL_MS)
  }

  /** 用户点击"再等 10 分钟"：关闭气泡，推迟（最多 MAX_SNOOZES 次） */
  function snooze() {
    uiStore.hideBreakReminderDialog()
    if (uiStore.breakReminderSnoozeCount < MAX_SNOOZES) {
      uiStore.incrementBreakSnooze()
      schedule(SNOOZE_INTERVAL_MS)
    } else {
      // 已推迟 2 次，重置并按正常间隔重新开始
      uiStore.resetBreakSnooze()
      schedule(BREAK_INTERVAL_MS)
    }
  }

  function init() {
    schedule(BREAK_INTERVAL_MS)
  }

  function destroy() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return { init, destroy, confirm, snooze }
}
```

- [ ] **Step 2: 提交**

```bash
git add renderer/src/composables/useBreakReminder.js
git commit -m "feat: add useBreakReminder composable with snooze support"
```

---

## Task 6: 创建 `BreakReminderBubble.vue`

**Files:**
- Create: `renderer/src/components/BreakReminderBubble.vue`

- [ ] **Step 1: 新建文件**

新建 `renderer/src/components/BreakReminderBubble.vue`，内容如下：

```vue
<template>
  <div class="break-reminder-overlay">
    <div class="break-bubble">
      <div class="bubble-content">
        <p class="reminder-text">
          主人，你已经工作 45 分钟了，起来活动一下吧！
        </p>
        <div class="bubble-actions">
          <button class="btn-confirm" @click="onConfirm">好的去休息</button>
          <button class="btn-snooze" @click="onSnooze">再等 10 分钟</button>
        </div>
      </div>
      <div class="bubble-tail"></div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

// App.vue 通过 provide('breakReminder', { confirm, snooze }) 注入
const breakReminder = inject('breakReminder')

function onConfirm() {
  breakReminder.confirm()
}

function onSnooze() {
  breakReminder.snooze()
}
</script>

<style scoped>
.break-reminder-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  pointer-events: none;
}

.break-bubble {
  pointer-events: auto;
  position: relative;
  animation: bubbleIn 0.3s ease-out;
}

.bubble-content {
  background: rgba(255, 255, 255, 0.97);
  border-radius: 18px;
  padding: 16px 20px;
  max-width: 280px;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.reminder-text {
  margin: 0 0 12px 0;
  text-align: center;
}

.bubble-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.btn-confirm,
.btn-snooze {
  padding: 6px 14px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  transition: opacity 0.15s;
}

.btn-confirm:hover,
.btn-snooze:hover {
  opacity: 0.8;
}

.btn-confirm {
  background: #4caf50;
  color: white;
}

.btn-snooze {
  background: #e0e0e0;
  color: #555;
}

.bubble-tail {
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-top: 10px solid rgba(255, 255, 255, 0.97);
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add renderer/src/components/BreakReminderBubble.vue
git commit -m "feat: add BreakReminderBubble component with confirm/snooze actions"
```

---

## Task 7: 修改 `App.vue`，组合所有功能

**Files:**
- Modify: `renderer/src/App.vue`

- [ ] **Step 1: 将 `App.vue` 替换为以下完整内容**

```vue
<template>
  <div class="app-container">
    <PetCanvas ref="petCanvasRef" />
    <ChatBubble v-if="chatStore.showBubble" />
    <InputPanel v-if="uiStore.showInput" />
    
    <!-- 语音录音按钮 -->
    <div class="voice-control" v-if="!uiStore.showInput">
      <VoiceRecorder />
    </div>
    
    <!-- 语音包管理器 -->
    <VoiceManager 
      v-if="uiStore.showVoiceManager" 
      @close="uiStore.closeVoiceManager()"
    />

    <!-- 休息提醒气泡 -->
    <BreakReminderBubble v-if="uiStore.showBreakReminder" />
  </div>
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted } from 'vue'
import { useChatStore } from './stores/chat'
import { useUiStore } from './stores/ui'
import PetCanvas from './components/PetCanvas.vue'
import ChatBubble from './components/ChatBubble.vue'
import InputPanel from './components/InputPanel.vue'
import VoiceRecorder from './components/VoiceRecorder.vue'
import VoiceManager from './components/VoiceManager.vue'
import BreakReminderBubble from './components/BreakReminderBubble.vue'
import { useNatureMode } from './composables/useNatureMode'
import { useBreakReminder } from './composables/useBreakReminder'

const chatStore = useChatStore()
const uiStore = useUiStore()

// PetCanvas ref，传给 composable 以调用 transitionTo()
const petCanvasRef = ref(null)

// 天性模式调度器
const { init: initNature, destroy: destroyNature } = useNatureMode(petCanvasRef)

// 休息提醒（expose confirm/snooze 给 BreakReminderBubble）
const { init: initBreak, destroy: destroyBreak, confirm: breakConfirm, snooze: breakSnooze } = useBreakReminder(petCanvasRef)
provide('breakReminder', { confirm: breakConfirm, snooze: breakSnooze })

onMounted(() => {
  initNature()
  initBreak()

  // Electron 事件监听
  if (window.electronAPI) {
    window.electronAPI.onOpenSettings(() => {
      uiStore.openSettings()
    })
    window.electronAPI.onOpenVoiceManager(() => {
      uiStore.openVoiceManager()
    })
    window.electronAPI.onToggleFocusMode(() => {
      uiStore.toggleFocusMode()
    })
    window.electronAPI.onToggleNatureMode((enabled) => {
      uiStore.setNatureMode(enabled)
    })
  }
})

onUnmounted(() => {
  destroyNature()
  destroyBreak()
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: transparent;
}

.voice-control {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add renderer/src/App.vue
git commit -m "feat: wire up nature mode, break reminder, and sound system in App.vue"
```

---

## Task 8: 集成验证

**目标：** 快速验证三个功能均正常运行（通过临时缩短定时器）。

- [ ] **Step 1: 临时缩短 `useNatureMode.js` 的调度间隔**

将 `randomInterval()` 改为 5-10 秒，方便测试：

```js
function randomInterval() {
  return (5 + Math.random() * 5) * 1000  // 5-10 秒（测试用）
}
```

- [ ] **Step 2: 临时缩短 `useBreakReminder.js` 的提醒间隔**

将 `BREAK_INTERVAL_MS` 改为 10 秒：

```js
const BREAK_INTERVAL_MS  = 10 * 1000  // 10 秒（测试用）
const SNOOZE_INTERVAL_MS =  5 * 1000  // 5 秒（测试用）
```

- [ ] **Step 3: 启动开发服务器并观察**

```bash
# 终端 1
npm run dev

# 终端 2
cd python-service && python main.py

# 终端 3
npm run electron:dev
```

- [ ] **Step 4: 验证天性模式**

- 等待 5-10 秒，观察宠物是否随机触发动作（歪头/撒娇/汪叫）
- 观察浏览器控制台，确认无报错
- 偶尔（约 30% 概率）应出现对话气泡

- [ ] **Step 5: 验证音效**

- 确认系统音量已开启
- 触发天性模式动作时，应听到对应音调（800Hz/600Hz/400Hz）

- [ ] **Step 6: 验证休息提醒**

- 等待约 10 秒，应弹出"主人，你已经工作 45 分钟了"气泡
- 点击"再等 10 分钟"，5 秒后再次弹出（验证推迟功能）
- 再次点击"再等 10 分钟"，5 秒后再次弹出（第二次推迟）
- 再次点击"再等 10 分钟"，此时超过 MAX_SNOOZES，重置为 10 秒后触发（验证上限）
- 点击"好的去休息"，气泡关闭，10 秒后再次触发（验证重置逻辑）

- [ ] **Step 7: 验证专注模式屏蔽天性触发**

在 Electron 右键菜单中开启专注模式，等待超过随机间隔，确认天性模式不再触发动作。

- [ ] **Step 8: 恢复正式定时器时间**

`useNatureMode.js` 恢复：
```js
function randomInterval() {
  return (5 + Math.random() * 10) * 60 * 1000  // 5-15 分钟
}
```

`useBreakReminder.js` 恢复：
```js
const BREAK_INTERVAL_MS  = 45 * 60 * 1000
const SNOOZE_INTERVAL_MS = 10 * 60 * 1000
```

- [ ] **Step 9: 最终提交**

```bash
git add renderer/src/composables/useNatureMode.js renderer/src/composables/useBreakReminder.js
git commit -m "feat: restore production timer intervals after integration testing"
```

---

## 成功标准

- [ ] 天性模式开启时，5-15 分钟内宠物自动触发随机动作（歪头/撒娇/汪叫等）
- [ ] 触发动作时同步播放对应音效（无浏览器报错）
- [ ] 约 30% 概率显示预置文案气泡，3 秒后自动消失
- [ ] 专注模式开启时，天性模式不触发任何行为
- [ ] 45 分钟后显示休息提醒气泡，动画切换为撒娇
- [ ] "好的去休息"按钮关闭气泡并重置 45 分钟计时器
- [ ] "再等 10 分钟"推迟最多 2 次，第 3 次自动重置为 45 分钟计时

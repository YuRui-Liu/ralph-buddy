<template>
  <div class="app-container">
    <!-- 根据动画模式选择渲染组件 -->
    <PetCanvas
      v-if="settings.animationMode === 'bone'"
      ref="petCanvasRef"
    />
    <PoseCanvas
      v-else-if="settings.animationMode === 'rhyfu'"
      ref="poseCanvasRef"
    />
    <ChatBubble v-if="chatStore.showBubble" />
    <InputPanel v-if="uiStore.showInput" />

    <!-- 底部控制栏 -->
    <div class="bottom-bar" v-if="!uiStore.showInput">
      <button class="interact-btn feed-btn" @click="doInteract('feed')" title="喂食">🍖</button>
      <VoiceRecorder />
      <button class="interact-btn play-btn" @click="doInteract('play')" title="玩耍">🎾</button>
    </div>

    <!-- 语音包管理器 -->
    <VoiceManager
      v-if="uiStore.showVoiceManager"
      @close="uiStore.closeVoiceManager()"
    />

    <!-- 休息提醒气泡 -->
    <BreakReminderBubble v-if="uiStore.showBreakReminder" />

    <!-- 记忆管理面板 -->
    <MemoryPanel
      v-if="uiStore.showMemoryPanel"
      @close="uiStore.closeMemoryPanel()"
    />

    <!-- 属性面板 -->
    <AttributesPanel
      v-if="uiStore.showAttributesPanel"
      @close="uiStore.closeAttributesPanel()"
    />

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

    <!-- 设置面板 -->
    <SettingsPanel v-if="uiStore.showSettings" />
  </div>
</template>

<script setup>
import { ref, computed, provide, onMounted, onUnmounted } from 'vue'
import { useChatStore } from './stores/chat'
import { useUiStore } from './stores/ui'
import { useSettingsStore } from './stores/settings'
import { usePetStore } from './stores/pet'
import PetCanvas from './components/PetCanvas.vue'
import PoseCanvas from './components/PoseCanvas.vue'
import ChatBubble from './components/ChatBubble.vue'
import InputPanel from './components/InputPanel.vue'
import VoiceRecorder from './components/VoiceRecorder.vue'
import VoiceManager from './components/VoiceManager.vue'
import BreakReminderBubble from './components/BreakReminderBubble.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import AttributesPanel from './components/AttributesPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import DreamBubble from './components/DreamBubble.vue'
import DreamDiary from './components/DreamDiary.vue'
import { useNatureMode } from './composables/useNatureMode'
import { useBreakReminder } from './composables/useBreakReminder'
import { usePetAttributeTicker } from './composables/usePetAttributeTicker'
import { useEmotionObserver } from './composables/useEmotionObserver'

const chatStore = useChatStore()
const uiStore = useUiStore()
const settings = useSettingsStore()
const petStore = usePetStore()

async function doInteract(action) {
  const port = await window.electronAPI?.getPythonPort?.() || 18765
  try {
    const res = await fetch(`http://127.0.0.1:${port}/api/pet/interact/${action}`, { method: 'POST' })
    if (!res.ok) return
    const attrs = await res.json()
    petStore.applyAttributes(attrs)

    // 触发来福动画反应
    const canvas = activeCanvasRef.value
    if (canvas) {
      if (action === 'feed') {
        chatStore.showMessage('汪！好吃好吃！', 3000)
        if (canvas.transitionTo) canvas.transitionTo('happy_run')
      } else if (action === 'play') {
        chatStore.showMessage('汪汪！好好玩！', 3000)
        if (canvas.trigger) canvas.trigger('excited')
        else if (canvas.transitionTo) canvas.transitionTo('happy_run')
      }
    }
  } catch (e) {
    console.error(`[interact] ${action} failed:`, e)
  }
}

// Canvas ref，传给 composable 以调用 transitionTo()
const petCanvasRef    = ref(null)
const poseCanvasRef   = ref(null)

// 统一代理：始终指向当前激活的 canvas，任意模式均可用
const activeCanvasRef = computed(() => {
  if (settings.animationMode === 'rhyfu')   return poseCanvasRef.value
  return petCanvasRef.value
})

// 包装成 Ref 形式传给需要 .value 的 composable
const activeCanvasProxy = { get value() { return activeCanvasRef.value } }

// 天性模式调度器
const { init: initNature, destroy: destroyNature } = useNatureMode(activeCanvasProxy)

// 休息提醒（expose confirm/snooze 给 BreakReminderBubble）
const { init: initBreak, destroy: destroyBreak, confirm: breakConfirm, snooze: breakSnooze } = useBreakReminder(activeCanvasProxy)
provide('breakReminder', { confirm: breakConfirm, snooze: breakSnooze })

// 情绪观察（需要行为序列器，目前先传 null，PoseCanvas 挂载后注入）
const emotionObserver = useEmotionObserver(null, chatStore)
provide('emotionObserver', emotionObserver)

// 属性定时同步 & 做梦
const { init: initAttrTicker, destroy: destroyAttrTicker } = usePetAttributeTicker()

// 同步模式状态到主进程（右键菜单 checkbox 需要）
function syncModeToMain() {
  if (window.electronAPI?.syncModeState) {
    window.electronAPI.syncModeState({
      natureMode: uiStore.natureMode,
      focusMode:  uiStore.focusMode,
      autoVAD:    settings.autoVAD,
    })
  }
}

onMounted(() => {
  initNature()
  initBreak()
  emotionObserver.init()
  initAttrTicker()

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
      syncModeToMain()
    })
    window.electronAPI.onSetFocusMode((enabled) => {
      uiStore.focusMode = enabled
      syncModeToMain()
    })
    window.electronAPI.onToggleNatureMode((enabled) => {
      uiStore.setNatureMode(enabled)
      syncModeToMain()
    })
    window.electronAPI.onOpenMemory(() => {
      uiStore.openMemoryPanel()
    })
    window.electronAPI.onOpenAttributes(() => {
      uiStore.openAttributesPanel()
    })
    window.electronAPI.onOpenDreamDiary(() => {
      uiStore.openDreamDiary()
    })
    window.electronAPI.onSetAutoVAD((enabled) => {
      settings.autoVAD = enabled
      settings.saveSettings()
      syncModeToMain()
    })
    window.electronAPI.onCloseSettings(() => {
      uiStore.closeSettings()
    })
    // 初始同步模式状态到主进程
    syncModeToMain()

    window.electronAPI.onTriggerBehavior((behaviorId) => {
      const canvas = activeCanvasRef.value
      if (!canvas) return
      // PoseCanvas 有 trigger()（走完整行为序列）；其他模式降级为 transitionTo
      if (typeof canvas.trigger === 'function') {
        canvas.trigger(behaviorId)
      } else if (typeof canvas.transitionTo === 'function') {
        // 行为 id 映射到简单 PetState
        const fallback = {
          scholar: 'cute_pose', investigate: 'cute_pose',
          flatter: 'cuddle',    lickScreen: 'lick_screen',
          pee: 'pee',           sad: 'idle',   bedtime: 'sleep',
        }
        canvas.transitionTo(fallback[behaviorId] || 'idle')
      }
    })
  }
})

onUnmounted(() => {
  destroyNature()
  destroyBreak()
  emotionObserver.destroy()
  destroyAttrTicker()
  if (window.electronAPI) {
    window.electronAPI.removeAllAppListeners()
  }
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: transparent;
}

.bottom-bar {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  opacity: 0.7;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bottom-bar:hover {
  opacity: 1;
}

.interact-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: rgba(102, 126, 234, 0.4);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 0;
}

.interact-btn:hover {
  background: rgba(102, 126, 234, 0.7);
  transform: scale(1.15);
}

.interact-btn:active {
  transform: scale(0.95);
}
</style>

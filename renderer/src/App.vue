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

    <!-- 记忆管理面板 -->
    <MemoryPanel
      v-if="uiStore.showMemoryPanel"
      @close="uiStore.closeMemoryPanel()"
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
import PetCanvas from './components/PetCanvas.vue'
import PoseCanvas from './components/PoseCanvas.vue'
import ChatBubble from './components/ChatBubble.vue'
import InputPanel from './components/InputPanel.vue'
import VoiceRecorder from './components/VoiceRecorder.vue'
import VoiceManager from './components/VoiceManager.vue'
import BreakReminderBubble from './components/BreakReminderBubble.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import { useNatureMode } from './composables/useNatureMode'
import { useBreakReminder } from './composables/useBreakReminder'
import { usePetAttributeTicker } from './composables/usePetAttributeTicker'

const chatStore = useChatStore()
const uiStore = useUiStore()
const settings = useSettingsStore()

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

// 属性定时同步 & 做梦
const { init: initAttrTicker, destroy: destroyAttrTicker } = usePetAttributeTicker()

onMounted(() => {
  initNature()
  initBreak()
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
    })
    window.electronAPI.onToggleNatureMode((enabled) => {
      uiStore.setNatureMode(enabled)
    })
    window.electronAPI.onOpenMemory(() => {
      uiStore.openMemoryPanel()
    })
    window.electronAPI.onCloseSettings(() => {
      uiStore.closeSettings()
    })
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

.voice-control {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
}
</style>

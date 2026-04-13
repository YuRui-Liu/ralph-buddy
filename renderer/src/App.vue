<template>
  <div class="app-container">
    <!-- 根据动画模式选择渲染组件 -->
    <PetCanvas
      v-if="settings.animationMode === 'bone' || settings.animationMode === 'procedural'"
      ref="petCanvasRef"
    />
    <SpriteCanvas
      v-else-if="settings.animationMode === 'sprite'"
      ref="spriteCanvasRef"
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
import { ref, provide, onMounted, onUnmounted } from 'vue'
import { useChatStore } from './stores/chat'
import { useUiStore } from './stores/ui'
import { useSettingsStore } from './stores/settings'
import PetCanvas from './components/PetCanvas.vue'
import SpriteCanvas from './components/SpriteCanvas.vue'
import ChatBubble from './components/ChatBubble.vue'
import InputPanel from './components/InputPanel.vue'
import VoiceRecorder from './components/VoiceRecorder.vue'
import VoiceManager from './components/VoiceManager.vue'
import BreakReminderBubble from './components/BreakReminderBubble.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import { useNatureMode } from './composables/useNatureMode'
import { useBreakReminder } from './composables/useBreakReminder'

const chatStore = useChatStore()
const uiStore = useUiStore()
const settings = useSettingsStore()

// PetCanvas ref，传给 composable 以调用 transitionTo()
const petCanvasRef = ref(null)
const spriteCanvasRef = ref(null)

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
    window.electronAPI.onOpenMemory(() => {
      uiStore.openMemoryPanel()
    })
    window.electronAPI.onCloseSettings(() => {
      uiStore.closeSettings()
    })
  }
})

onUnmounted(() => {
  destroyNature()
  destroyBreak()
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

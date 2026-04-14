<template>
  <div class="sprite-canvas-container" :style="containerStyle">
    <canvas
      ref="canvasRef"
      class="sprite-canvas"
    />

    <!-- 加载状态 -->
    <div v-if="!animator.isReady.value" class="loading-overlay">
      <div class="loading-spinner" />
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSpriteAnimator } from '@/composables/useSpriteAnimator'
import { useSettingsStore } from '@/stores/settings'
import { PetState } from '@/stores/pet'

const props = defineProps({
  width: {
    type: Number,
    default: 400
  },
  height: {
    type: Number,
    default: 500
  }
})

const emit = defineEmits(['click', 'stateChange'])

const canvasRef = ref(null)
const settingsStore = useSettingsStore()
const animator = useSpriteAnimator()

// 容器样式
const containerStyle = computed(() => ({
  width: `${props.width}px`,
  height: `${props.height}px`
}))

// 初始化
onMounted(async () => {
  if (canvasRef.value) {
    // 加载切图资源
    const spritePath = `/sprites/${settingsStore.currentSkin || 'dog'}`
    await animator.loadSprites(spritePath)

    // 初始化渲染
    animator.init(canvasRef.value)
  }
})

// 监听宠物状态变化
watch(() => settingsStore.currentState, (newState) => {
  if (newState && animator.isReady.value) {
    animator.transitionTo(newState)
  }
})

// 暴露方法
defineExpose({
  play: (action) => animator.play(action),
  stop: () => animator.stop(),
  transitionTo: (action) => animator.transitionTo(action),
  blink: () => animator.blink()
})
</script>

<style scoped>
.sprite-canvas-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border-radius: 12px;
  overflow: hidden;
}

.sprite-canvas {
  display: block;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(4px);
  border-radius: 12px;
  color: #666;
  font-size: 14px;
  gap: 12px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e0e0;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

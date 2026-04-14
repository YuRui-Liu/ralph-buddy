<template>
  <div
    ref="containerRef"
    class="pose-canvas-wrap"
    @mousedown="startDrag"
  >
    <canvas ref="canvasRef" class="pose-canvas" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { usePoseAnimator }        from '@/composables/usePoseAnimator'
import { useBehaviorSequencer }   from '@/composables/useBehaviorSequencer'
import { usePetStore, PetState }  from '@/stores/pet'
import { useUiStore }             from '@/stores/ui'
import { useChatStore }           from '@/stores/chat'
import { useSettingsStore }       from '@/stores/settings'

const containerRef = ref(null)
const canvasRef    = ref(null)
const petStore     = usePetStore()
const uiStore      = useUiStore()
const chatStore    = useChatStore()
const settings     = useSettingsStore()

const animator    = usePoseAnimator('/rhyfu/sprites')
const sequencer   = useBehaviorSequencer(animator, chatStore, petStore)

// ─── 拖拽（主进程轮询模式，整个拖拽只需 2 次 IPC） ──────────
let isDragging = false

function startDrag(e) {
  if (uiStore.focusMode) return
  isDragging = true
  animator.setDragging(true)

  const rect = containerRef.value?.getBoundingClientRect()
  window.electronAPI.startDrag({
    clickX: Math.round(e.clientX - rect.left),
    clickY: Math.round(e.clientY - rect.top)
  })

  document.addEventListener('mouseup', stopDrag)
}

function stopDrag() {
  isDragging = false
  animator.setDragging(false)
  window.electronAPI.stopDrag()
  document.removeEventListener('mouseup', stopDrag)
}

// ─── 渲染帧钩子：透明度检测（已改为 mousemove 驱动，无需 rAF 循环） ──

// ─── 状态监听 ──────────────────────────────────────────────
watch(() => petStore.currentState, state => {
  if (animator.isReady.value) {
    animator.transitionTo(state)
  }
})

// 睡眠监听（与 PetCanvas 保持一致）
watch(() => petStore.isSleepy, isSleepy => {
  if (isSleepy) {
    animator.transitionTo(PetState.SLEEP)
  } else if (animator.currentState.value === PetState.SLEEP) {
    animator.transitionTo(PetState.IDLE)
  }
})

// ─── 生命周期 ──────────────────────────────────────────────
onMounted(async () => {
  await animator.loadPoses()
  await nextTick()   // 确保 CSS 布局完成再读尺寸
  animator.init(canvasRef.value)
  window.addEventListener('resize', onResize)

  // 开启行为自动调度
  sequencer.startAutoSchedule()
})

function onResize() {
  animator.resize(canvasRef.value)
}

onUnmounted(() => {
  sequencer.stopAutoSchedule()
  window.removeEventListener('resize', onResize)
  document.removeEventListener('mouseup',  stopDrag)
})

// ─── 暴露给父组件 ──────────────────────────────────────────
defineExpose({
  transitionTo:  (s) => animator.transitionTo(s),
  play:          (s) => animator.play(s),
  stop:          ()  => animator.stop(),
  addProp:       (p) => animator.addProp(p),
  removeProp:    (p) => animator.removeProp(p),
  trigger:       (b) => sequencer.trigger(b),
  notifyInteraction: () => sequencer.notifyInteraction(),
})
</script>

<style scoped>
.pose-canvas-wrap {
  width: 100%;
  height: 100%;
  cursor: grab;
  background: transparent;
}
.pose-canvas-wrap:active { cursor: grabbing; }
.pose-canvas {
  display: block;
  width: 100%;
  height: 100%;
  background: transparent;
}
</style>

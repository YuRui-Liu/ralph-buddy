/**
 * DogBuddy 统一动画控制器
 *
 * 根据设置自动选择骨骼动画模式（来福2D 由 PoseCanvas 独立驱动）
 */

import { computed, watch, ref } from 'vue'
import { useSettingsStore, AnimationMode } from '../stores/settings'
import { useBoneAnimator } from './useBoneAnimator'
import { PetState } from '../stores/pet'

export function usePetAnimationController() {
  const settings = useSettingsStore()

  // 骨骼动画器
  const boneAnimator = useBoneAnimator()

  // 当前动画状态
  const currentAnimState = ref(null)

  // 当前模式
  const currentMode = computed(() => settings.animationMode)

  // 是否骨骼模式
  const isBone = computed(() => currentMode.value === AnimationMode.BONE)

  // ========== 统一播放接口 ==========

  async function play(action, loop = false) {
    currentAnimState.value = action
    return boneAnimator.play(action, loop)
  }

  async function transitionTo(action, duration = 0.3) {
    return play(action, false)
  }

  function stop() {
    boneAnimator.stop()
    currentAnimState.value = null
  }

  function update(time, currentState) {
    boneAnimator.update(time)
  }

  // ========== 模式切换 ==========

  function setMode(mode) {
    settings.setAnimationMode(mode)
  }

  function useBone() {
    setMode(AnimationMode.BONE)
  }

  // ========== 特殊动作 ==========

  function wakeUp() {
    return Promise.resolve()
  }

  // ========== 监听模式变化 ==========

  watch(() => settings.animationMode, (newMode, oldMode) => {
    console.log(`[PetAnimation] 模式切换: ${oldMode} → ${newMode}`)
    stop()
    play(PetState.IDLE)
  })

  // ========== 初始化 ==========

  function init(threeObj) {
    console.log('[PetAnimation] 初始化动画控制器')
    boneAnimator.init(threeObj)
    play(PetState.IDLE)
  }

  // ========== 导出 ==========

  return {
    currentMode,
    isBone,
    currentAnimState,
    init,
    play,
    stop,
    transitionTo,
    update,
    setMode,
    useBone,
    wakeUp,
    _boneAnimator: boneAnimator
  }
}

export default usePetAnimationController

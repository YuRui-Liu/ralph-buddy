/**
 * DogBuddy 骨骼动画器
 *
 * 封装 Three.js AnimationMixer，实现骨骼动画播放
 */

import { ref } from 'vue'
import * as THREE from 'three'
import { PetState } from '../stores/pet'

export function useBoneAnimator() {
  // Three.js 对象引用
  let threeObj = null

  // 当前播放的动画
  const currentAction = ref(null)
  const currentAnimName = ref(null)

  // 动画名称映射（GLB 中的动画名称 -> PetState）
  const animNameMap = {
    idle: PetState.IDLE,
    walk: PetState.WALK,
    sleep: PetState.SLEEP,
    lick: PetState.LICK,
    lick_screen: PetState.LICK,
    cuddle: PetState.CUDDLE,
    cute: PetState.CUTE,
    cute_pose: PetState.CUTE,
    bark: PetState.BARK,
    pee: PetState.PEE,
    happy_run: PetState.HAPPY_RUN,
    run: PetState.HAPPY_RUN
  }

  // ========== 初始化 ==========

  function init(obj) {
    threeObj = obj
    console.log('[BoneAnimator] 初始化')
    if (threeObj.animations) {
      console.log(`[BoneAnimator] 可用动画: ${Object.keys(threeObj.animations).join(', ')}`)
    }
  }

  // ========== 播放控制 ==========

  /**
   * 播放指定动画
   * @param {string} action - 动作名称
   * @param {boolean} loop - 是否循环
   */
  function play(action, loop = false) {
    if (!threeObj?.mixer || !threeObj.animations) {
      console.warn('[BoneAnimator] 动画器未初始化或没有可用动画')
      return Promise.resolve()
    }

    // 查找对应的动画
    const animName = findAnimName(action)

    if (animName && threeObj.animations[animName]) {
      const actionObj = threeObj.animations[animName]

      // 停止当前动画
      if (currentAction.value) {
        currentAction.value.fadeOut(0.3)
      }

      // 播放新动画
      actionObj.reset()
      actionObj.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity)
      actionObj.clampWhenFinished = !loop
      actionObj.fadeIn(0.3).play()

      currentAction.value = actionObj
      currentAnimName.value = animName

      console.log(`[BoneAnimator] 播放: ${animName} (loop: ${loop})`)

      // 如果不是循环动画，动画结束后自动停止
      if (!loop) {
        setupAnimationEndHandler(actionObj)
      }

      return Promise.resolve()
    } else {
      console.warn(`[BoneAnimator] 未找到动画: ${action}`)
      return Promise.resolve()
    }
  }

  /**
   * 查找动画名称
   */
  function findAnimName(action) {
    // 直接匹配
    if (threeObj.animations[action]) {
      return action
    }

    // 通过映射表查找
    const mappedName = animNameMap[action]
    if (mappedName && threeObj.animations[mappedName]) {
      return mappedName
    }

    // 模糊匹配（包含关系）
    const actionLower = action.toLowerCase()
    for (const animName of Object.keys(threeObj.animations)) {
      if (animName.toLowerCase().includes(actionLower) ||
          actionLower.includes(animName.toLowerCase())) {
        return animName
      }
    }

    return null
  }

  /**
   * 设置动画结束处理器
   */
  function setupAnimationEndHandler(actionObj) {
    const onFinish = () => {
      currentAction.value = null
      currentAnimName.value = null
    }

    // 监听动画结束
    actionObj.onFinished = onFinish
  }

  // ========== 停止控制 ==========

  function stop() {
    if (currentAction.value) {
      currentAction.value.stop()
      currentAction.value = null
    }
    currentAnimName.value = null
  }

  /**
   * 过渡到指定动画
   */
  function transitionTo(action, duration = 0.3) {
    return play(action, false)
  }

  // ========== 帧更新 ==========

  function update(delta) {
    if (threeObj?.mixer) {
      threeObj.mixer.update(delta)
    }
  }

  // ========== 导出 ==========

  return {
    currentAction,
    currentAnimName,
    init,
    play,
    stop,
    transitionTo,
    update
  }
}

export default useBoneAnimator

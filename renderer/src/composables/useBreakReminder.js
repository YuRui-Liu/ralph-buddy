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

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // 状态
  const showInput = ref(false)
  const showSettings = ref(false)
  const showVoiceManager = ref(false)
  const focusMode = ref(false)
  const natureMode = ref(true)
  const petScale = ref(1) // 0.8 | 1 | 1.2
  const showBreakReminder = ref(false)
  const breakReminderSnoozeCount = ref(0)

  // 方法
  function toggleInput() {
    showInput.value = !showInput.value
  }

  function openSettings() {
    showSettings.value = true
  }

  function closeSettings() {
    showSettings.value = false
  }

  function openVoiceManager() {
    showVoiceManager.value = true
  }

  function closeVoiceManager() {
    showVoiceManager.value = false
  }

  function toggleFocusMode() {
    focusMode.value = !focusMode.value
  }

  function setNatureMode(enabled) {
    natureMode.value = enabled
  }

  function setPetScale(scale) {
    petScale.value = scale
  }

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
})

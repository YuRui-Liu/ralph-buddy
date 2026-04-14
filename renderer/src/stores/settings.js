import { defineStore } from 'pinia'
import { ref } from 'vue'

// 动画模式枚举
export const AnimationMode = {
  BONE: 'bone',           // 骨骼动画模式 (3D模型)
  RHYFU: 'rhyfu'          // 来福2D姿势模式 (SVG姿势图 + 程序化微动效 + 道具层)
}

export const useSettingsStore = defineStore('settings', () => {
  // ========== 动画模式设置 ==========

  // 当前动画模式，默认来福2D
  const animationMode = ref(AnimationMode.RHYFU)

  // 动作强度系数 (0.5 - 1.5)
  const animationIntensity = ref(1.0)

  // 当前皮肤 (sprite模式下使用)
  const currentSkin = ref('dog')

  // ========== 主题设置 ==========

  // 主题模式: 'light' | 'dark' | 'system'
  const themeMode = ref('system')

  // ========== 声音设置 ==========

  // TTS 音量 (0 - 1)
  const ttsVolume = ref(0.8)

  // 是否启用 TTS
  const ttsEnabled = ref(true)

  // ========== 窗口设置 ==========

  // 窗口透明度 (0.3 - 1)
  const windowOpacity = ref(1.0)

  // 是否始终置顶
  const alwaysOnTop = ref(true)

  // ========== 天性模式设置 ==========

  // 是否启用天性模式
  const natureModeEnabled = ref(true)

  // 天性模式触发间隔（分钟）
  const natureModeInterval = ref(5)

  // ========== 语音设置 ==========

  // 语音自动检测开关（持久化）
  const autoVAD = ref(true)

  // ========== 情绪观察设置 ==========

  const emotionEnabled = ref(false)
  const emotionInterval = ref(10)  // 分钟

  // ========== 方法 ==========

  function setAnimationMode(mode) {
    const valid = Object.values(AnimationMode)
    if (valid.includes(mode)) {
      animationMode.value = mode
      console.log(`[Settings] 动画模式切换: ${mode}`)
    } else {
      console.warn(`[Settings] 未知动画模式: ${mode}，有效值: ${valid.join(', ')}`)
    }
  }

  function setAnimationIntensity(intensity) {
    animationIntensity.value = Math.max(0.5, Math.min(1.5, intensity))
  }

  function setThemeMode(mode) {
    if (['light', 'dark', 'system'].includes(mode)) {
      themeMode.value = mode
      applyTheme(mode)
    }
  }

  function setTtsVolume(volume) {
    ttsVolume.value = Math.max(0, Math.min(1, volume))
  }

  function setWindowOpacity(opacity) {
    windowOpacity.value = Math.max(0.3, Math.min(1, opacity))
    applyWindowOpacity(opacity)
  }

  function toggleAlwaysOnTop() {
    alwaysOnTop.value = !alwaysOnTop.value
    applyAlwaysOnTop(alwaysOnTop.value)
  }

  function toggleNatureMode() {
    natureModeEnabled.value = !natureModeEnabled.value
  }

  // ========== 内部方法 ==========

  function applyTheme(mode) {
    const root = document.documentElement
    if (mode === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
    } else {
      root.setAttribute('data-theme', mode)
    }
  }

  function applyWindowOpacity(opacity) {
    if (window.electronAPI?.setOpacity) {
      window.electronAPI.setOpacity(opacity)
    }
  }

  function applyAlwaysOnTop(enabled) {
    if (window.electronAPI?.setAlwaysOnTop) {
      window.electronAPI.setAlwaysOnTop(enabled)
    }
  }

  // ========== 初始化 ==========

  // 从 localStorage 恢复设置
  function loadSettings() {
    try {
      const saved = localStorage.getItem('dogbuddy_settings')
      if (saved) {
        const settings = JSON.parse(saved)
        if (settings.animationMode) animationMode.value = settings.animationMode
        if (settings.animationIntensity !== undefined) animationIntensity.value = settings.animationIntensity
        if (settings.themeMode) themeMode.value = settings.themeMode
        if (settings.ttsVolume !== undefined) ttsVolume.value = settings.ttsVolume
        if (settings.ttsEnabled !== undefined) ttsEnabled.value = settings.ttsEnabled
        if (settings.windowOpacity !== undefined) windowOpacity.value = settings.windowOpacity
        if (settings.alwaysOnTop !== undefined) alwaysOnTop.value = settings.alwaysOnTop
        if (settings.natureModeEnabled !== undefined) natureModeEnabled.value = settings.natureModeEnabled
        if (settings.natureModeInterval !== undefined) natureModeInterval.value = settings.natureModeInterval
        if (settings.autoVAD !== undefined) autoVAD.value = settings.autoVAD
        if (settings.emotionEnabled !== undefined) emotionEnabled.value = settings.emotionEnabled
        if (settings.emotionInterval !== undefined) emotionInterval.value = settings.emotionInterval
      }
    } catch (e) {
      console.error('[Settings] 加载设置失败:', e)
    }
  }

  // 保存设置到 localStorage
  function saveSettings() {
    try {
      const settings = {
        animationMode: animationMode.value,
        animationIntensity: animationIntensity.value,
        themeMode: themeMode.value,
        ttsVolume: ttsVolume.value,
        ttsEnabled: ttsEnabled.value,
        windowOpacity: windowOpacity.value,
        alwaysOnTop: alwaysOnTop.value,
        natureModeEnabled: natureModeEnabled.value,
        natureModeInterval: natureModeInterval.value,
        autoVAD: autoVAD.value,
        emotionEnabled: emotionEnabled.value,
        emotionInterval: emotionInterval.value,
      }
      localStorage.setItem('dogbuddy_settings', JSON.stringify(settings))
    } catch (e) {
      console.error('[Settings] 保存设置失败:', e)
    }
  }

  // 初始化时加载设置
  loadSettings()

  // 监听变化自动保存
  // 使用 computed 或 watch，这里简化处理

  return {
    // 动画设置
    animationMode,
    animationIntensity,
    currentSkin,
    setAnimationMode,
    setAnimationIntensity,

    // 主题设置
    themeMode,
    setThemeMode,

    // 声音设置
    ttsVolume,
    ttsEnabled,
    setTtsVolume,

    // 窗口设置
    windowOpacity,
    alwaysOnTop,
    setWindowOpacity,
    toggleAlwaysOnTop,

    // 天性模式设置
    natureModeEnabled,
    natureModeInterval,
    toggleNatureMode,

    // 语音设置
    autoVAD,

    // 情绪观察设置
    emotionEnabled,
    emotionInterval,

    // 方法
    loadSettings,
    saveSettings
  }
})

/**
 * useEmotionObserver — 来福偷偷观察主人
 *
 * 管理摄像头截帧、调度（定时/事件/手动三触发）、
 * 结果分发到 petStore 和 behaviorSequencer。
 *
 * 摄像头策略：每次截帧时打开 → 拍一帧 → 立即关闭，不保持常开。
 */

import { watch, onUnmounted } from 'vue'
import { usePetStore } from '../stores/pet'
import { useSettingsStore } from '../stores/settings'
import { apiFetch } from '../utils/api'

// 情绪 → 行为脚本映射
const EMOTION_BEHAVIOR_MAP = {
  happy:    'emotion_happy_react',
  sad:      'emotion_comfort',
  angry:    'emotion_cautious',
  fear:     'emotion_comfort',
  disgust:  'emotion_cautious',
  surprise: 'emotion_curious',
  neutral:  null,
}

export function useEmotionObserver (behaviorSequencer, chatStore) {
  const petStore = usePetStore()
  const settings = useSettingsStore()

  let intervalTimer = null
  let noFaceCount = 0
  let currentInterval = 0

  async function captureFrame () {
    let stream = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      const track = stream.getVideoTracks()[0]
      const imageCapture = new ImageCapture(track)
      const bitmap = await imageCapture.grabFrame()

      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(bitmap, 0, 0)

      return new Promise((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', 0.8)
      })
    } catch (err) {
      console.warn('[EmotionObserver] 摄像头截帧失败:', err.message)
      return null
    } finally {
      if (stream) stream.getTracks().forEach(t => t.stop())
    }
  }

  async function detectEmotion (forceDeep = false) {
    if (petStore.emotionObserver.isObserving) return null

    const eo = petStore.emotionObserver
    eo.isObserving = true

    if (behaviorSequencer && !behaviorSequencer.isRunning.value) {
      behaviorSequencer.trigger('peek_observe')
    }

    try {
      const blob = await captureFrame()
      if (!blob) {
        eo.isObserving = false
        return null
      }

      const formData = new FormData()
      formData.append('image', blob, 'frame.jpg')
      formData.append('deep', forceDeep ? 'true' : 'false')

      const res = await apiFetch('/api/emotion', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const result = await res.json()
      console.log('[EmotionObserver] 检测结果:', result)

      if (result.has_face) {
        noFaceCount = 0
        resetInterval()
        eo.lastEmotion = result.local.emotion
        eo.lastConfidence = result.local.confidence
        eo.lastDetectTime = Date.now()

        if (result.local.emotion && EMOTION_BEHAVIOR_MAP[result.local.emotion]) {
          if (behaviorSequencer && !behaviorSequencer.isRunning.value) {
            behaviorSequencer.trigger(EMOTION_BEHAVIOR_MAP[result.local.emotion])
          }
        }

        const neg = ['sad', 'angry', 'fear', 'disgust']
        if (neg.includes(result.local.emotion)) {
          eo.consecutiveNeg++
        } else {
          eo.consecutiveNeg = 0
        }

        if (result.deep) {
          eo.lastDeepDesc = result.deep.description || ''
          if (result.deep.suggested_speech && chatStore?.showMessage) {
            chatStore.showMessage(result.deep.suggested_speech, 6000)
          }
        }
      } else {
        noFaceCount++
        if (noFaceCount >= 3) {
          slowDownInterval()
        }
      }

      return result
    } catch (err) {
      console.error('[EmotionObserver] 检测请求失败:', err)
      return null
    } finally {
      eo.isObserving = false
    }
  }

  function startSchedule () {
    stopSchedule()
    currentInterval = settings.emotionInterval * 60 * 1000
    intervalTimer = setInterval(() => detectEmotion(false), currentInterval)
    console.log(`[EmotionObserver] 定时观察已启动: 每 ${settings.emotionInterval} 分钟`)
  }

  function stopSchedule () {
    if (intervalTimer) {
      clearInterval(intervalTimer)
      intervalTimer = null
    }
  }

  function resetInterval () {
    if (intervalTimer && currentInterval !== settings.emotionInterval * 60 * 1000) {
      startSchedule()
    }
  }

  function slowDownInterval () {
    stopSchedule()
    currentInterval = Math.min(currentInterval * 2, 30 * 60 * 1000)
    intervalTimer = setInterval(() => detectEmotion(false), currentInterval)
    console.log(`[EmotionObserver] 未检测到人脸，降频: ${Math.round(currentInterval / 60000)} 分钟`)
  }

  function onBeforeChat () {
    if (!settings.emotionEnabled || !petStore.emotionObserver.enabled) return
    const last = petStore.emotionObserver.lastDetectTime
    if (Date.now() - last > 60000) {
      detectEmotion(false)
    }
  }

  function onIdle (idleMs) {
    if (!settings.emotionEnabled || !petStore.emotionObserver.enabled) return
    if (idleMs > 5 * 60 * 1000) {
      detectEmotion(false)
    }
  }

  function manualDetect () {
    return detectEmotion(true)
  }

  async function requestPermission () {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      stream.getTracks().forEach(t => t.stop())
      return true
    } catch {
      return false
    }
  }

  function init () {
    if (settings.emotionEnabled && petStore.emotionObserver.enabled) {
      startSchedule()
    }
  }

  function destroy () {
    stopSchedule()
  }

  watch(() => settings.emotionEnabled, (enabled) => {
    if (enabled && petStore.emotionObserver.enabled) {
      startSchedule()
    } else {
      stopSchedule()
    }
  })

  watch(() => settings.emotionInterval, () => {
    if (intervalTimer) startSchedule()
  })

  onUnmounted(() => destroy())

  return {
    init,
    destroy,
    detectEmotion,
    manualDetect,
    onBeforeChat,
    onIdle,
    requestPermission,
  }
}

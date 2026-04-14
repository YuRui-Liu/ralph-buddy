<template>
  <div class="voice-recorder">
    <button
      class="record-btn"
      :class="{
        'recording': isRecording,
        'processing': isProcessing,
        'speaking': isSpeaking,
        'vad-active': vadListening
      }"
      @click="onMicClick"
      :disabled="isProcessing"
    >
      <span class="icon">{{ buttonIcon }}</span>
      <span v-if="isRecording" class="pulse-ring"></span>
    </button>
    <span class="status-label" :class="statusClass">{{ statusLabel }}</span>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { useSimpleVAD } from '../composables/useSimpleVAD'

const chatStore = useChatStore()
const settings = useSettingsStore()

const isRecording = ref(false)
const isProcessing = ref(false)
const isSpeaking = ref(false)
const statusText = ref('')
const vadListening = ref(false)

let pythonPort = 18765

// ── VAD 实例（浏览器端语音检测）──

const vad = useSimpleVAD({
  onSpeechStart: () => {
    console.log('[VAD] 检测到语音开始')
    isRecording.value = true
    statusText.value = '正在听...'
  },
  onSpeechEnd: async (blob) => {
    console.log('[VAD] 检测到语音结束, blob size:', blob?.size)
    isRecording.value = false
    statusText.value = ''
    if (blob && blob.size > 0) {
      await processVADAudio(blob)
    }
  },
  onVADMisfire: () => {
    console.log('[VAD] 误触发（太短）')
    isRecording.value = false
    statusText.value = '没听清，请重试'
    setTimeout(() => { statusText.value = '' }, 1500)
  }
})

// ── 计算属性 ──

const buttonIcon = computed(() => {
  if (isProcessing.value) return '⏳'
  if (isSpeaking.value) return '🔊'
  if (isRecording.value) return '🔴'
  if (vadListening.value) return '🎤'
  return '🎤'
})

const statusLabel = computed(() => {
  if (statusText.value) return statusText.value
  if (isProcessing.value) return '思考中'
  if (isSpeaking.value) return '说话中'
  if (isRecording.value) return '聆听中...'
  if (vadListening.value) return '说话即可'
  return '点击说话'
})

const statusClass = computed(() => {
  if (isRecording.value) return 'recording'
  if (isProcessing.value) return 'processing'
  if (isSpeaking.value) return 'speaking'
  return ''
})

// ── 按钮点击 ──

async function onMicClick() {
  if (isProcessing.value || isSpeaking.value) return

  if (settings.autoVAD) {
    // VAD 模式：点击切换监听开关
    if (vadListening.value) {
      await stopVAD()
    } else {
      await startVAD()
    }
  } else {
    // 手动模式：点击开始/停止 Python 录音
    if (isRecording.value) {
      await stopAndTranscribe()
    } else {
      await startRecording()
    }
  }
}

// ── VAD 模式 ──

async function startVAD() {
  try {
    await vad.start()
    vadListening.value = true
    console.log('[VAD] 自动监听已启动')
  } catch (e) {
    console.error('[VAD] 启动失败:', e)
    statusText.value = 'VAD启动失败'
    setTimeout(() => { statusText.value = '' }, 2000)
  }
}

function stopVAD() {
  vad.stop()
  vadListening.value = false
  isRecording.value = false
  console.log('[VAD] 自动监听已停止')
}

async function processVADAudio(blob) {
  // 暂停 VAD 防止 TTS 播放时误触
  vad.pause()
  isProcessing.value = true
  statusText.value = '识别中...'

  try {
    // Step 1: STT
    const formData = new FormData()
    formData.append('audio', blob, 'recording.wav')
    formData.append('language', 'zh')

    const sttRes = await fetch(`http://127.0.0.1:${pythonPort}/api/stt`, {
      method: 'POST',
      body: formData
    })
    if (!sttRes.ok) throw new Error(`STT 失败: ${sttRes.status}`)

    const sttResult = await sttRes.json()
    const userText = sttResult.text?.trim()
    if (!userText) {
      statusText.value = '没听清，请重试'
      return
    }

    chatStore.addMessage('user', userText)
    statusText.value = `你: "${userText}"`

    // Step 2: Chat
    statusText.value = '来福思考中...'
    const chatRes = await fetch(`http://127.0.0.1:${pythonPort}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    })
    if (!chatRes.ok) throw new Error(`Chat 失败: ${chatRes.status}`)

    const chatData = await chatRes.json()
    const replyText = chatData.reply
    if (!replyText) throw new Error('没有收到回复')

    chatStore.addMessage('assistant', replyText)
    chatStore.showMessage(replyText, 6000)

    // Step 3: TTS
    await playResponse(replyText)

  } catch (e) {
    console.error('[VAD] 语音对话失败:', e)
    statusText.value = '出错了，请重试'
  } finally {
    isProcessing.value = false
    if (!statusText.value.startsWith('出错')) {
      statusText.value = ''
    }
    // 恢复 VAD 监听
    await vad.resume()
  }
}

// ── 手动模式（Python 后端录音）──

async function startRecording() {
  try {
    const res = await fetch(`http://127.0.0.1:${pythonPort}/api/mic/start`, { method: 'POST' })
    const data = await res.json()
    if (data.status === 'recording' || data.status === 'already_recording') {
      isRecording.value = true
      statusText.value = ''
    }
  } catch (e) {
    console.error('[Manual] 启动录音失败:', e)
    statusText.value = '录音启动失败'
    setTimeout(() => { statusText.value = '' }, 2000)
  }
}

async function stopAndTranscribe() {
  isRecording.value = false
  isProcessing.value = true
  statusText.value = '识别中...'

  try {
    const res = await fetch(`http://127.0.0.1:${pythonPort}/api/mic/stop`, { method: 'POST' })
    const data = await res.json()

    if (!data.text || data.text.trim() === '') {
      statusText.value = '没听清，请重试'
      setTimeout(() => { statusText.value = '' }, 2000)
      return
    }

    const userText = data.text.trim()
    chatStore.addMessage('user', userText)
    statusText.value = `你: "${userText}"`

    statusText.value = '来福思考中...'
    const chatRes = await fetch(`http://127.0.0.1:${pythonPort}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    })
    if (!chatRes.ok) throw new Error(`Chat 失败: ${chatRes.status}`)

    const chatData = await chatRes.json()
    const replyText = chatData.reply
    if (!replyText) throw new Error('没有收到回复')

    chatStore.addMessage('assistant', replyText)
    chatStore.showMessage(replyText, 6000)

    await playResponse(replyText)

  } catch (e) {
    console.error('[Manual] 语音对话失败:', e)
    statusText.value = '出错了，请重试'
  } finally {
    isProcessing.value = false
    if (!statusText.value.startsWith('出错')) {
      statusText.value = ''
    }
  }
}

// ── TTS 播放 ──

async function playResponse(text) {
  try {
    isSpeaking.value = true
    statusText.value = '来福说话中...'

    const formData = new FormData()
    formData.append('text', text)

    const response = await fetch(`http://127.0.0.1:${pythonPort}/api/tts`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error(`TTS 失败: ${response.status}`)

    const contentType = response.headers.get('content-type') || 'audio/mpeg'
    const audioBlob = new Blob([await response.arrayBuffer()], { type: contentType })
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)

    await new Promise((resolve) => {
      audio.onended = () => { URL.revokeObjectURL(audioUrl); resolve() }
      audio.onerror = () => { URL.revokeObjectURL(audioUrl); resolve() }
      audio.play().catch(resolve)
    })
  } catch (e) {
    console.error('[TTS] 播放失败:', e)
  } finally {
    isSpeaking.value = false
    statusText.value = ''
  }
}

// ── autoVAD 设置变化 ──

watch(() => settings.autoVAD, (enabled) => {
  if (enabled) {
    startVAD()
  } else {
    stopVAD()
  }
})

// ── 生命周期 ──

onMounted(async () => {
  pythonPort = await window.electronAPI?.getPythonPort?.() || 18765

  // 如果 autoVAD 已启用，自动开始监听
  if (settings.autoVAD) {
    await startVAD()
  }

  // Ctrl+P 快捷键
  if (window.electronAPI?.onToggleRecording) {
    window.electronAPI.onToggleRecording(() => onMicClick())
  }
})

onUnmounted(() => {
  if (vadListening.value) {
    vad.stop()
  }
  if (isRecording.value && !settings.autoVAD) {
    fetch(`http://127.0.0.1:${pythonPort}/api/mic/cancel`, { method: 'POST' }).catch(() => {})
  }
})
</script>

<style scoped>
.voice-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.record-btn {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(102, 126, 234, 0.55);
  color: white;
  cursor: pointer;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.record-btn:hover {
  background: rgba(102, 126, 234, 0.8);
  transform: scale(1.1);
}

.record-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.record-btn.recording {
  background: rgba(245, 87, 108, 0.7);
}

.record-btn.processing {
  background: rgba(79, 172, 254, 0.7);
}

.record-btn.speaking {
  background: rgba(67, 233, 123, 0.7);
}

.record-btn.vad-active {
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.4);
}

.icon {
  font-size: 16px;
  line-height: 1;
}

.pulse-ring {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid rgba(245, 87, 108, 0.6);
  animation: pulse-expand 1.2s ease-out infinite;
  pointer-events: none;
}

@keyframes pulse-expand {
  0%   { transform: scale(1);   opacity: 0.8; }
  100% { transform: scale(1.6); opacity: 0; }
}

.status-label {
  font-size: 10px;
  color: rgba(102, 102, 102, 0.8);
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s;
}

.status-label.recording {
  color: rgba(245, 87, 108, 0.9);
}

.status-label.processing {
  color: rgba(79, 172, 254, 0.9);
}

.status-label.speaking {
  color: rgba(67, 233, 123, 0.9);
}
</style>

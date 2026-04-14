<template>
  <div class="voice-recorder">
    <!-- 录音按钮 -->
    <button
      class="record-btn"
      :class="{ 
        'recording': isRecording, 
        'processing': isProcessing,
        'speaking': isSpeaking 
      }"
      @mousedown="startRecording"
      @mouseup="stopRecording"
      @mouseleave="stopRecording"
      @touchstart.prevent="startRecording"
      @touchend.prevent="stopRecording"
      :disabled="isProcessing"
    >
      <div class="btn-content">
        <span class="icon">{{ buttonIcon }}</span>
        <span class="text">{{ buttonText }}</span>
      </div>
      
      <!-- 录音波形动画 -->
      <div v-if="isRecording" class="wave-animation">
        <span v-for="i in 5" :key="i" :style="{ animationDelay: `${i * 0.1}s` }"></span>
      </div>
      
      <!-- 处理中旋转 -->
      <div v-if="isProcessing" class="spinner"></div>
    </button>
    
    <!-- 状态提示 -->
    <div class="status-hint" :class="statusClass">
      {{ statusHint }}
    </div>
    
    <!-- 音量指示器 -->
    <div v-if="isRecording" class="volume-indicator">
      <div class="volume-bar" :style="{ width: `${volume * 100}%` }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { usePetStore } from '../stores/pet'
import { useUiStore } from '../stores/ui'
import { useSimpleVAD } from '../composables/useSimpleVAD'

const chatStore = useChatStore()
const petStore = usePetStore()
const uiStore = useUiStore()

// 状态
const isRecording = ref(false)
const isProcessing = ref(false)
const isSpeaking = ref(false)
const volume = ref(0)
const statusText = ref('')

// 手动录音相关（VAD 不可用时的 fallback）
let manualRecording = false

// 计算属性
const buttonIcon = computed(() => {
  if (isProcessing.value) return '⏳'
  if (isSpeaking.value) return '🔊'
  if (isRecording.value) return '⏹️'
  return '🎤'
})

const buttonText = computed(() => {
  if (isProcessing.value) return '思考中...'
  if (isSpeaking.value) return '说话中...'
  if (isRecording.value) return '聆听中...'
  return '待命'
})

const statusHint = computed(() => {
  return statusText.value || '对我说话即可，无需按键'
})

const statusClass = computed(() => {
  if (isRecording.value) return 'recording'
  if (isProcessing.value) return 'processing'
  if (isSpeaking.value) return 'speaking'
  return ''
})

// 初始化 VAD - 基于 Web Audio 能量检测，无需 WASM/ORT
const vad = useSimpleVAD({
  onSpeechStart: () => {
    console.log('🎤 检测到语音开始')
    isRecording.value = true
    statusText.value = '正在听...'
  },
  onSpeechEnd: async (blob) => {
    console.log('🎤 检测到语音结束')
    isRecording.value = false
    statusText.value = ''
    await processAudioBlob(blob)
  },
  onVADMisfire: () => {
    console.log('🎤 VAD 误触发')
    isRecording.value = false
    statusText.value = '没听清，请重试'
    setTimeout(() => { statusText.value = '' }, 1500)
  }
})

async function initVAD() {
  statusText.value = '初始化中...'
  try {
    await vad.start()
    statusText.value = ''
    console.log('✅ VAD 初始化完成，常驻监听中')
  } catch (error) {
    console.error('❌ VAD 初始化失败:', error)
    statusText.value = '按住说话（VAD不可用）'
  }
}

// 手动录音：按下按钮时触发 VAD 的录音流程
// VAD 的 ScriptProcessorNode 已经在持续捕获 PCM，这里只需模拟 speech start/end
function startRecording() {
  if (isProcessing.value || isRecording.value) return
  // 不做额外操作——VAD 自动检测即可。
  // 按钮仅作为视觉反馈，实际录音由 VAD 全权管理。
  statusText.value = '请说话，VAD 会自动检测...'
}

function stopRecording() {
  // VAD 模式下无需手动停止
}

// 统一处理音频 Blob（VAD 直接输出 WAV，无需额外转换）
async function processAudioBlob(blob) {
  if (!blob || blob.size === 0) {
    statusText.value = '录音太短，请重试'
    return
  }

  // 暂停 VAD：防止处理/TTS 播放期间扬声器声音抬高背景噪声阈值
  vad.pause()

  isProcessing.value = true
  statusText.value = '识别中...'

  try {
    console.log(`🎤 发送音频: ${blob.size} bytes, type=${blob.type}`)

    const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765

    // Step 1: STT — VAD 输出的已经是 WAV
    const formData = new FormData()
    formData.append('audio', blob, 'recording.wav')
    formData.append('language', 'zh')

    const sttRes = await fetch(`http://127.0.0.1:${pythonPort}/api/stt`, {
      method: 'POST',
      body: formData
    })
    if (!sttRes.ok) throw new Error(`STT 请求失败: ${sttRes.status}`)

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
    if (!chatRes.ok) throw new Error(`Chat 请求失败: ${chatRes.status}`)

    const chatData = await chatRes.json()
    const replyText = chatData.reply
    if (!replyText) throw new Error('没有收到回复')

    chatStore.addMessage('assistant', replyText)
    chatStore.showMessage(replyText, 6000)

    // Step 3: TTS
    await playResponse(replyText)

  } catch (error) {
    console.error('❌ 语音对话失败:', error)
    statusText.value = '出错了，请重试'
  } finally {
    isProcessing.value = false
    statusText.value = ''
    // 恢复 VAD 监听，重新估算背景噪声基线
    await vad.resume()
  }
}

// 播放回复语音（使用来福专属声音）
async function playResponse(text) {
  try {
    isSpeaking.value = true
    statusText.value = "来福说话中..."

    const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765

    const formData = new FormData()
    formData.append('text', text)
    // voice_id 留空，后端默认用 laifu-clone（若已启动）

    const response = await fetch(`http://127.0.0.1:${pythonPort}/api/tts`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) throw new Error(`TTS 请求失败: ${response.status}`)

    const contentType = response.headers.get('content-type') || 'audio/mpeg'
    const audioBlob = new Blob([await response.arrayBuffer()], { type: contentType })
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)

    await new Promise((resolve) => {
      audio.onended = () => { URL.revokeObjectURL(audioUrl); resolve() }
      audio.onerror = () => { URL.revokeObjectURL(audioUrl); resolve() }
      audio.play().catch(resolve)
    })

  } catch (error) {
    console.error("❌ 语音播放失败:", error)
  } finally {
    isSpeaking.value = false
    statusText.value = ""
  }
}

// 生命周期
onMounted(() => {
  initVAD()
})

onUnmounted(() => {
  stopRecording()
  vad.stop()
})
</script>

<style scoped>
.voice-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.record-btn {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  overflow: hidden;
}

.record-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.record-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.record-btn.recording {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  animation: pulse 1s infinite;
}

.record-btn.processing {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.record-btn.speaking {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.btn-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.icon {
  font-size: 24px;
}

.text {
  font-size: 11px;
  font-weight: 500;
}

/* 波形动画 */
.wave-animation {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 2px;
}

.wave-animation span {
  width: 3px;
  height: 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 2px;
  animation: wave 0.5s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1); }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 87, 108, 0.4); }
  50% { box-shadow: 0 0 0 15px rgba(245, 87, 108, 0); }
}

/* 旋转动画 */
.spinner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 状态提示 */
.status-hint {
  font-size: 12px;
  color: #666;
  text-align: center;
  min-height: 18px;
  transition: color 0.3s;
}

.status-hint.recording {
  color: #f5576c;
}

.status-hint.processing {
  color: #00f2fe;
}

.status-hint.speaking {
  color: #43e97b;
}

/* 音量指示器 */
.volume-indicator {
  width: 100px;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.volume-bar {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.05s ease;
}
</style>

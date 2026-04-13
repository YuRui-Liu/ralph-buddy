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
import { useUiStore } from '../stores/ui'

const chatStore = useChatStore()
const uiStore = useUiStore()

// 状态
const isRecording = ref(false)
const isProcessing = ref(false)
const isSpeaking = ref(false)
const isReady = ref(false)
const volume = ref(0)
const statusText = ref('')

// VAD 和录音相关
let vadInstance = null
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let volumeInterval = null

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

// 初始化 VAD - 常驻监听，无需按键
async function initVAD() {
  statusText.value = "初始化中..."
  try {
    if (!window.vad?.MicVAD) throw new Error("VAD 脚本未加载，请刷新页面")
    if (!window.ort) throw new Error("ONNX Runtime 未加载，请刷新页面")
    
    const { MicVAD } = window.vad
    const ort = window.ort

    const isDev = window.location.protocol === 'http:'

    // WASM 路径策略：
    //   Electron dev 模式 → onnxWASMBasePath 用 file:// 绝对路径
    //     ORT 内部 ja(b)=b.startsWith("file://") 为 true → 跳过 streaming compile
    //     同时预加载 wasmBinary（HTTP fetch），ORT 的 La() 直接用 binary，不再尝试 fetch(file://)
    //     （COEP:require-corp 会阻断跨协议 file:// fetch，这是上次 AbortError 的根因）
    //   Electron prod / 浏览器 → 保持相对路径，file:// 页面下 Chromium 本身处理正确
    let onnxWASMBasePath
    let modelURL

    if (isDev && window.electronAPI?.getVadBasePath) {
      onnxWASMBasePath = await window.electronAPI.getVadBasePath()  // file:// 路径

      // 预加载 WASM binary（via HTTP，避免 COEP 阻断 file:// fetch）
      // ORT La() 检测到 wasmBinary 非空时直接 instantiate，不再发起 fetch
      try {
        const wasmBuf = await fetch('/vad/ort-wasm-simd-threaded.wasm').then(r => r.arrayBuffer())
        ort.env.wasm.wasmBinary = wasmBuf
      } catch (e) {
        // 预加载失败：onnxWASMBasePath 回退到 HTTP，避免 La() fetch(file://) 被 COEP 阻断
        console.warn('[VAD] WASM 预加载失败，回退 HTTP 路径', e)
        onnxWASMBasePath = `${window.location.origin}/vad/`
      }

      // modelURL 始终用 HTTP（file:// fetch 会被 COEP 阻断 → AbortError）
      modelURL = '/vad/silero_vad_legacy.onnx'
    } else {
      // prod（页面本身是 file://，相对路径即 file://） 或非 Electron 环境
      onnxWASMBasePath = isDev ? `${window.location.origin}/vad/` : './vad/'
      modelURL = isDev ? '/vad/silero_vad_legacy.onnx' : './vad/silero_vad_legacy.onnx'
    }

    vadInstance = await MicVAD.new({
      ort: ort,
      onnxWASMBasePath,
      modelURL,
      minSpeechFrames: 3,
      maxSpeechFrames: 300,
      positiveSpeechThreshold: 0.5,
      negativeSpeechThreshold: 0.35,
      onSpeechStart: () => {
        console.log("🎤 检测到语音开始")
        isRecording.value = true
        statusText.value = "正在听..."
      },
      onSpeechEnd: async (audio) => {
        console.log("🎤 检测到语音结束")
        isRecording.value = false
        statusText.value = ""
        await handleSpeechEnd(audio)
      },
      onVADMisfire: () => {
        console.log("🎤 VAD 误触发")
        isRecording.value = false
        statusText.value = "没听清，请重试"
        setTimeout(() => { statusText.value = "" }, 1500)
      }
    })

    await vadInstance.start()
    isReady.value = true
    statusText.value = ""
    console.log("✅ VAD 初始化完成，常驻监听中")
  } catch (error) {
    console.error("❌ VAD 初始化失败:", error)
    statusText.value = "按住说话（VAD不可用）"
    isReady.value = true
  }
}

// 开始录音
async function startRecording() {
  if (isProcessing.value || isRecording.value) return
  
  try {
    // 请求麦克风权限
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    })
    
    // 创建 MediaRecorder
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    })
    
    audioChunks = []
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }
    
    mediaRecorder.onstop = () => {
      handleRecordingStop()
    }
    
    // 开始录音
    mediaRecorder.start(100) // 每100ms收集一次数据
    isRecording.value = true
    statusText.value = "正在录音..."
    
    // 启动音量检测
    startVolumeDetection(stream)
    
  } catch (error) {
    console.error("❌ 录音启动失败:", error)
    statusText.value = "无法访问麦克风"
  }
}

// 停止录音
function stopRecording() {
  if (!isRecording.value || !mediaRecorder) return
  
  mediaRecorder.stop()
  isRecording.value = false
  
  // 停止所有音轨
  mediaRecorder.stream.getTracks().forEach(track => track.stop())
  
  // 停止音量检测
  stopVolumeDetection()
}

// 处理录音停止
async function handleRecordingStop() {
  if (audioChunks.length === 0) {
    statusText.value = "录音太短，请重试"
    return
  }

  isProcessing.value = true
  statusText.value = "识别中..."

  try {
    const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765

    // Step 1: STT — 识别用户说的话
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    formData.append('language', 'zh')

    const sttRes = await fetch(`http://127.0.0.1:${pythonPort}/api/stt`, {
      method: 'POST',
      body: formData
    })
    if (!sttRes.ok) throw new Error(`STT 请求失败: ${sttRes.status}`)

    const sttResult = await sttRes.json()
    const userText = sttResult.text?.trim()
    if (!userText) {
      statusText.value = "没听清，请重试"
      return
    }

    // 记录用户消息到聊天记录
    chatStore.addMessage('user', userText)
    statusText.value = `你: "${userText}"`

    // Step 2: Chat — 获取来福的回复
    statusText.value = "来福思考中..."
    const chatRes = await fetch(`http://127.0.0.1:${pythonPort}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    })
    if (!chatRes.ok) throw new Error(`Chat 请求失败: ${chatRes.status}`)

    const chatData = await chatRes.json()
    const replyText = chatData.reply
    if (!replyText) throw new Error("没有收到回复")

    // 显示来福回复气泡
    chatStore.addMessage('assistant', replyText)
    chatStore.showMessage(replyText, 6000)

    // Step 3: TTS — 用来福专属声音播放回复
    await playResponse(replyText)

  } catch (error) {
    console.error("❌ 语音对话失败:", error)
    statusText.value = "出错了，请重试"
  } finally {
    isProcessing.value = false
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

// 音量检测
function startVolumeDetection(stream) {
  audioContext = new (window.AudioContext || window.webkitAudioContext)()
  analyser = audioContext.createAnalyser()
  analyser.fftSize = 256
  
  const source = audioContext.createMediaStreamSource(stream)
  source.connect(analyser)
  
  const dataArray = new Uint8Array(analyser.frequencyBinCount)
  
  volumeInterval = setInterval(() => {
    analyser.getByteFrequencyData(dataArray)
    
    // 计算平均音量
    let sum = 0
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i]
    }
    const average = sum / dataArray.length
    volume.value = Math.min(average / 128, 1) // 归一化到 0-1
  }, 50)
}

function stopVolumeDetection() {
  if (volumeInterval) {
    clearInterval(volumeInterval)
    volumeInterval = null
  }
  if (audioContext) {
    audioContext.close()
    audioContext = null
  }
  volume.value = 0
}

// 处理 VAD 语音结束
async function handleSpeechEnd(audio) {
  // 将 Float32Array 转换为 WAV 格式
  const wavBlob = float32ToWav(audio, 16000)
  audioChunks = [wavBlob]
  await handleRecordingStop()
}

// Float32Array 转 WAV
function float32ToWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  
  // WAV 头
  const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }
  
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)
  
  // 写入音频数据
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]))
    s = s < 0 ? s * 0x8000 : s * 0x7FFF
    view.setInt16(offset, s, true)
    offset += 2
  }
  
  return new Blob([buffer], { type: 'audio/wav' })
}

// 生命周期
onMounted(() => {
  initVAD()
})

onUnmounted(() => {
  stopRecording()
  stopVolumeDetection()
  if (vadInstance) {
    vadInstance.pause()
    vadInstance.destroy()
    vadInstance = null
  }
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

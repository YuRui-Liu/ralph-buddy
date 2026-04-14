<template>
  <div class="voice-wizard-overlay" @click.self="close">
    <div class="voice-wizard">
      <!-- 标题栏 -->
      <div class="wizard-header">
        <h3>🎙️ 制作宠物语音包</h3>
        <button class="close-btn" @click="close">×</button>
      </div>
      
      <!-- 步骤指示器 -->
      <div class="step-indicator">
        <div 
          v-for="(step, index) in steps" 
          :key="index"
          class="step"
          :class="{ active: currentStep === index, completed: currentStep > index }"
        >
          <div class="step-number">{{ index + 1 }}</div>
          <div class="step-label">{{ step.label }}</div>
        </div>
        <div class="step-line" :style="{ width: `${(currentStep / (steps.length - 1)) * 100}%` }"></div>
      </div>
      
      <!-- 步骤内容 -->
      <div class="wizard-content">
        <!-- 步骤 1: 选择方式 -->
        <div v-if="currentStep === 0" class="step-content">
          <h4>选择语音包制作方式</h4>
          
          <div class="option-cards">
            <div 
              class="option-card"
              :class="{ selected: createMethod === 'edge' }"
              @click="createMethod = 'edge'"
            >
              <div class="card-icon">☁️</div>
              <div class="card-title">使用 Edge TTS</div>
              <div class="card-desc">
                快速简单，无需训练<br>
                使用微软在线语音<br>
                多种音色可选
              </div>
            </div>
            
            <div 
              class="option-card"
              :class="{ selected: createMethod === 'clone' }"
              @click="createMethod = 'clone'"
            >
              <div class="card-icon">🎭</div>
              <div class="card-title">克隆你的声音</div>
              <div class="card-desc">
                个性化定制<br>
                需要 30秒-2分钟 录音<br>
                训练时间约 5-10 分钟
              </div>
            </div>
          </div>
        </div>
        
        <!-- 步骤 2: 配置 -->
        <div v-if="currentStep === 1" class="step-content">
          <!-- Edge TTS 配置 -->
          <template v-if="createMethod === 'edge'">
            <h4>选择语音</h4>
            <div class="voice-grid">
              <div
                v-for="voice in edgeVoices"
                :key="voice.short_name"
                class="voice-item"
                :class="{ selected: selectedVoice === voice.short_name }"
                @click="selectedVoice = voice.short_name"
              >
                <div class="voice-name">{{ voice.short_name }}</div>
                <div class="voice-preview">
                  <button @click.stop="previewVoice(voice.short_name)">
                    {{ isPreviewing ? '⏹️' : '▶️' }}
                  </button>
                </div>
              </div>
            </div>
            
            <div class="form-group">
              <label>语音包名称</label>
              <input 
                v-model="packageName" 
                placeholder="例如：晓晓语音"
                class="form-input"
              />
            </div>
          </template>
          
          <!-- 克隆配置 -->
          <template v-if="createMethod === 'clone'">
            <h4>录制参考音频</h4>
            
            <div class="recording-section">
              <div class="recording-tips">
                <p>💡 录音提示：</p>
                <ul>
                  <li>在安静的环境中录音</li>
                  <li>距离麦克风 10-20 厘米</li>
                  <li>语速适中，吐字清晰</li>
                  <li>建议时长 30秒-2分钟</li>
                </ul>
              </div>
              
              <div class="recording-area">
                <div v-if="!recordedAudio" class="record-placeholder">
                  <button 
                    class="record-btn-large"
                    :class="{ recording: isRecording }"
                    @mousedown="startRecording"
                    @mouseup="stopRecording"
                    @mouseleave="stopRecording"
                  >
                    <span class="record-icon">{{ isRecording ? '⏹️' : '🎙️' }}</span>
                    <span class="record-text">
                      {{ isRecording ? `录音中 ${recordingTime}s` : '按住录音' }}
                    </span>
                  </button>
                  
                  <!-- 录音波形 -->
                  <div v-if="isRecording" class="recording-wave">
                    <span v-for="i in 20" :key="i" :style="{ height: `${Math.random() * 100}%` }"></span>
                  </div>
                </div>
                
                <div v-else class="recorded-preview">
                  <audio :src="recordedAudioUrl" controls></audio>
                  <div class="preview-actions">
                    <button @click="reRecord">重新录制</button>
                    <button @click="uploadAudio" class="primary">使用这段录音</button>
                  </div>
                </div>
              </div>
              
              <div class="form-group">
                <label>语音包名称</label>
                <input 
                  v-model="packageName" 
                  placeholder="例如：我的声音"
                  class="form-input"
                />
              </div>
            </div>
          </template>
        </div>
        
        <!-- 步骤 3: 处理/训练 -->
        <div v-if="currentStep === 2" class="step-content">
          <div class="processing-status">
            <div v-if="createMethod === 'edge'" class="success-state">
              <div class="success-icon">✅</div>
              <h4>语音包创建成功！</h4>
              <p>Edge TTS 语音包已准备就绪</p>
            </div>
            
            <div v-else class="training-state">
              <div v-if="trainingStatus === 'uploading'">
                <div class="spinner-large"></div>
                <h4>上传音频中...</h4>
              </div>
              
              <div v-else-if="trainingStatus === 'processing'">
                <div class="spinner-large"></div>
                <h4>音频预处理中...</h4>
                <p>降噪、标准化、分割...</p>
              </div>
              
              <div v-else-if="trainingStatus === 'training'">
                <div class="spinner-large"></div>
                <h4>模型训练中...</h4>
                <p>这可能需要 5-10 分钟</p>
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: `${trainingProgress}%` }"></div>
                </div>
              </div>
              
              <div v-else-if="trainingStatus === 'completed'">
                <div class="success-icon">🎉</div>
                <h4>训练完成！</h4>
                <p>你的专属语音包已就绪</p>
              </div>
              
              <div v-else-if="trainingStatus === 'error'">
                <div class="error-icon">❌</div>
                <h4>训练失败</h4>
                <p>{{ errorMessage }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 底部按钮 -->
      <div class="wizard-footer">
        <button 
          v-if="currentStep > 0" 
          class="btn-secondary"
          @click="prevStep"
          :disabled="isProcessing"
        >
          上一步
        </button>
        
        <button 
          v-if="currentStep < steps.length - 1"
          class="btn-primary"
          @click="nextStep"
          :disabled="!canProceed || isProcessing"
        >
          {{ nextButtonText }}
        </button>
        
        <button 
          v-else
          class="btn-primary"
          @click="finish"
          :disabled="trainingStatus === 'training' || trainingStatus === 'uploading' || trainingStatus === 'processing'"
        >
          完成
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { apiFetch } from '@/utils/api'

const emit = defineEmits(['close', 'created'])

// 步骤配置
const steps = [
  { label: '选择方式' },
  { label: '配置' },
  { label: '完成' }
]

// 状态
const currentStep = ref(0)
const createMethod = ref('edge')
const packageName = ref('')
const selectedVoice = ref('xiaoxiao')
const isProcessing = ref(false)

// Edge TTS 语音列表
const edgeVoices = ref([
  { short_name: 'xiaoxiao', full_name: 'zh-CN-XiaoxiaoNeural' },
  { short_name: 'xiaoyi', full_name: 'zh-CN-XiaoyiNeural' },
  { short_name: 'yunjian', full_name: 'zh-CN-YunjianNeural' },
  { short_name: 'yunxi', full_name: 'zh-CN-YunxiNeural' },
  { short_name: 'xiaochen', full_name: 'zh-CN-XiaochenNeural' },
  { short_name: 'xiaohan', full_name: 'zh-CN-XiaohanNeural' },
])

// 录音相关
const isRecording = ref(false)
const recordingTime = ref(0)
const recordedAudio = ref(null)
const recordedAudioUrl = ref('')
let mediaRecorder = null
let audioChunks = []
let recordingTimer = null

// 训练相关
const trainingStatus = ref('')
const trainingProgress = ref(0)
const errorMessage = ref('')

// 计算属性
const canProceed = computed(() => {
  if (currentStep.value === 0) return createMethod.value !== ''
  if (currentStep.value === 1) {
    if (createMethod.value === 'edge') {
      return packageName.value.trim() !== '' && selectedVoice.value !== ''
    } else {
      return packageName.value.trim() !== '' && recordedAudio.value !== null
    }
  }
  return true
})

const nextButtonText = computed(() => {
  if (currentStep.value === 1 && createMethod.value === 'clone') {
    return '开始训练'
  }
  return '下一步'
})

// 方法
function close() {
  emit('close')
}

function nextStep() {
  if (currentStep.value === 1 && createMethod.value === 'clone') {
    startTraining()
  }
  currentStep.value++
}

function prevStep() {
  currentStep.value--
}

async function startTraining() {
  isProcessing.value = true
  trainingStatus.value = 'uploading'
  
  try {
    // 上传音频
    const formData = new FormData()
    formData.append('audio', recordedAudio.value, 'recording.webm')
    formData.append('name', packageName.value)

    const uploadRes = await apiFetch('/api/voice-clone/upload', {
      method: 'POST',
      body: formData
    })

    if (!uploadRes.ok) throw new Error('上传失败')

    const uploadData = await uploadRes.json()

    // 开始训练
    trainingStatus.value = 'training'

    const trainRes = await apiFetch('/api/voice-clone/train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        temp_path: uploadData.temp_path,
        name: packageName.value
      })
    })
    
    if (!trainRes.ok) {
      const error = await trainRes.json()
      throw new Error(error.detail || '训练失败')
    }
    
    trainingStatus.value = 'completed'
    
  } catch (error) {
    console.error('训练失败:', error)
    trainingStatus.value = 'error'
    errorMessage.value = error.message
  } finally {
    isProcessing.value = false
  }
}

async function finish() {
  if (createMethod.value === 'edge') {
    // 创建 Edge TTS 语音包
    try {
      const res = await apiFetch('/api/tts/voices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: packageName.value,
          voice_name: selectedVoice.value,
          type: 'edge-tts'
        })
      })
      
      if (res.ok) {
        emit('created')
      }
    } catch (error) {
      console.error('创建语音包失败:', error)
    }
  }
  
  close()
}

// 录音功能
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream)
    audioChunks = []
    
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      recordedAudio.value = blob
      recordedAudioUrl.value = URL.createObjectURL(blob)
    }
    
    mediaRecorder.start()
    isRecording.value = true
    recordingTime.value = 0
    
    recordingTimer = setInterval(() => {
      recordingTime.value++
    }, 1000)
    
  } catch (error) {
    console.error('录音失败:', error)
    alert('无法访问麦克风')
  }
}

function stopRecording() {
  if (!isRecording.value || !mediaRecorder) return
  
  mediaRecorder.stop()
  isRecording.value = false
  clearInterval(recordingTimer)
  
  mediaRecorder.stream.getTracks().forEach(track => track.stop())
}

function reRecord() {
  recordedAudio.value = null
  recordedAudioUrl.value = ''
  audioChunks = []
}

function uploadAudio() {
  // 音频已保存在 recordedAudio 中，进入下一步
}

// 预览语音
const isPreviewing = ref(false)
async function previewVoice(voiceName) {
  if (isPreviewing.value) {
    isPreviewing.value = false
    return
  }
  
  try {
    isPreviewing.value = true
    const formData = new FormData()
    formData.append('text', '你好，我是来福，一只可爱的柯基犬！')
    formData.append('voice_id', voiceName)

    const res = await apiFetch('/api/tts', {
      method: 'POST',
      body: formData
    })
    
    if (res.ok) {
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      
      audio.onended = () => {
        isPreviewing.value = false
        URL.revokeObjectURL(url)
      }
      
      await audio.play()
    }
  } catch (error) {
    console.error('预览失败:', error)
    isPreviewing.value = false
  }
}

// 清理
onUnmounted(() => {
  if (recordingTimer) clearInterval(recordingTimer)
  if (mediaRecorder) mediaRecorder.stream?.getTracks()?.forEach(t => t.stop())
})
</script>

<style scoped>
.voice-wizard-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.voice-wizard {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #eee;
}

.wizard-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.close-btn:hover {
  color: #333;
}

/* 步骤指示器 */
.step-indicator {
  display: flex;
  justify-content: space-between;
  padding: 20px 40px;
  position: relative;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #666;
  transition: all 0.3s;
}

.step.active .step-number {
  background: #667eea;
  color: white;
}

.step.completed .step-number {
  background: #43e97b;
  color: white;
}

.step-label {
  font-size: 12px;
  color: #666;
}

.step-line {
  position: absolute;
  top: 36px;
  left: 60px;
  right: 60px;
  height: 2px;
  background: #e0e0e0;
  z-index: 0;
}

.step-line::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: #667eea;
  width: var(--progress, 0%);
  transition: width 0.3s;
}

/* 内容区 */
.wizard-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.step-content h4 {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #333;
}

/* 选项卡片 */
.option-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.option-card {
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.option-card:hover {
  border-color: #667eea;
  transform: translateY(-2px);
}

.option-card.selected {
  border-color: #667eea;
  background: #f8f9ff;
}

.card-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.card-title {
  font-weight: bold;
  margin-bottom: 8px;
}

.card-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}

/* 语音网格 */
.voice-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.voice-item {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.voice-item:hover {
  border-color: #667eea;
}

.voice-item.selected {
  border-color: #667eea;
  background: #f8f9ff;
}

.voice-name {
  font-size: 14px;
  margin-bottom: 8px;
}

.voice-preview button {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
}

/* 表单 */
.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  color: #333;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
}

.form-input:focus {
  outline: none;
  border-color: #667eea;
}

/* 录音区 */
.recording-section {
  text-align: center;
}

.recording-tips {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  text-align: left;
}

.recording-tips p {
  margin: 0 0 8px 0;
  font-weight: bold;
}

.recording-tips ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #666;
}

.recording-area {
  margin-bottom: 20px;
}

.record-btn-large {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 0 auto;
  transition: all 0.3s;
}

.record-btn-large.recording {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  animation: pulse 1s infinite;
}

.record-icon {
  font-size: 32px;
}

.record-text {
  font-size: 12px;
}

.recording-wave {
  display: flex;
  justify-content: center;
  gap: 3px;
  margin-top: 16px;
  height: 40px;
  align-items: center;
}

.recording-wave span {
  width: 4px;
  background: #667eea;
  border-radius: 2px;
  animation: wave 0.5s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { transform: scaleY(0.3); }
  50% { transform: scaleY(1); }
}

.recorded-preview {
  audio {
    width: 100%;
    margin-bottom: 16px;
  }
}

.preview-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.preview-actions button {
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid #ddd;
  background: white;
  cursor: pointer;
}

.preview-actions button.primary {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

/* 处理状态 */
.processing-status {
  text-align: center;
  padding: 40px;
}

.success-icon, .error-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.spinner-large {
  width: 64px;
  height: 64px;
  border: 4px solid #e0e0e0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 16px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s;
}

/* 底部按钮 */
.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #eee;
}

.btn-primary, .btn-secondary {
  padding: 10px 24px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5a6fd6;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333;
}

.btn-secondary:hover:not(:disabled) {
  background: #e8e8e8;
}
</style>

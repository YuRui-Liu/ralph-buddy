<template>
  <div class="voice-manager-overlay" @click.self="close">
    <div class="voice-manager">
      <!-- 标题栏 -->
      <div class="manager-header">
        <h3>🎙️ 语音包管理</h3>
        <button class="close-btn" @click="close">×</button>
      </div>
      
      <!-- 内容区 -->
      <div class="manager-content">
        <!-- 当前激活 -->
        <div class="active-voice-section">
          <h4>当前使用</h4>
          <div v-if="activeVoice" class="active-voice-card">
            <div class="voice-icon">{{ activeVoice.type === 'edge-tts' ? '☁️' : '🎭' }}</div>
            <div class="voice-info">
              <div class="voice-name">{{ activeVoice.name }}</div>
              <div class="voice-type">{{ getVoiceTypeLabel(activeVoice.type) }}</div>
            </div>
            <button class="test-btn" @click="testVoice(activeVoice)">试听</button>
          </div>
          <div v-else class="no-active">
            未选择语音包
          </div>
        </div>
        
        <!-- 语音包列表 -->
        <div class="voice-list-section">
          <div class="section-header">
            <h4>我的语音包</h4>
            <button class="add-btn" @click="openWizard">
              <span>+</span> 新建
            </button>
          </div>
          
          <div class="voice-list">
            <div
              v-for="voice in voicePackages"
              :key="voice.id"
              class="voice-item"
              :class="{ active: activeVoice?.id === voice.id }"
            >
              <div class="voice-icon-small">{{ voice.type === 'edge-tts' ? '☁️' : '🎭' }}</div>
              
              <div class="voice-details">
                <div class="voice-name-row">
                  <span class="name">{{ voice.name }}</span>
                  <span v-if="activeVoice?.id === voice.id" class="active-badge">使用中</span>
                </div>
                <div class="voice-meta">
                  {{ getVoiceTypeLabel(voice.type) }} · {{ formatDate(voice.created_at) }}
                </div>
              </div>
              
              <div class="voice-actions">
                <button 
                  class="action-btn activate"
                  :disabled="activeVoice?.id === voice.id"
                  @click="activateVoice(voice)"
                >
                  {{ activeVoice?.id === voice.id ? '✓' : '启用' }}
                </button>
                <button class="action-btn test" @click="testVoice(voice)">▶</button>
                <button 
                  class="action-btn delete"
                  :disabled="voicePackages.length <= 1"
                  @click="confirmDelete(voice)"
                >
                  🗑
                </button>
              </div>
            </div>
          </div>
          
          <div v-if="voicePackages.length === 0" class="empty-state">
            <div class="empty-icon">🎙️</div>
            <p>还没有语音包</p>
            <button class="create-btn" @click="openWizard">创建语音包</button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 创建向导 -->
    <VoicePackageWizard
      v-if="showWizard"
      @close="closeWizard"
      @created="onVoiceCreated"
    />
    
    <!-- 删除确认 -->
    <div v-if="showDeleteConfirm" class="confirm-dialog-overlay">
      <div class="confirm-dialog">
        <h4>确认删除</h4>
        <p>确定要删除语音包 "{{ voiceToDelete?.name }}" 吗？</p>
        <div class="dialog-actions">
          <button class="btn-secondary" @click="showDeleteConfirm = false">取消</button>
          <button class="btn-danger" @click="deleteVoice">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import VoicePackageWizard from './VoicePackageWizard.vue'
import { apiFetch } from '@/utils/api'

const emit = defineEmits(['close'])

// 状态
const voicePackages = ref([])
const activeVoice = ref(null)
const showWizard = ref(false)
const showDeleteConfirm = ref(false)
const voiceToDelete = ref(null)
const isTesting = ref(false)

// 加载语音包列表
async function loadVoices() {
  try {
    const res = await apiFetch('/api/tts/voices')
    
    if (res.ok) {
      const data = await res.json()
      voicePackages.value = data.packages || []
      activeVoice.value = voicePackages.value.find(v => v.is_active) || null
    }
  } catch (error) {
    console.error('加载语音包失败:', error)
  }
}

// 启用语音包
async function activateVoice(voice) {
  try {
    const res = await apiFetch(`/api/tts/voices/${voice.id}/activate`, {
      method: 'POST'
    })
    
    if (res.ok) {
      // 更新本地状态
      voicePackages.value.forEach(v => v.is_active = (v.id === voice.id))
      activeVoice.value = voice
    }
  } catch (error) {
    console.error('启用语音包失败:', error)
    alert('启用失败，请重试')
  }
}

// 试听语音
async function testVoice(voice) {
  if (isTesting.value) return
  
  try {
    isTesting.value = true
    // 如果当前不是激活的语音，临时切换
    const testText = '你好，我是来福，一只可爱的柯基犬！汪汪！'

    const formData = new FormData()
    formData.append('text', testText)
    if (voice.voice_name) {
      formData.append('voice_id', voice.voice_name)
    }

    const res = await apiFetch('/api/tts', {
      method: 'POST',
      body: formData
    })
    
    if (res.ok) {
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      
      audio.onended = () => {
        isTesting.value = false
        URL.revokeObjectURL(url)
      }
      
      await audio.play()
    }
  } catch (error) {
    console.error('试听失败:', error)
    isTesting.value = false
    alert('试听失败')
  }
}

// 确认删除
function confirmDelete(voice) {
  voiceToDelete.value = voice
  showDeleteConfirm.value = true
}

// 删除语音包
async function deleteVoice() {
  if (!voiceToDelete.value) return

  try {
    const res = await apiFetch(`/api/tts/voices/${voiceToDelete.value.id}`, {
      method: 'DELETE'
    })
    
    if (res.ok) {
      // 从列表中移除
      voicePackages.value = voicePackages.value.filter(v => v.id !== voiceToDelete.value.id)
      
      // 如果删除的是激活的，重置
      if (activeVoice.value?.id === voiceToDelete.value.id) {
        activeVoice.value = voicePackages.value[0] || null
      }
      
      showDeleteConfirm.value = false
      voiceToDelete.value = null
    }
  } catch (error) {
    console.error('删除失败:', error)
    alert('删除失败')
  }
}

// 打开向导
function openWizard() {
  showWizard.value = true
}

// 关闭向导
function closeWizard() {
  showWizard.value = false
}

// 语音包创建完成
function onVoiceCreated() {
  loadVoices()
  closeWizard()
}

// 关闭管理器
function close() {
  emit('close')
}

// 辅助函数
function getVoiceTypeLabel(type) {
  const labels = {
    'edge-tts': 'Edge TTS',
    'gpt-sovits': 'GPT-SoVITS 克隆'
  }
  return labels[type] || type
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

// 初始化
onMounted(() => {
  loadVoices()
})
</script>

<style scoped>
.voice-manager-overlay {
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

.voice-manager {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.manager-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #eee;
}

.manager-header h3 {
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

/* 内容区 */
.manager-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* 当前激活 */
.active-voice-section {
  margin-bottom: 24px;
}

.active-voice-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #666;
}

.active-voice-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
  border: 2px solid #667eea;
  border-radius: 12px;
}

.voice-icon {
  font-size: 32px;
}

.voice-info {
  flex: 1;
}

.voice-name {
  font-weight: bold;
  font-size: 16px;
}

.voice-type {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.test-btn {
  padding: 8px 16px;
  border: 1px solid #667eea;
  background: white;
  color: #667eea;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.test-btn:hover {
  background: #667eea;
  color: white;
}

.no-active {
  padding: 24px;
  text-align: center;
  color: #999;
  background: #f5f5f5;
  border-radius: 12px;
}

/* 列表区 */
.voice-list-section {
  flex: 1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h4 {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.add-btn:hover {
  background: #5a6fd6;
}

/* 语音列表 */
.voice-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voice-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  transition: all 0.2s;
}

.voice-item:hover {
  border-color: #667eea;
  background: #f8f9ff;
}

.voice-item.active {
  border-color: #667eea;
  background: #f8f9ff;
}

.voice-icon-small {
  font-size: 24px;
}

.voice-details {
  flex: 1;
  min-width: 0;
}

.voice-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.voice-name-row .name {
  font-weight: 500;
  font-size: 14px;
}

.active-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: #667eea;
  color: white;
  border-radius: 4px;
}

.voice-meta {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.voice-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #e0e0e0;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.action-btn:hover:not(:disabled) {
  border-color: #667eea;
  background: #f8f9ff;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.activate {
  color: #667eea;
  min-width: 48px;
}

.action-btn.delete {
  color: #f5576c;
}

.action-btn.delete:hover:not(:disabled) {
  border-color: #f5576c;
  background: #fff5f5;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-state p {
  color: #999;
  margin-bottom: 16px;
}

.create-btn {
  padding: 10px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

/* 确认对话框 */
.confirm-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.confirm-dialog {
  background: white;
  padding: 24px;
  border-radius: 12px;
  width: 90%;
  max-width: 320px;
  text-align: center;
}

.confirm-dialog h4 {
  margin: 0 0 12px 0;
}

.confirm-dialog p {
  color: #666;
  margin-bottom: 20px;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-secondary, .btn-danger {
  padding: 10px 20px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333;
}

.btn-danger {
  background: #f5576c;
  color: white;
}
</style>

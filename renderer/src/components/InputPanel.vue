<template>
  <div class="input-panel">
    <div class="input-container">
      <input 
        v-model="inputText" 
        type="text" 
        placeholder="和来福说点什么..."
        @keyup.enter="sendMessage"
        ref="inputRef"
      />
      <button 
        class="voice-btn" 
        :class="{ 'recording': chatStore.isRecording }"
        @mousedown="startRecording"
        @mouseup="stopRecording"
        @mouseleave="stopRecording"
      >
        <span v-if="!chatStore.isRecording">🎤</span>
        <span v-else>🔴</span>
      </button>
      <button class="send-btn" @click="sendMessage" :disabled="!inputText.trim()">
        发送
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { usePetStore } from '../stores/pet'
import { apiFetch } from '@/utils/api'

const chatStore = useChatStore()
const petStore = usePetStore()
const inputText = ref('')
const inputRef = ref(null)

// 发送消息
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  // 添加用户消息
  chatStore.addMessage('user', text)
  inputText.value = ''

  // 显示输入中状态
  chatStore.setTyping(true)
  chatStore.showMessage('...')

  try {
    // 调用后端 API 获取回复
    const response = await apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    })

    const data = await response.json()
    
    // 显示回复
    chatStore.setTyping(false)
    chatStore.showMessage(data.reply, 5000)
    chatStore.addMessage('assistant', data.reply)
  } catch (error) {
    console.error('Chat error:', error)
    chatStore.setTyping(false)
    chatStore.showMessage('汪？来福没听清楚，再说一遍好吗？', 3000)
  }
}

// 录音功能（占位）
function startRecording() {
  chatStore.setRecording(true)
  // TODO: 实现录音逻辑
}

function stopRecording() {
  if (chatStore.isRecording) {
    chatStore.setRecording(false)
    // TODO: 发送录音并获取回复
  }
}

onMounted(() => {
  inputRef.value?.focus()
})
</script>

<style scoped>
.input-panel {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 350px;
  z-index: 100;
}

.input-container {
  display: flex;
  gap: 8px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  padding: 8px 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.input-container input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  outline: none;
  padding: 4px 8px;
  color: #333;
}

.input-container input::placeholder {
  color: #999;
}

.voice-btn, .send-btn {
  border: none;
  background: #f0f0f0;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  font-size: 16px;
}

.voice-btn:hover, .send-btn:hover {
  background: #e0e0e0;
  transform: scale(1.05);
}

.voice-btn.recording {
  background: #ff4444;
  animation: pulse 1s infinite;
}

.send-btn {
  width: auto;
  padding: 0 16px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 500;
  color: #666;
}

.send-btn:not(:disabled) {
  background: #4CAF50;
  color: white;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(255, 68, 68, 0.4);
  }
  50% {
    transform: scale(1.1);
    box-shadow: 0 0 0 10px rgba(255, 68, 68, 0);
  }
}
</style>

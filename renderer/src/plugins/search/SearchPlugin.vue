<template>
  <div class="search-plugin">
    <div class="header">
      <span class="title">搜索助手</span>
      <button class="clear-btn" @click="clearChat" title="清空对话">🗑️</button>
    </div>

    <div class="chat-area" ref="chatArea">
      <div v-if="!messages.length" class="empty-hint">输入问题开始对话</div>
      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="message-content" v-html="formatMessage(msg.content)"></div>
      </div>
      <div v-if="loading" class="message assistant">
        <div class="message-content typing">思考中...</div>
      </div>
    </div>

    <div class="input-bar">
      <input v-model="input" placeholder="输入问题..." @keydown.enter="send" :disabled="loading" />
      <button class="send-btn" @click="send" :disabled="loading || !input.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { apiFetch } from '../../utils/api'

const props = defineProps({ manifest: Object })

const input = ref('')
const messages = ref([])
const loading = ref(false)
const chatArea = ref(null)

let sessionId = 'search_' + Date.now()

async function send() {
  if (!input.value.trim() || loading.value) return
  const userMsg = input.value.trim()
  input.value = ''
  messages.value.push({ role: 'user', content: userMsg })
  scrollToBottom()

  loading.value = true
  try {
    const res = await apiFetch('/api/plugin/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plugin_id: 'search',
        message: userMsg,
        session_id: sessionId,
        llm_config: props.manifest?.llm || {},
      })
    })
    if (!res.ok) throw new Error(`请求失败: ${res.status}`)
    const data = await res.json()
    messages.value.push({ role: 'assistant', content: data.reply })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `错误: ${e.message}` })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function clearChat() {
  messages.value = []
  try {
    await apiFetch('/api/plugin/session/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    })
  } catch (e) { /* ignore */ }
  sessionId = 'search_' + Date.now()
}

function formatMessage(text) {
  return text.replace(/\n/g, '<br>')
}

async function scrollToBottom() {
  await nextTick()
  if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
}
</script>

<style scoped>
.search-plugin { height: 100vh; display: flex; flex-direction: column; }

.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid #eee;
}
.title { font-size: 16px; font-weight: 700; }
.clear-btn {
  background: none; border: none; font-size: 16px; cursor: pointer;
  opacity: 0.5; transition: opacity 0.2s;
}
.clear-btn:hover { opacity: 1; }

.chat-area {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.empty-hint { text-align: center; color: #bbb; margin-top: 40px; font-size: 14px; }

.message {
  max-width: 85%; padding: 10px 14px; border-radius: 12px;
  font-size: 14px; line-height: 1.6;
}
.message.user {
  align-self: flex-end; background: #667eea; color: white;
  border-bottom-right-radius: 4px;
}
.message.assistant {
  align-self: flex-start; background: white; border: 1px solid #eee;
  color: #333; border-bottom-left-radius: 4px;
}
.typing { color: #aaa; font-style: italic; }

.input-bar {
  display: flex; gap: 8px; padding: 12px 16px;
  border-top: 1px solid #eee; background: white;
}
.input-bar input {
  flex: 1; padding: 10px 14px; border: 1px solid #ddd;
  border-radius: 8px; font-size: 14px; font-family: inherit;
}
.input-bar input:focus { outline: none; border-color: #667eea; }

.send-btn {
  padding: 10px 20px; background: #667eea; color: white;
  border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>

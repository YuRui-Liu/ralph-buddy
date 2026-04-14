<template>
  <div class="flirt-plugin">
    <div class="header">
      <span class="title">💕 聊天搭子</span>
      <button class="clear-btn" @click="clearAll" title="清空">🗑️</button>
    </div>

    <!-- 对话记录区 -->
    <div class="chat-log" ref="chatLog">
      <div v-if="!chatMessages.length" class="empty-hint">
        添加你们的聊天记录，我来帮你分析
      </div>
      <div v-for="(msg, i) in chatMessages" :key="i" :class="['chat-msg', msg.role]">
        <span class="msg-role">{{ msg.role === 'me' ? '我' : 'TA' }}</span>
        <span class="msg-text">{{ msg.text }}</span>
        <button class="msg-del" @click="chatMessages.splice(i, 1)">×</button>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-section">
      <div class="input-row">
        <select v-model="currentRole" class="role-select">
          <option value="them">TA说</option>
          <option value="me">我说</option>
        </select>
        <input
          v-model="input"
          :placeholder="currentRole === 'them' ? '对方说了什么...' : '你说了什么...'"
          @keydown.enter.exact="addMessage"
          @keydown.ctrl.enter="analyze"
        />
        <button class="add-btn" @click="addMessage" :disabled="!input.trim()">+</button>
      </div>
      <div class="action-row">
        <span class="hint">Enter 添加消息，Ctrl+Enter 分析</span>
        <button class="analyze-btn" @click="analyze" :disabled="loading || !chatMessages.length">
          {{ loading ? '分析中...' : '帮我分析' }}
        </button>
      </div>
    </div>

    <!-- 分析结果 -->
    <div class="results" v-if="analysis || replies.length">
      <div class="analysis-card" v-if="analysis">
        <div class="analysis-label">局势分析</div>
        <div class="analysis-text">{{ analysis }}</div>
      </div>
      <div class="reply-card" v-for="(r, i) in replies" :key="i">
        <div class="reply-text">"{{ r.text }}"</div>
        <div class="reply-tip">💡 {{ r.tip }}</div>
        <button class="copy-btn" @click="copyText(r.text)">复制</button>
      </div>
    </div>

    <div class="error" v-if="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { apiFetch } from '../../utils/api'

const props = defineProps({ manifest: Object })

const input = ref('')
const currentRole = ref('them')
const chatMessages = ref([])  // [{role: 'me'|'them', text: '...'}]
const replies = ref([])
const analysis = ref('')
const loading = ref(false)
const error = ref('')
const chatLog = ref(null)

let sessionId = 'flirt_' + Date.now()

async function addMessage() {
  if (!input.value.trim()) return
  chatMessages.value.push({
    role: currentRole.value === 'me' ? 'me' : 'them',
    text: input.value.trim()
  })
  input.value = ''
  // 自动切换角色
  currentRole.value = currentRole.value === 'me' ? 'them' : 'me'
  await nextTick()
  if (chatLog.value) chatLog.value.scrollTop = chatLog.value.scrollHeight
}

async function analyze() {
  if (!chatMessages.value.length || loading.value) return
  loading.value = true
  error.value = ''
  replies.value = []
  analysis.value = ''

  // 构建对话上下文
  const context = chatMessages.value
    .map(m => `${m.role === 'me' ? '我' : '对方'}：${m.text}`)
    .join('\n')

  try {
    const res = await apiFetch('/api/plugin/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plugin_id: 'flirt',
        message: `以下是我们的聊天记录：\n${context}\n\n请分析并给出回复建议。`,
        session_id: sessionId,
        llm_config: props.manifest?.llm || {},
      })
    })
    if (!res.ok) throw new Error(`请求失败: ${res.status}`)

    const data = await res.json()
    if (data.structured) {
      analysis.value = data.structured.analysis || ''
      replies.value = data.structured.replies || []
    } else {
      replies.value = [{ text: data.reply, tip: '直接回复' }]
    }
  } catch (e) {
    error.value = `分析失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

function clearAll() {
  chatMessages.value = []
  replies.value = []
  analysis.value = ''
  error.value = ''
  sessionId = 'flirt_' + Date.now()
}

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {})
}
</script>

<style scoped>
.flirt-plugin {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}
.title { font-size: 16px; font-weight: 700; }
.clear-btn {
  background: none; border: none; font-size: 16px; cursor: pointer;
  opacity: 0.5; transition: opacity 0.2s;
}
.clear-btn:hover { opacity: 1; }

/* 对话记录区 */
.chat-log {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}

.empty-hint {
  text-align: center; color: #bbb; margin-top: 30px; font-size: 14px;
}

.chat-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 13px;
  position: relative;
}

.chat-msg.me {
  background: rgba(102, 126, 234, 0.08);
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-msg.them {
  background: rgba(245, 87, 108, 0.06);
  align-self: flex-start;
}

.msg-role {
  font-size: 11px;
  font-weight: 700;
  color: #999;
  min-width: 20px;
}

.msg-text {
  color: #333;
  line-height: 1.4;
}

.msg-del {
  background: none; border: none; color: #ccc; cursor: pointer;
  font-size: 14px; padding: 0 4px; opacity: 0; transition: opacity 0.15s;
}
.chat-msg:hover .msg-del { opacity: 1; }

/* 输入区 */
.input-section {
  padding: 10px 16px;
  border-top: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-row {
  display: flex;
  gap: 6px;
}

.role-select {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 13px;
  background: white;
  cursor: pointer;
  min-width: 70px;
}

.input-row input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 13px;
  font-family: inherit;
}
.input-row input:focus { outline: none; border-color: #667eea; }

.add-btn {
  width: 36px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  cursor: pointer;
}
.add-btn:disabled { opacity: 0.4; }

.action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint { font-size: 11px; color: #bbb; }

.analyze-btn {
  padding: 8px 20px;
  background: linear-gradient(135deg, #f093fb, #f5576c);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 分析结果 */
.results {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.analysis-card {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  padding: 12px;
}
.analysis-label { font-size: 11px; font-weight: 700; color: #b45309; margin-bottom: 4px; }
.analysis-text { font-size: 13px; color: #78350f; line-height: 1.5; }

.reply-card {
  background: white; border: 1px solid #eee; border-radius: 10px;
  padding: 12px; position: relative;
}
.reply-text { font-size: 14px; color: #222; margin-bottom: 6px; line-height: 1.5; }
.reply-tip { font-size: 12px; color: #888; }

.copy-btn {
  position: absolute; top: 10px; right: 10px; padding: 4px 10px;
  background: #f0f0f0; border: none; border-radius: 4px; font-size: 11px; cursor: pointer;
}
.copy-btn:hover { background: #e0e0e0; }

.error { padding: 0 16px; color: #f5576c; font-size: 13px; }
</style>

<template>
  <div class="flirt-plugin">
    <div class="header">
      <span class="title">撩妹助手</span>
    </div>

    <div class="input-section">
      <label>她说了什么：</label>
      <textarea
        v-model="input"
        placeholder="输入对方发来的消息..."
        rows="3"
        @keydown.ctrl.enter="analyze"
      ></textarea>
      <button class="analyze-btn" @click="analyze" :disabled="loading || !input.trim()">
        {{ loading ? '分析中...' : '分析' }}
      </button>
    </div>

    <div class="results" v-if="replies.length">
      <div class="reply-card" v-for="(r, i) in replies" :key="i">
        <div class="reply-text">"{{ r.text }}"</div>
        <div class="reply-tip">{{ r.tip }}</div>
        <button class="copy-btn" @click="copyText(r.text)">复制</button>
      </div>
    </div>

    <div class="error" v-if="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({ manifest: Object })

const input = ref('')
const replies = ref([])
const loading = ref(false)
const error = ref('')

let pythonPort = 18765
let sessionId = 'flirt_' + Date.now()

async function init() {
  pythonPort = await window.pluginAPI?.getPythonPort?.() || 18765
}
init()

async function analyze() {
  if (!input.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  replies.value = []

  try {
    const res = await fetch(`http://127.0.0.1:${pythonPort}/api/plugin/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plugin_id: 'flirt',
        message: input.value.trim(),
        session_id: sessionId,
        llm_config: props.manifest?.llm || {},
      })
    })
    if (!res.ok) throw new Error(`请求失败: ${res.status}`)

    const data = await res.json()
    if (data.structured?.replies) {
      replies.value = data.structured.replies
    } else {
      replies.value = [{ text: data.reply, tip: '直接回复' }]
    }
  } catch (e) {
    error.value = `分析失败: ${e.message}`
  } finally {
    loading.value = false
  }
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
  padding: 16px;
  gap: 16px;
  overflow-y: auto;
}

.header { display: flex; align-items: center; }
.title { font-size: 18px; font-weight: 700; }

.input-section { display: flex; flex-direction: column; gap: 8px; }
.input-section label { font-size: 13px; font-weight: 600; color: #555; }
.input-section textarea {
  padding: 10px; border: 1px solid #ddd; border-radius: 8px;
  font-size: 14px; resize: none; font-family: inherit;
}
.input-section textarea:focus { outline: none; border-color: #667eea; }

.analyze-btn {
  padding: 10px; background: linear-gradient(135deg, #f093fb, #f5576c);
  color: white; border: none; border-radius: 8px; font-size: 14px;
  font-weight: 600; cursor: pointer; transition: opacity 0.2s;
}
.analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.results { display: flex; flex-direction: column; gap: 12px; }

.reply-card {
  background: white; border: 1px solid #eee; border-radius: 10px;
  padding: 14px; position: relative;
}
.reply-text { font-size: 15px; color: #222; margin-bottom: 8px; line-height: 1.5; }
.reply-tip { font-size: 12px; color: #888; }

.copy-btn {
  position: absolute; top: 10px; right: 10px; padding: 4px 10px;
  background: #f0f0f0; border: none; border-radius: 4px; font-size: 11px; cursor: pointer;
}
.copy-btn:hover { background: #e0e0e0; }

.error { color: #f5576c; font-size: 13px; }
</style>

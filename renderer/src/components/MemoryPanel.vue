<template>
  <div :class="standalone ? 'panel-standalone' : 'memory-panel-overlay'" @click.self="close">
    <div :class="standalone ? 'panel-full' : 'memory-panel'">
      <!-- 标题栏 -->
      <div class="panel-header">
        <span class="panel-title">🧠 来福的记忆</span>
        <button class="close-btn" @click="close">×</button>
      </div>

      <!-- 用户画像 -->
      <section class="section">
        <h3 class="section-title">👤 用户画像</h3>
        <div class="profile-box" v-if="Object.keys(profile).length > 1">
          <div class="profile-stat">对话总数：{{ profile.total_conversations ?? 0 }} 轮</div>
          <div
            v-for="(value, key) in profileFacts"
            :key="key"
            class="profile-item"
          >
            <span class="fact-key">{{ key }}</span>
            <span class="fact-value">{{ value }}</span>
          </div>
        </div>
        <div class="empty-hint" v-else>暂无画像，多和来福聊聊吧~</div>
      </section>

      <!-- 重要记忆 -->
      <section class="section">
        <div class="section-header">
          <h3 class="section-title">📌 重要记忆</h3>
          <button class="add-btn" @click="showAddInput = !showAddInput">+ 添加</button>
        </div>

        <!-- 添加记忆输入框 -->
        <div v-if="showAddInput" class="add-input-row">
          <input
            v-model="newMemoryText"
            class="add-input"
            placeholder="输入要让来福记住的事..."
            @keyup.enter="addMemory"
            ref="addInputRef"
          />
          <button class="confirm-btn" @click="addMemory" :disabled="!newMemoryText.trim()">确认</button>
        </div>

        <ul class="events-list" v-if="events.length">
          <li v-for="event in events" :key="event.id" class="event-item">
            <span class="event-content">{{ event.content }}</span>
            <button class="delete-btn" @click="deleteEvent(event.id)" title="删除">🗑</button>
          </li>
        </ul>
        <div class="empty-hint" v-else>还没有重要记忆</div>
      </section>

      <!-- 搜索记忆 -->
      <section class="section">
        <h3 class="section-title">🔍 搜索记忆</h3>
        <div class="search-row">
          <input
            v-model="searchQuery"
            class="search-input"
            placeholder="搜索关键词..."
            @input="debouncedSearch"
          />
        </div>
        <ul class="events-list" v-if="searchResults.length">
          <li v-for="(r, i) in searchResults" :key="i" class="event-item search-result">
            <span class="event-content">{{ r.content }}</span>
          </li>
        </ul>
        <div class="empty-hint" v-else-if="searchQuery && !isSearching">无匹配结果</div>
      </section>

      <!-- 危险区 -->
      <section class="section danger-section">
        <button class="danger-btn" @click="confirmClear">清除全部记忆</button>
        <div v-if="clearConfirming" class="confirm-hint">
          确定要清除吗？
          <button class="confirm-yes" @click="clearAll">确定</button>
          <button class="confirm-no" @click="clearConfirming = false">取消</button>
        </div>
      </section>

      <!-- 全局加载提示 -->
      <div class="loading-overlay" v-if="isLoading">
        <span>处理中...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '@/utils/api'

const props = defineProps({ standalone: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

function close() {
  if (props.standalone) {
    window.pluginAPI?.closeWindow()
  } else {
    emit('close')
  }
}

const profile    = ref({})
const events     = ref([])
const searchQuery   = ref('')
const searchResults = ref([])
const newMemoryText = ref('')
const showAddInput  = ref(false)
const clearConfirming = ref(false)
const isLoading  = ref(false)
const isSearching = ref(false)
const addInputRef = ref(null)

// 画像数据（排除统计字段）
const profileFacts = computed(() => {
  const { total_conversations, ...rest } = profile.value
  return rest
})

// 加载画像
async function loadProfile() {
  try {
    const r = await apiFetch('/api/memory/summary')
    if (r.ok) profile.value = await r.json()
  } catch (e) {
    console.error('加载画像失败', e)
  }
}

// 加载重要记忆列表
async function loadEvents() {
  try {
    const r = await apiFetch('/api/memory/events')
    if (r.ok) {
      const data = await r.json()
      events.value = data.events
    }
  } catch (e) {
    console.error('加载记忆列表失败', e)
  }
}

// 添加记忆
async function addMemory() {
  const text = newMemoryText.value.trim()
  if (!text) return
  isLoading.value = true
  try {
    const r = await apiFetch('/api/memory/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text, importance: 3 }),
    })
    if (r.ok) {
      newMemoryText.value = ''
      showAddInput.value = false
      await loadEvents()
    }
  } catch (e) {
    console.error('添加记忆失败', e)
  } finally {
    isLoading.value = false
  }
}

// 删除记忆
async function deleteEvent(id) {
  isLoading.value = true
  try {
    const r = await apiFetch(`/api/memory/events/${id}`, { method: 'DELETE' })
    if (r.ok) await loadEvents()
  } catch (e) {
    console.error('删除记忆失败', e)
  } finally {
    isLoading.value = false
  }
}

// 搜索记忆（防抖 300ms）
let searchTimer = null
function debouncedSearch() {
  clearTimeout(searchTimer)
  if (!searchQuery.value.trim()) { searchResults.value = []; return }
  searchTimer = setTimeout(doSearch, 300)
}

async function doSearch() {
  isSearching.value = true
  try {
    const r = await apiFetch(`/api/memory/search?query=${encodeURIComponent(searchQuery.value)}`)
    if (r.ok) {
      const data = await r.json()
      searchResults.value = data.results
    }
  } catch (e) {
    console.error('搜索失败', e)
  } finally {
    isSearching.value = false
  }
}

// 清除全部
function confirmClear() {
  clearConfirming.value = true
}

async function clearAll() {
  isLoading.value = true
  clearConfirming.value = false
  try {
    await apiFetch('/api/memory/clear', { method: 'DELETE' })
    profile.value = {}
    events.value  = []
    searchResults.value = []
  } catch (e) {
    console.error('清除失败', e)
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProfile(), loadEvents()])
})
</script>

<style scoped>
.memory-panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.memory-panel {
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  width: 360px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 0 0 16px;
  position: relative;
}

.panel-standalone {
  width: 100%; height: 100vh; background: #fff;
}
.panel-full {
  width: 100%; height: 100%; background: #fff;
  overflow-y: auto; padding: 0 0 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 12px;
  border-bottom: 1px solid rgba(0,0,0,0.08);
  position: sticky;
  top: 0;
  background: rgba(255,255,255,0.97);
  z-index: 1;
}

.panel-title { font-size: 16px; font-weight: 600; color: #333; }

.close-btn {
  background: none; border: none; font-size: 20px;
  color: #999; cursor: pointer; padding: 0 4px;
}
.close-btn:hover { color: #333; }

.section { padding: 12px 20px 4px; }

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-title { font-size: 13px; font-weight: 600; color: #555; margin: 0 0 8px; }

.profile-box {
  background: #f8f8f8;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
}
.profile-stat { color: #888; margin-bottom: 6px; }
.profile-item { display: flex; gap: 8px; padding: 2px 0; }
.fact-key { color: #666; min-width: 60px; }
.fact-value { color: #333; font-weight: 500; }

.add-btn {
  font-size: 12px; background: #667eea; color: #fff;
  border: none; border-radius: 6px; padding: 4px 10px; cursor: pointer;
}
.add-btn:hover { background: #5a6fd6; }

.add-input-row { display: flex; gap: 8px; margin-bottom: 8px; }
.add-input {
  flex: 1; border: 1px solid #ddd; border-radius: 8px;
  padding: 6px 10px; font-size: 13px; outline: none;
}
.add-input:focus { border-color: #667eea; }

.confirm-btn {
  background: #667eea; color: #fff; border: none;
  border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px;
}
.confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.events-list { list-style: none; padding: 0; margin: 0; }

.event-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
  gap: 8px;
}
.event-item:last-child { border-bottom: none; }

.event-content { font-size: 13px; color: #333; flex: 1; line-height: 1.5; }

.delete-btn {
  background: none; border: none; cursor: pointer;
  font-size: 14px; opacity: 0.5; padding: 0;
  flex-shrink: 0;
}
.delete-btn:hover { opacity: 1; }

.search-row { margin-bottom: 8px; }
.search-input {
  width: 100%; box-sizing: border-box;
  border: 1px solid #ddd; border-radius: 8px;
  padding: 7px 12px; font-size: 13px; outline: none;
}
.search-input:focus { border-color: #667eea; }

.search-result { background: #f5f5ff; border-radius: 6px; padding: 6px 8px; margin-bottom: 4px; }

.empty-hint { font-size: 12px; color: #bbb; text-align: center; padding: 8px 0; }

.danger-section { border-top: 1px solid #f0f0f0; margin-top: 4px; padding-top: 16px; }

.danger-btn {
  width: 100%; padding: 8px; background: #fff0f0;
  border: 1px solid #ffcccc; border-radius: 8px;
  color: #e53e3e; cursor: pointer; font-size: 13px;
}
.danger-btn:hover { background: #ffe0e0; }

.confirm-hint { margin-top: 8px; font-size: 13px; color: #666; display: flex; gap: 8px; align-items: center; }
.confirm-yes { background: #e53e3e; color: #fff; border: none; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 12px; }
.confirm-no  { background: #eee; color: #333; border: none; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 12px; }

.loading-overlay {
  position: absolute; inset: 0; background: rgba(255,255,255,0.7);
  display: flex; align-items: center; justify-content: center;
  border-radius: 16px; font-size: 14px; color: #667eea;
}
</style>

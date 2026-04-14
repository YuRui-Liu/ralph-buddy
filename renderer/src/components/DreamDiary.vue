<template>
  <div :class="standalone ? 'panel-standalone' : 'diary-overlay'" @click.self="close">
    <div :class="standalone ? 'panel-full' : 'diary-panel'">
      <div class="diary-header">
        <h2>来福的梦境日记</h2>
        <button class="close-btn" @click="close">✕</button>
      </div>

      <div class="diary-content">
        <div v-if="loading" class="diary-loading">加载中...</div>

        <div v-else-if="dreams.length === 0" class="diary-empty">
          <p>来福还没做过梦哦</p>
          <p class="hint">让来福睡一觉试试？</p>
        </div>

        <div v-else class="dream-list">
          <div v-for="dream in dreams" :key="dream.id" class="dream-card">
            <img
              v-if="dream.image_url"
              :src="dream.image_url"
              class="card-image"
              alt="梦境"
            />
            <div class="card-body">
              <p class="card-text">{{ dream.text }}</p>
              <div class="card-deltas" v-if="Object.keys(dream.attribute_deltas || {}).length">
                <span
                  v-for="(val, key) in dream.attribute_deltas"
                  :key="key"
                  class="delta-badge"
                  :class="val > 0 ? 'positive' : 'negative'"
                >
                  {{ deltaLabel[key] || key }} {{ val > 0 ? '+' : '' }}{{ val }}
                </span>
              </div>
              <p class="card-date">{{ formatDate(dream.created_at) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiFetch, apiUrl } from '@/utils/api'

const props = defineProps({ standalone: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

function close() {
  if (props.standalone) {
    window.pluginAPI?.closeWindow()
  } else {
    emit('close')
  }
}

const dreams = ref([])
const loading = ref(true)

const deltaLabel = {
  mood: '心情', energy: '精力', health: '健康',
  affection: '亲密', obedience: '顺从', snark: '毒舌',
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(async () => {
  try {
    const res = await apiFetch('/api/dream/history')
    if (res.ok) {
      const data = await res.json()
      dreams.value = (data.dreams || []).map(d => ({
        ...d,
        image_url: d.image_path
          ? apiUrl(`/api/dream/image/${d.image_path.split('/').pop()}`)
          : null,
      }))
    }
  } catch (e) {
    console.error('[DreamDiary] 加载失败:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.diary-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.panel-standalone { width: 100%; height: 100vh; background: #fff; }
.panel-full { width: 100%; height: 100%; background: #fff; overflow-y: auto; }

.diary-panel {
  width: 360px;
  max-height: 80vh;
  background: var(--bg-panel, #fff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.diary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: linear-gradient(135deg, #7c4dff 0%, #536dfe 100%);
  color: white;
}

.diary-header h2 {
  margin: 0;
  font-size: 16px;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 13px;
}

.diary-content {
  padding: 14px;
  overflow-y: auto;
  flex: 1;
}

.diary-loading, .diary-empty {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.diary-empty .hint {
  font-size: 12px;
  margin-top: 8px;
}

.dream-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dream-card {
  background: linear-gradient(135deg, #f5f0ff 0%, #ede7f6 100%);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(100, 80, 160, 0.1);
}

.card-image {
  width: 100%;
  height: 150px;
  object-fit: cover;
}

.card-body {
  padding: 12px 14px;
}

.card-text {
  margin: 0 0 8px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3f6b;
}

.card-deltas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.delta-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.delta-badge.positive {
  background: rgba(67, 233, 123, 0.15);
  color: #2e7d32;
}

.delta-badge.negative {
  background: rgba(245, 87, 108, 0.15);
  color: #c62828;
}

.card-date {
  margin: 0;
  font-size: 11px;
  color: #999;
}

[data-theme="dark"] .diary-panel {
  --bg-panel: #2a2a2a;
}

[data-theme="dark"] .dream-card {
  background: linear-gradient(135deg, #3a3050 0%, #2d2845 100%);
}

[data-theme="dark"] .card-text {
  color: #d4c8f0;
}
</style>

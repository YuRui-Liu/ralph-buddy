<template>
  <div :class="standalone ? 'panel-standalone' : 'attributes-overlay'" @click.self="close">
    <div :class="standalone ? 'panel-full' : 'attributes-panel'">
      <!-- 头部 -->
      <div class="panel-header">
        <h2>来福属性</h2>
        <button class="close-btn" @click="close">✕</button>
      </div>

      <!-- 属性列表 -->
      <div class="panel-content">
        <div
          v-for="attr in attributes"
          :key="attr.key"
          class="attr-row"
        >
          <div class="attr-label">
            <span class="attr-icon">{{ attr.icon }}</span>
            <span class="attr-name">{{ attr.name }}</span>
          </div>
          <div class="attr-bar-wrap">
            <div
              class="attr-bar"
              :style="{ width: attr.value + '%', background: barColor(attr.value) }"
            />
          </div>
          <span class="attr-value">{{ attr.value }}</span>
        </div>

        <!-- 当前模式提示 -->
        <div class="mode-hint">
          <span v-if="uiStore.natureMode">当前：天性模式 — 来福会主动互动</span>
          <span v-else-if="uiStore.focusMode">当前：专注模式 — 来福安静陪伴</span>
          <span v-else>当前：普通模式</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePetStore } from '@/stores/pet'
import { useUiStore } from '@/stores/ui'

const petStore = usePetStore()
const props = defineProps({ standalone: { type: Boolean, default: false } })
const uiStore = useUiStore()

const attributes = computed(() => [
  { key: 'health',    name: '健康',   icon: '❤️', value: petStore.health },
  { key: 'mood',      name: '心情',   icon: '😊', value: petStore.mood },
  { key: 'energy',    name: '精力',   icon: '⚡', value: petStore.energy },
  { key: 'affection', name: '亲密度', icon: '💕', value: petStore.affection },
  { key: 'obedience', name: '顺从度', icon: '🎓', value: petStore.obedience },
  { key: 'snark',     name: '毒舌值', icon: '🗯️', value: petStore.snark },
])

function barColor(val) {
  if (val >= 70) return 'linear-gradient(90deg, #43e97b, #38f9d7)'
  if (val >= 40) return 'linear-gradient(90deg, #f6d365, #fda085)'
  return 'linear-gradient(90deg, #f093fb, #f5576c)'
}

function close() {
  if (props.standalone) {
    window.pluginAPI?.closeWindow()
  } else {
    uiStore.closeAttributesPanel()
  }
}
</script>

<style scoped>
.attributes-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.panel-standalone { width: 100%; height: 100vh; background: #fff; }
.panel-full { width: 100%; height: 100%; background: #fff; overflow-y: auto; }

.attributes-panel {
  width: 320px;
  background: var(--bg-panel, #ffffff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
  color: #fff;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.close-btn {
  background: rgba(255, 255, 255, 0.25);
  border: none;
  color: white;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.4);
}

.panel-content {
  padding: 16px 18px;
}

.attr-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.attr-row:last-of-type {
  margin-bottom: 0;
}

.attr-label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 80px;
}

.attr-icon {
  font-size: 16px;
}

.attr-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.attr-bar-wrap {
  flex: 1;
  height: 10px;
  background: var(--bg-secondary, #eee);
  border-radius: 5px;
  overflow: hidden;
}

.attr-bar {
  height: 100%;
  border-radius: 5px;
  transition: width 0.4s ease;
}

.attr-value {
  min-width: 28px;
  text-align: right;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary, #555);
}

.mode-hint {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(128, 128, 128, 0.2);
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary, #888);
}

/* 暗色主题 */
[data-theme="dark"] .attributes-panel {
  --bg-panel: #2a2a2a;
  --bg-secondary: #3a3a3a;
  --text-primary: #fff;
  --text-secondary: #aaa;
}
</style>

<template>
  <div class="plugin-toolbar" @click.stop>
    <button class="toolbar-btn" @click="toggleMenu" title="工具箱">🧰</button>
    <div class="plugin-menu" v-if="showMenu">
      <button v-for="p in plugins" :key="p.id" class="plugin-item" @click="openPlugin(p)">
        <span class="plugin-icon">{{ p.icon }}</span>
        <span class="plugin-name">{{ p.name }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getPlugins, getPlugin } from '../plugins/registry.js'

const plugins = getPlugins()
const showMenu = ref(false)

function toggleMenu() {
  showMenu.value = !showMenu.value
}

function openPlugin(manifest) {
  showMenu.value = false
  if (window.electronAPI?.openPlugin) {
    window.electronAPI.openPlugin(manifest.id, manifest)
  }
}

function closeMenu() {
  showMenu.value = false
}

onMounted(() => {
  document.addEventListener('click', closeMenu)
  if (window.electronAPI?.registerPluginShortcuts) {
    window.electronAPI.registerPluginShortcuts(plugins)
  }
  if (window.electronAPI?.onOpenPluginRequest) {
    window.electronAPI.onOpenPluginRequest((pluginId) => {
      const m = getPlugin(pluginId)
      if (m) openPlugin(m)
    })
  }
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
})
</script>

<style scoped>
.plugin-toolbar {
  position: relative;
}

.toolbar-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: rgba(102, 126, 234, 0.4);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 0;
}

.toolbar-btn:hover {
  background: rgba(102, 126, 234, 0.7);
  transform: scale(1.15);
}

.plugin-menu {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 6px;
  min-width: 130px;
  z-index: 200;
}

.plugin-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.plugin-item:hover {
  background: rgba(102, 126, 234, 0.12);
}

.plugin-icon { font-size: 16px; }
.plugin-name { color: #333; font-weight: 500; }
</style>

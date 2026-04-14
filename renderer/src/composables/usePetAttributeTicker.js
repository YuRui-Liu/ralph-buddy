/**
 * usePetAttributeTicker — 宠物属性定时同步
 */
import { watch } from 'vue'
import { usePetStore } from '../stores/pet'
import { useChatStore } from '../stores/chat'

const TICK_INTERVAL = 10 * 60 * 1000  // 10 minutes
const API_BASE = 'http://127.0.0.1'

let tickTimer = null
let port = 18765

async function getPort() {
  if (window.electronAPI) {
    port = await window.electronAPI.getPythonPort()
  }
  return port
}

async function fetchAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes`)
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性拉取失败:', e)
  }
}

async function tickAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes/tick`, { method: 'POST' })
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性 tick 失败:', e)
  }
}

async function tryDream(petStore, chatStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/dream`, { method: 'POST' })
    if (!res.ok) return
    const data = await res.json()
    if (data.status === 'success' && data.dream_text) {
      if (data.attributes) petStore.applyAttributes(data.attributes)
      // Show dream text after waking up (3s delay)
      setTimeout(() => {
        if (chatStore?.showMessage) {
          chatStore.showMessage(`(梦到了) ${data.dream_text}`, 6000)
        }
      }, 3000)
    }
  } catch (e) {
    console.warn('做梦请求失败:', e)
  }
}

export function usePetAttributeTicker() {
  const petStore = usePetStore()
  const chatStore = useChatStore()

  function init() {
    fetchAttributes(petStore)
    tickTimer = setInterval(() => tickAttributes(petStore), TICK_INTERVAL)
    watch(() => petStore.currentState, (newState) => {
      if (newState === 'sleep') tryDream(petStore, chatStore)
    })
  }

  function destroy() {
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
  }

  return { init, destroy }
}

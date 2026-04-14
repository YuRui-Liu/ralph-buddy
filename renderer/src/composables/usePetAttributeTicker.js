/**
 * usePetAttributeTicker — 宠物属性定时同步 + 睡眠/做梦/醒来流程
 */
import { watch } from 'vue'
import { usePetStore } from '../stores/pet'
import { useChatStore } from '../stores/chat'
import { apiFetch } from '../utils/api'

const TICK_INTERVAL = 10 * 60 * 1000  // 10 minutes
const DREAM_DELAY = 30 * 1000         // 进入睡眠 30 秒后触发做梦
const MAX_SLEEP = 5 * 60 * 1000       // 最长睡眠 5 分钟

let tickTimer = null
let sleepDreamTimer = null
let sleepMaxTimer = null
let behaviorSequencer = null  // 由外部注入

async function fetchAttributes(petStore) {
  try {
    const res = await apiFetch('/api/pet/attributes')
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
    const res = await apiFetch('/api/pet/attributes/tick', { method: 'POST' })
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性 tick 失败:', e)
  }
}

// ── 做梦 + 图片生成 ──

async function tryDream(petStore) {
  try {
    // Step 1: 触发做梦
    const res = await apiFetch('/api/pet/dream', { method: 'POST' })
    if (!res.ok) return
    const data = await res.json()
    if (data.status !== 'success' || !data.dream_text) return

    if (data.attributes) petStore.applyAttributes(data.attributes)

    // 暂存梦境文字结果
    const dreamData = {
      text: data.dream_text,
      imageSrc: null,
      attributeDeltas: data.attribute_deltas || {},
    }

    // Step 2: 生成梦境图片（不阻塞，失败也无所谓）
    if (data.image_prompt) {
      try {
        const imgRes = await apiFetch('/api/dream/image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: data.image_prompt,
            event_id: data.event_id,
          }),
        })
        if (imgRes.ok) {
          const imgData = await imgRes.json()
          if (imgData.status === 'success' && imgData.image_base64) {
            dreamData.imageSrc = `data:image/png;base64,${imgData.image_base64}`
          }
        }
      } catch (e) {
        console.warn('[Dream] 图片生成失败:', e)
      }
    }

    // 暂存结果，醒来时展示
    petStore.dreamResult = dreamData
    console.log('[Dream] 梦境已生成，等待醒来展示')

  } catch (e) {
    console.warn('做梦请求失败:', e)
  }
}

// ── 醒来流程 ──

function wakeUp(petStore) {
  // 清理定时器
  if (sleepDreamTimer) { clearTimeout(sleepDreamTimer); sleepDreamTimer = null }
  if (sleepMaxTimer) { clearTimeout(sleepMaxTimer); sleepMaxTimer = null }

  // 播放醒来动画
  if (behaviorSequencer) {
    behaviorSequencer.trigger('wakeup')
  } else {
    petStore.setState('idle')
  }

  // 醒来后展示梦境气泡（延迟 2.5 秒，等 wakeup 动画播完）
  if (petStore.dreamResult) {
    setTimeout(() => {
      petStore.showDreamBubble = true
    }, 2500)
  }
}

// ── 进入睡眠 ──

function onSleepStart(petStore) {
  console.log('[Sleep] 进入睡眠')

  // 30 秒后做梦
  sleepDreamTimer = setTimeout(() => {
    tryDream(petStore)
  }, DREAM_DELAY)

  // 最长 5 分钟后自动醒来
  sleepMaxTimer = setTimeout(() => {
    console.log('[Sleep] 最长睡眠时间到，自动醒来')
    wakeUp(petStore)
  }, MAX_SLEEP)
}

function onSleepEnd(petStore) {
  console.log('[Sleep] 离开睡眠')
  // 如果是被外部唤醒（点击/互动），执行醒来流程
  wakeUp(petStore)
}

export function usePetAttributeTicker() {
  const petStore = usePetStore()
  const chatStore = useChatStore()

  function init() {
    fetchAttributes(petStore)
    tickTimer = setInterval(() => tickAttributes(petStore), TICK_INTERVAL)

    watch(() => petStore.currentState, (newState, oldState) => {
      if (newState === 'sleep' && oldState !== 'sleep') {
        onSleepStart(petStore)
      } else if (newState !== 'sleep' && oldState === 'sleep') {
        onSleepEnd(petStore)
      }
    })
  }

  function destroy() {
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
    if (sleepDreamTimer) { clearTimeout(sleepDreamTimer); sleepDreamTimer = null }
    if (sleepMaxTimer) { clearTimeout(sleepMaxTimer); sleepMaxTimer = null }
  }

  function setBehaviorSequencer(seq) {
    behaviorSequencer = seq
  }

  return { init, destroy, setBehaviorSequencer }
}

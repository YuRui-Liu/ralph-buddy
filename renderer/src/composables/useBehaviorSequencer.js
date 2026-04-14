/**
 * useBehaviorSequencer — 行为序列编排器
 *
 * 将多个元动作（pose + prop + 文字 + 声音）编排成"场景脚本"
 * 自组织调度：基于空闲时长、时间段、随机权重自动触发复杂行为
 */

import { ref, onUnmounted } from 'vue'

// ─── 行为脚本库 ────────────────────────────────────────────
export const BEHAVIOR_SCRIPTS = {

  // 学究模式：戴眼镜思考
  scholar: {
    id: 'scholar',
    label: '学究模式',
    cooldown: 1200000,   // 20分钟冷却
    weight: 6,
    trigger: { idleMinMs: 60000 },
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'prop',  value: 'glasses',    op: 'add' },
      { type: 'wait',  duration: 800 },
      { type: 'pose',  value: 'sit',        duration: 300 },
      { type: 'prop',  value: 'questionMark', op: 'add' },
      { type: 'bubble', text: '让我想想……' },
      { type: 'wait',  duration: 3000 },
      { type: 'prop',  value: 'questionMark', op: 'remove' },
      { type: 'bubble', text: '汪！我懂了！' },
      { type: 'pose',  value: 'bark',       duration: 600 },
      { type: 'wait',  duration: 1200 },
      { type: 'prop',  value: 'glasses',    op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 拿放大镜侦探模式
  investigate: {
    id: 'investigate',
    label: '侦探模式',
    cooldown: 900000,
    weight: 5,
    trigger: { idleMinMs: 90000 },
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 300 },
      { type: 'prop',  value: 'magnifier',  op: 'add' },
      { type: 'bubble', text: '（嗅嗅……有什么线索？）' },
      { type: 'wait',  duration: 4000 },
      { type: 'pose',  value: 'lick_screen', duration: 500 },
      { type: 'bubble', text: '就是这个味！' },
      { type: 'wait',  duration: 1500 },
      { type: 'prop',  value: 'magnifier',  op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 谄媚：靠近 + 卖萌
  flatter: {
    id: 'flatter',
    label: '谄媚讨好',
    cooldown: 300000,
    weight: 15,
    trigger: { idleMinMs: 10000 },
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'bubble', text: '主人主人主人！' },
      { type: 'wait',  duration: 2500 },
      { type: 'pose',  value: 'cuddle',     duration: 300 },
      { type: 'bubble', text: '摸我摸我~' },
      { type: 'wait',  duration: 2000 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 舔屏（随机）
  lickScreen: {
    id: 'lickScreen',
    label: '舔屏',
    cooldown: 600000,
    weight: 4,
    trigger: { idleMinMs: 30000 },
    steps: [
      { type: 'pose',  value: 'lick_screen', duration: 300 },
      { type: 'wait',  duration: 3000 },
      { type: 'bubble', text: '（嗯……有点咸）' },
      { type: 'wait',  duration: 1500 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 撒尿
  pee: {
    id: 'pee',
    label: '撒尿',
    cooldown: 1800000,   // 30分钟
    weight: 2,
    trigger: { idleMinMs: 120000 },
    steps: [
      { type: 'pose',  value: 'pee',        duration: 500 },
      { type: 'prop',  value: 'peeStream',  op: 'add' },
      { type: 'wait',  duration: 3500 },
      { type: 'prop',  value: 'peeStream',  op: 'remove' },
      { type: 'bubble', text: '好多了 (*≧▽≦)' },
      { type: 'wait',  duration: 1200 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 难过（随机情绪）
  sad: {
    id: 'sad',
    label: '难过',
    cooldown: 1500000,
    weight: 3,
    trigger: { idleMinMs: 300000 },   // 5分钟无交互
    steps: [
      { type: 'pose',  value: 'sad',        duration: 600 },
      { type: 'bubble', text: '主人不理我了……' },
      { type: 'wait',  duration: 3000 },
      { type: 'bubble', text: '（假装若无其事地踢石头）' },
      { type: 'wait',  duration: 2000 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 兴奋蹦跳（收到交互后）
  excited: {
    id: 'excited',
    label: '兴奋',
    cooldown: 60000,
    weight: 20,
    trigger: { event: 'interaction' },   // 交互触发
    steps: [
      { type: 'pose',  value: 'happy_run',  duration: 200 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'wait',  duration: 1500 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  bedtime: {
    id: 'bedtime',
    label: '睡前仪式',
    cooldown: 3600000,
    weight: 10,
    trigger: { timeRange: [22, 6], idleMinMs: 600000 },
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'bubble', text: '好困……' },
      { type: 'wait',  duration: 2000 },
      { type: 'pose',  value: 'sleep',      duration: 800 },
      { type: 'prop',  value: 'zzzs',       op: 'add' },
      { type: 'bubble', text: '（呼呼……）' },
      { type: 'wait',  duration: 3000 },
    ],
  },

  // 醒来动画（由 usePetAttributeTicker 调用，不参与随机触发）
  wakeup: {
    id: 'wakeup',
    label: '醒来',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'prop',  value: 'zzzs',       op: 'remove' },
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'wait',  duration: 800 },
      { type: 'pose',  value: 'bark',       duration: 300 },
      { type: 'wait',  duration: 500 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // ─── 情绪观察 ───

  // 偷看动作（由 useEmotionObserver 主动调用，不参与随机触发）
  peek_observe: {
    id: 'peek_observe',
    label: '偷看',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'alert',      duration: 300 },
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'wait',  duration: 600 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：安慰（主人难过/害怕时）
  emotion_comfort: {
    id: 'emotion_comfort',
    label: '安慰主人',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'sad',        duration: 400 },
      { type: 'pose',  value: 'cuddle',     duration: 300 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'wait',  duration: 3000 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：开心（主人高兴时）
  emotion_happy_react: {
    id: 'emotion_happy_react',
    label: '跟着开心',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'happy_run',  duration: 200 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'wait',  duration: 2000 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：小心翼翼（主人生气时）
  emotion_cautious: {
    id: 'emotion_cautious',
    label: '小心翼翼',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'sad',        duration: 500 },
      { type: 'wait',  duration: 2000 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：好奇（主人惊讶时）
  emotion_curious: {
    id: 'emotion_curious',
    label: '好奇',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 300 },
      { type: 'wait',  duration: 1500 },
      { type: 'pose',  value: 'idle' },
    ],
  },
}

// ─── Composable ──────────────────────────────────────────────
export function useBehaviorSequencer(animator, chatStore, petStore) {
  const isRunning       = ref(false)
  const currentBehavior = ref(null)
  const lastInteraction = ref(Date.now())

  // 各行为的最后触发时间
  const lastTriggered   = new Map()

  let idleCheckTimer    = null
  let abortController   = null

  // ─── 通知最近有交互 ─────────────────────────────────────────
  function notifyInteraction() {
    lastInteraction.value = Date.now()
  }

  // ─── 执行一个行为脚本 ────────────────────────────────────────
  async function runBehavior(script) {
    if (isRunning.value) return
    isRunning.value = true
    currentBehavior.value = script.id
    lastTriggered.set(script.id, Date.now())

    const abort = new AbortController()
    abortController = abort

    try {
      for (const step of script.steps) {
        if (abort.signal.aborted) break
        await executeStep(step, abort.signal)
      }
    } finally {
      isRunning.value = false
      currentBehavior.value = null
      abortController = null
    }
  }

  async function executeStep(step, signal) {
    if (signal?.aborted) return

    switch (step.type) {
      case 'pose':
        animator.transitionTo(step.value)
        if (step.duration) await sleep(step.duration, signal)
        break

      case 'prop':
        if (step.op === 'add')    animator.addProp(step.value)
        if (step.op === 'remove') animator.removeProp(step.value)
        if (step.op === 'clear')  animator.clearProps()
        break

      case 'bubble':
        if (chatStore?.showMessage) {
          chatStore.showMessage(step.text, step.duration || 3000)
        }
        break

      case 'wait':
        await sleep(step.duration || 1000, signal)
        break
    }
  }

  function sleep(ms, signal) {
    return new Promise((resolve, reject) => {
      const t = setTimeout(resolve, ms)
      signal?.addEventListener('abort', () => { clearTimeout(t); resolve() })
    })
  }

  // ─── 中断当前行为 ──────────────────────────────────────────
  function interrupt() {
    abortController?.abort()
    animator.stop()
  }

  // ─── 自动调度：每 30 秒检查是否触发空闲行为 ─────────────────
  function startAutoSchedule() {
    idleCheckTimer = setInterval(() => {
      if (isRunning.value) return
      tryTriggerIdleBehavior()
    }, 30000)
  }

  function stopAutoSchedule() {
    if (idleCheckTimer) clearInterval(idleCheckTimer)
  }

  function tryTriggerIdleBehavior() {
    const now = Date.now()
    const idleMs = now - lastInteraction.value
    const hour = new Date().getHours()

    // 收集满足条件的候选行为
    const candidates = []

    for (const [id, script] of Object.entries(BEHAVIOR_SCRIPTS)) {
      if (!script.trigger) continue
      const last = lastTriggered.get(id) || 0
      if (now - last < script.cooldown) continue   // 冷却中

      const t = script.trigger
      // 检查空闲时间
      if (t.idleMinMs && idleMs < t.idleMinMs) continue
      // 检查时间段 [startHour, endHour]（跨午夜处理）
      if (t.timeRange) {
        const [s, e] = t.timeRange
        const inRange = s > e
          ? (hour >= s || hour < e)
          : (hour >= s && hour < e)
        if (!inRange) continue
      }
      // 事件驱动型跳过（由 triggerEvent 主动调用）
      if (t.event) continue

      candidates.push({ script, weight: script.weight })
    }

    // ── 属性联动权重修正 ──
    if (petStore) {
      for (const c of candidates) {
        const id = c.script.id
        const e  = petStore.energy
        const m  = petStore.mood
        const h  = petStore.health
        const af = petStore.affection

        if (e < 20) {
          if (id === 'bedtime')  c.weight *= 3
          if (id === 'excited' || id === 'flatter' || id === 'investigate') c.weight *= 0.2
        }
        if (m < 30) {
          if (id === 'sad')     c.weight *= 3
          if (id === 'flatter') c.weight *= 0.5
        }
        if (m > 80) {
          if (id === 'excited' || id === 'flatter') c.weight *= 2
        }
        if (h < 30) {
          if (id === 'bedtime')  c.weight *= 2
          if (id !== 'bedtime' && id !== 'sad') c.weight *= 0.3
        }
        if (af > 80) {
          if (id === 'flatter' || id === 'lickScreen') c.weight *= 2
        }
      }
    }

    if (candidates.length === 0) return

    // 加权随机选择
    const totalW = candidates.reduce((s, c) => s + c.weight, 0)
    let rand = Math.random() * totalW
    for (const c of candidates) {
      rand -= c.weight
      if (rand <= 0) {
        runBehavior(c.script)
        return
      }
    }
  }

  // ─── 事件触发型行为 ─────────────────────────────────────────
  function triggerEvent(eventName) {
    notifyInteraction()
    if (isRunning.value) return
    const candidates = Object.values(BEHAVIOR_SCRIPTS).filter(s => {
      if (s.trigger?.event !== eventName) return false
      const last = lastTriggered.get(s.id) || 0
      return Date.now() - last >= s.cooldown
    })
    if (candidates.length === 0) return
    // 简单取第一个（可扩展为加权）
    runBehavior(candidates[0])
  }

  // ─── 直接触发指定行为 ───────────────────────────────────────
  function trigger(behaviorId) {
    const script = BEHAVIOR_SCRIPTS[behaviorId]
    if (!script) return
    if (isRunning.value) interrupt()
    runBehavior(script)
  }

  // ─── 生命周期 ──────────────────────────────────────────────
  onUnmounted(() => stopAutoSchedule())

  return {
    isRunning,
    currentBehavior,
    startAutoSchedule,
    stopAutoSchedule,
    trigger,
    triggerEvent,
    notifyInteraction,
    interrupt,
    BEHAVIOR_SCRIPTS,
  }
}

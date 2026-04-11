/**
 * useNatureMode
 * 天性模式调度器。当天性模式开启且非专注模式时，每 5-15 分钟随机触发一次宠物行为。
 *
 * 用法（在 App.vue 中）：
 *   const petCanvasRef = ref(null)
 *   const { init, destroy } = useNatureMode(petCanvasRef)
 *   onMounted(() => init())
 *   onUnmounted(() => destroy())
 */

import { usePetStore, PetState } from '../stores/pet'
import { useUiStore } from '../stores/ui'
import { useChatStore } from '../stores/chat'
import { useSoundManager } from './useSoundManager'

// 预置互动文案池
const NATURE_PHRASES = [
  '汪！主人在干嘛呀～',
  '呜…来福想你了！',
  '主人，陪我玩嘛～',
  '汪汪！我刚才梦到骨头了！',
  '主人你有没有在偷偷看我？',
  '来福今天表现怎么样？',
  '汪！外面好像有动静！',
  '主人，摸摸我嘛～',
  '呜呜，来福饿了…',
  '汪！我爱你主人！'
]

// 动作 → 音效映射
const ACTION_SOUNDS = {
  [PetState.BARK]:      'bark_short',
  [PetState.HAPPY_RUN]: 'bark_happy',
  [PetState.CUDDLE]:    'whine',
  [PetState.CUTE]:      'whine',
  [PetState.LICK]:      null,
  [PetState.PEE]:       null,
}

// 随机间隔：5-15 分钟（ms）
function randomInterval() {
  return (5 + Math.random() * 10) * 60 * 1000
}

export function useNatureMode(petCanvasRef) {
  const petStore = usePetStore()
  const uiStore = useUiStore()
  const chatStore = useChatStore()
  const { playSound } = useSoundManager()

  let timer = null

  function scheduleNext() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(triggerBehavior, randomInterval())
  }

  function triggerBehavior() {
    // 条件检查：天性模式开启且非专注模式
    if (uiStore.natureMode && !uiStore.focusMode) {
      const action = petStore.getRandomBehavior()

      // 1. 触发动画
      if (petCanvasRef.value && petCanvasRef.value.transitionTo) {
        petCanvasRef.value.transitionTo(action)
      }

      // 2. 播放音效
      const soundName = ACTION_SOUNDS[action]
      if (soundName) {
        playSound(soundName)
      }

      // 3. 30% 概率显示预置文案气泡（3秒后自动关闭）
      if (Math.random() < 0.3) {
        const phrase = NATURE_PHRASES[Math.floor(Math.random() * NATURE_PHRASES.length)]
        chatStore.showMessage(phrase, 3000)
      }
    }

    // 无论是否触发，都继续调度下一次
    scheduleNext()
  }

  function init() {
    scheduleNext()
  }

  function destroy() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return { init, destroy }
}

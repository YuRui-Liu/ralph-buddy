import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 宠物状态枚举
export const PetState = {
  IDLE:       'idle',
  WALK:       'walk',
  SLEEP:      'sleep',
  LICK:       'lick_screen',
  CUDDLE:     'cuddle',
  CUTE:       'cute_pose',
  BARK:       'bark',
  PEE:        'pee',
  HAPPY_RUN:  'happy_run',
  // 2D 姿势模式新增
  SAD:        'sad',
  EXCITED:    'excited',
  DRAG:       'drag',       // 被拎着脖子拖动
  HELD_NECK:  'held_neck',  // 同上（静止版）
  SCHOLAR:    'scholar',    // 戴眼镜学究（由行为序列驱动）
  INVESTIGATE:'investigate',// 拿放大镜（由行为序列驱动）
  FLATTER:    'flatter',    // 谄媚
}

export const usePetStore = defineStore('pet', () => {
  // 状态
  const currentState = ref(PetState.IDLE)
  const targetPosition = ref({ x: 0, y: 0 })
  const isMoving = ref(false)
  const health = ref(80) // 0-100 健康值
  const affection = ref(50) // 0-100 好感度
  const mood = ref(50) // 0-100 心情值
  const energy = ref(80) // 0-100 精力值
  const obedience = ref(60) // 0-100 顺从度：越高越听话，低则任性调皮
  const snark = ref(30) // 0-100 毒舌值：越高说话越犀利直白，低则温和腼腆
  const lastInteraction = ref(Date.now())

  // 计算属性
  const isSleepy = computed(() => {
    const idleTime = Date.now() - lastInteraction.value
    return idleTime > 5 * 60 * 1000 // 5分钟无操作
  })

  // 方法
  function setState(state) {
    currentState.value = state
  }

  function setTargetPosition(x, y) {
    targetPosition.value = { x, y }
    isMoving.value = true
  }

  function stopMoving() {
    isMoving.value = false
  }

  function updateInteraction() {
    lastInteraction.value = Date.now()
  }

  function applyAttributes(attrs) {
    if (attrs.health    !== undefined) health.value    = Math.round(attrs.health)
    if (attrs.mood      !== undefined) mood.value      = Math.round(attrs.mood)
    if (attrs.energy    !== undefined) energy.value    = Math.round(attrs.energy)
    if (attrs.affection !== undefined) affection.value = Math.round(attrs.affection)
    if (attrs.obedience !== undefined) obedience.value = Math.round(attrs.obedience)
    if (attrs.snark     !== undefined) snark.value     = Math.round(attrs.snark)
  }

  // 天性模式：随机行为权重
  const idleBehaviors = [
    { action: PetState.LICK, weight: 0.05, cooldown: 300000 },
    { action: PetState.CUDDLE, weight: 0.15, cooldown: 60000 },
    { action: PetState.CUTE, weight: 0.20, cooldown: 30000 },
    { action: PetState.BARK, weight: 0.10, cooldown: 120000 },
    { action: PetState.PEE, weight: 0.02, cooldown: 600000 }
  ]

  function getRandomBehavior() {
    const totalWeight = idleBehaviors.reduce((sum, b) => sum + b.weight, 0)
    let random = Math.random() * totalWeight
    
    for (const behavior of idleBehaviors) {
      random -= behavior.weight
      if (random <= 0) {
        return behavior.action
      }
    }
    return PetState.IDLE
  }

  return {
    currentState,
    targetPosition,
    isMoving,
    health,
    affection,
    mood,
    energy,
    obedience,
    snark,
    lastInteraction,
    isSleepy,
    setState,
    setTargetPosition,
    stopMoving,
    updateInteraction,
    applyAttributes,
    getRandomBehavior
  }
})

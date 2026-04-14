/**
 * DogBuddy 程序化动画器
 *
 * 使用代码控制的变形/位移实现动画效果
 * 支持的动作：呼吸、尾巴摇摆、汪汪叫、卖萌、撒娇、舔屏、睡觉、奔跑等
 */

import { ref } from 'vue'
import { ProceduralAnimConfig } from '../config/animationConfig'
import { useSettingsStore } from '../stores/settings'
import { PetState } from '../stores/pet'

export function useProceduralAnim() {
  const settings = useSettingsStore()
  const cfg = ProceduralAnimConfig

  // 当前活动动画
  const currentAnim = ref(null)

  // Three.js 对象引用（由外部注入）
  let threeObj = null

  // 动画回调
  let currentActionResolve = null

  // ========== 初始化 ==========

  function init(obj) {
    threeObj = obj
  }

  // ========== 工具函数 ==========

  function getIntensity() {
    return settings.animationIntensity
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3)
  }

  // 数值动画
  function animateValue(from, to, duration, onUpdate, onComplete) {
    const startTime = Date.now()

    function tick() {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = easeOutCubic(progress)
      const value = from + (to - from) * eased

      onUpdate(value)

      if (progress < 1) {
        requestAnimationFrame(tick)
      } else {
        onComplete?.()
      }
    }

    tick()
  }

  function resetPosition() {
    if (!threeObj?.model) return
    threeObj.model.position.y = threeObj.baseY
    threeObj.model.rotation.x = 0
    threeObj.model.rotation.y = 0
    threeObj.model.rotation.z = 0
  }

  // ========== 持续动画 ==========

  function playBreath(time) {
    if (!threeObj?.model) return
    const { amplitude, speed, scaleY, scaleX, scaleZ } = cfg.BREATH
    const i = getIntensity()

    threeObj.model.position.y = threeObj.baseY + Math.sin(time * speed) * amplitude * i
    threeObj.model.scale.y = 1 + Math.sin(time * speed) * scaleY * i
    threeObj.model.scale.x = 1 - Math.sin(time * speed) * scaleX * i
    threeObj.model.scale.z = 1 - Math.sin(time * speed) * scaleZ * i
  }

  function playWagTail(time) {
    if (!threeObj?.tail) return
    const { angle, speed } = cfg.WAG_TAIL
    const i = getIntensity()
    threeObj.tail.rotation.z = Math.sin(time * speed) * angle * i
  }

  function playWalk(time) {
    if (!threeObj?.model) return
    const { bounceHeight, swayAngle, speed } = cfg.WALK
    const i = getIntensity()
    threeObj.model.position.y = threeObj.baseY + Math.abs(Math.sin(time * speed)) * bounceHeight * i
    threeObj.model.rotation.z = Math.sin(time * speed) * swayAngle * i
  }

  // ========== 触发式动画 ==========

  function playBark() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { bounceHeight, bounceCount, duration, shakeAngle } = cfg.BARK
      const i = getIntensity()
      let count = 0
      const startY = threeObj.model.position.y

      currentAnim.value = 'bark'

      function bounce() {
        if (count >= bounceCount) {
          resetPosition()
          currentAnim.value = null
          resolve()
          return
        }

        animateValue(startY, startY + bounceHeight * i, duration / 2,
          (val) => { threeObj.model.position.y = val },
          () => {
            animateValue(startY + bounceHeight * i, startY, duration / 2,
              (val) => {
                threeObj.model.position.y = val
                threeObj.model.rotation.z = Math.sin(Date.now() * 0.05) * shakeAngle * i
              },
              () => { count++; bounce() }
            )
          }
        )
      }

      bounce()
    })
  }

  function playCute() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { angle, duration, holdTime } = cfg.CUTE
      const i = getIntensity()
      const originalZ = threeObj.model.rotation.z || 0

      currentAnim.value = 'cute'

      animateValue(0, angle * i, duration / 4,
        (val) => { threeObj.model.rotation.z = originalZ + val },
        () => {
          setTimeout(() => {
            animateValue(angle * i, -angle * i * 0.5, duration / 4,
              (val) => { threeObj.model.rotation.z = originalZ + val },
              () => {
                animateValue(-angle * i * 0.5, 0, duration / 4,
                  (val) => { threeObj.model.rotation.z = originalZ + val },
                  () => { currentAnim.value = null; resolve() }
                )
              }
            )
          }, holdTime)
        }
      )
    })
  }

  function playCuddle() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { angle, speed, duration } = cfg.CUDDLE
      const i = getIntensity()
      const startTime = Date.now()

      currentAnim.value = 'cuddle'

      function sway() {
        const elapsed = Date.now() - startTime
        if (elapsed >= duration) {
          threeObj.model.rotation.z = 0
          currentAnim.value = null
          resolve()
          return
        }
        threeObj.model.rotation.z = Math.sin(elapsed * speed * 0.01) * angle * i
        requestAnimationFrame(sway)
      }

      sway()
    })
  }

  function playLick() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { forwardAngle, heightOffset, duration, holdTime } = cfg.LICK
      const i = getIntensity()
      const originalX = threeObj.model.rotation.x || 0

      currentAnim.value = 'lick'

      animateValue(0, forwardAngle * i, duration / 4,
        (val) => {
          threeObj.model.rotation.x = originalX + val
          threeObj.model.position.y = threeObj.baseY + val * heightOffset * 10
        },
        () => {
          setTimeout(() => {
            animateValue(forwardAngle * i, 0, duration / 2,
              (val) => {
                threeObj.model.rotation.x = originalX + val
                threeObj.model.position.y = threeObj.baseY + val * heightOffset * 10
              },
              () => { currentAnim.value = null; resolve() }
            )
          }, holdTime)
        }
      )
    })
  }

  function playSleep() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { lieDownAngle, targetY, transitionDuration } = cfg.SLEEP

      currentAnim.value = 'sleep'

      animateValue(0, lieDownAngle, transitionDuration,
        (val) => { threeObj.model.rotation.x = val },
        () => {
          threeObj.model.position.y = targetY
          currentAnim.value = 'sleeping'
          resolve()
        }
      )
    })
  }

  function wakeUp() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      currentAnim.value = 'wake'

      animateValue(-Math.PI / 2, 0, 500,
        (val) => {
          threeObj.model.rotation.x = val
          if (val > -0.5) threeObj.model.position.y = threeObj.baseY
        },
        () => { currentAnim.value = null; resolve() }
      )
    })
  }

  function playHappyRun() {
    return new Promise((resolve) => {
      if (!threeObj?.model) { resolve(); return }

      const { bounceHeight, bodySway } = cfg.HAPPY_RUN
      const i = getIntensity()
      const startTime = Date.now()

      currentAnim.value = 'happy_run'

      function run() {
        if (currentAnim.value !== 'happy_run') { resolve(); return }

        const t = Date.now() * 0.01
        threeObj.model.position.y = threeObj.baseY + Math.abs(Math.sin(t * 2)) * bounceHeight * i
        threeObj.model.rotation.z = Math.sin(t) * bodySway * i
        if (threeObj.tail) threeObj.tail.rotation.z = Math.sin(t * 3) * 0.8

        requestAnimationFrame(run)
      }

      run()
    })
  }

  // ========== 统一播放接口 ==========

  async function play(action, loop = false) {
    if (!threeObj) {
      console.warn('[ProceduralAnim] 未初始化')
      return
    }

    console.log(`[ProceduralAnim] 播放: ${action}`)

    switch (action) {
      case PetState.IDLE:
        resetPosition()
        currentAnim.value = 'idle'
        break
      case PetState.WALK:
        currentAnim.value = 'walk'
        break
      case PetState.SLEEP:
        await playSleep()
        break
      case PetState.LICK:
        await playLick()
        break
      case PetState.CUDDLE:
        await playCuddle()
        break
      case PetState.CUTE:
        await playCute()
        break
      case PetState.BARK:
        await playBark()
        break
      case PetState.PEE:
        await playCuddle()
        break
      case PetState.HAPPY_RUN:
        await playHappyRun()
        break
      default:
        resetPosition()
    }
  }

  function stop() {
    currentAnim.value = null
    currentActionResolve = null
    resetPosition()
  }

  function update(time, currentState) {
    if (!threeObj?.model) return

    if (currentAnim.value === 'idle' || currentAnim.value === null) {
      playBreath(time)
      playWagTail(time)
    } else if (currentAnim.value === 'walk' || currentState === PetState.WALK) {
      playWalk(time)
      playWagTail(time)
    } else if (currentAnim.value === 'sleeping') {
      const { breatheSpeed, breatheAmp } = cfg.SLEEP
      threeObj.model.position.y = threeObj.model.position.y + Math.sin(time * breatheSpeed) * breatheAmp
    }
  }

  return {
    currentAnim,
    init,
    play,
    stop,
    update,
    wakeUp,
    resetPosition,
    playBark,
    playCute,
    playCuddle,
    playLick,
    playSleep,
    playHappyRun
  }
}

export default useProceduralAnim

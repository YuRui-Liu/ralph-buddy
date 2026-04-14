/**
 * 切图动画器 - Sprite Animator
 *
 * 使用 Canvas 2D 渲染 PNG 切图组成的宠物
 * 通过程序化变换实现各种动画效果
 */

import { ref, shallowRef, onUnmounted } from 'vue'
import {
  layoutConfig,
  animationConfig,
  actionDefinitions,
  easings
} from '@/config/spriteAnimationConfig'

export function useSpriteAnimator() {
  // ============ 状态 ============
  const canvasRef = ref(null)
  const ctx = shallowRef(null)
  const isReady = ref(false)
  const currentAction = ref('IDLE')
  const isPlaying = ref(false)

  // 部位对象
  const parts = shallowRef({})

  // 循环动画
  const loops = new Map()

  // 定时器
  let animationFrameId = null
  let blinkInterval = null
  let startTime = 0

  // ============ 加载图片 ============
  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = src
    })
  }

  async function loadSprites(spritePath = '/sprites/dog') {
    const basePath = `${spritePath}/base`
    const statesPath = `${spritePath}/states`

    const paths = {
      body: `${basePath}/body.png`,
      head: `${basePath}/head.png`,
      tail: `${basePath}/tail.png`,
      eye_left: `${basePath}/eye_left.png`,
      eye_right: `${basePath}/eye_right.png`,
      mouth: `${basePath}/mouth_default.png`,
      ear_left: `${basePath}/ear_left.png`,
      ear_right: `${basePath}/ear_right.png`,
      paw_left: `${basePath}/paw_left.png`,
      paw_right: `${basePath}/paw_right.png`,
      // 状态图
      eye_closed: `${statesPath}/eye_closed.png`,
      mouth_open: `${statesPath}/mouth_open.png`,
      tongue_out: `${statesPath}/tongue_out.png`
    }

    const loaded = {}
    for (const [key, path] of Object.entries(paths)) {
      try {
        loaded[key] = await loadImage(path)
      } catch (e) {
        console.warn(`[SpriteAnimator] Failed to load: ${path}`)
      }
    }

    // 初始化部位
    parts.value = {
      body: createPart(loaded.body, 'body'),
      head: createPart(loaded.head, 'head'),
      tail: createPart(loaded.tail, 'tail'),
      eye_left: createPart(loaded.eye_left, 'eye_left'),
      eye_right: createPart(loaded.eye_right, 'eye_right'),
      mouth: createPart(loaded.mouth, 'mouth'),
      ear_left: createPart(loaded.ear_left, 'ear_left'),
      ear_right: createPart(loaded.ear_right, 'ear_right'),
      paw_left: createPart(loaded.paw_left, 'paw_left'),
      paw_right: createPart(loaded.paw_right, 'paw_right'),
      // 状态图缓存
      states: {
        eye_closed: loaded.eye_closed,
        mouth_open: loaded.mouth_open,
        tongue_out: loaded.tongue_out
      }
    }

    isReady.value = true
  }

  // ============ 创建部位对象 ============
  function createPart(image, name) {
    const anchor = layoutConfig.anchors[name] || { x: 0, y: 0 }
    const scale = layoutConfig.scales[name] || { x: 0.5, y: 0.5 }

    return {
      name,
      image,
      x: anchor.x,
      y: anchor.y,
      offsetX: 0,
      offsetY: 0,
      scaleX: scale.x,
      scaleY: scale.y,
      rotation: 0,
      rotationX: 0,
      rotationY: 0,
      opacity: 1,
      anchorX: 0.5,
      anchorY: 0.5,
      // 状态相关
      state: 'default',
      isBlinking: false,
      // 原始锚点
      baseX: anchor.x,
      baseY: anchor.y,
      baseScaleX: scale.x,
      baseScaleY: scale.y
    }
  }

  // ============ 渲染循环 ============
  function startRender() {
    if (animationFrameId) return

    startTime = performance.now()
    render()
  }

  function render(timestamp = 0) {
    if (!ctx.value) return

    const canvas = canvasRef.value
    if (!canvas) return

    const elapsed = (timestamp - startTime) / 1000

    // 清空画布
    ctx.value.clearRect(0, 0, canvas.width, canvas.height)

    // 绘制阴影
    drawShadow(ctx.value, canvas.width / 2, canvas.height - 50, currentAction.value)

    // 更新循环动画
    updateLoops(elapsed)

    // 绘制所有部位（按层级顺序）
    const drawOrder = ['tail', 'paw_left', 'paw_right', 'body', 'ear_left', 'ear_right', 'head', 'eye_left', 'eye_right', 'mouth']

    for (const name of drawOrder) {
      const part = parts.value[name]
      if (part && part.image && part.opacity > 0) {
        drawPart(ctx.value, part)
      }
    }

    animationFrameId = requestAnimationFrame(render)
  }

  function drawShadow(ctx, x, y, action) {
    ctx.save()
    ctx.fillStyle = 'rgba(0, 0, 0, 0.15)'

    let scaleX = 1
    let scaleY = 0.3

    // 根据动作调整阴影
    if (action === 'BARK' || action === 'HAPPY_RUN') {
      scaleY = 0.25
    } else if (action === 'SLEEP') {
      scaleX = 1.3
      scaleY = 0.2
    }

    ctx.beginPath()
    ctx.ellipse(x, y, 60 * scaleX, 20 * scaleY, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }

  function drawPart(ctx, part) {
    if (!part.image) return

    ctx.save()

    // 应用变换
    const centerX = part.x + part.offsetX
    const centerY = part.y + part.offsetY

    ctx.translate(centerX, centerY)
    ctx.rotate(part.rotation)
    ctx.scale(part.scaleX, part.scaleY)
    ctx.globalAlpha = part.opacity

    // 绘制图片
    const img = part.image
    const w = img.width
    const h = img.height

    ctx.drawImage(img, -w * part.anchorX, -h * part.anchorY, w, h)

    ctx.restore()
  }

  // ============ 循环动画更新 ============
  function updateLoops(elapsed) {
    const body = parts.value.body
    const tail = parts.value.tail
    const head = parts.value.head
    const eyes = [parts.value.eye_left, parts.value.eye_right]

    // 呼吸动画
    if (loops.has('breathe') && body) {
      const cfg = loops.get('breathe')
      const breatheValue = Math.sin(elapsed * cfg.speed) * cfg.amplitude
      body.scaleX = body.baseScaleX * (cfg.scaleX + breatheValue)
      body.scaleY = body.baseScaleY * (cfg.scaleY + breatheValue)
    }

    // 尾巴摇摆
    if (loops.has('tailWag') && tail) {
      const cfg = loops.get('tailWag')
      const variance = Math.sin(elapsed * 10) * cfg.variance
      tail.rotation = Math.sin(elapsed * cfg.speed) * (cfg.angle + variance)
    }

    // 身体摇晃
    if (loops.has('bodySway') && body) {
      const cfg = loops.get('bodySway')
      body.rotation = Math.sin(elapsed * cfg.speed) * cfg.angle
    }

    // 弹跳
    if (loops.has('bounce') && body) {
      const cfg = loops.get('bounce')
      body.offsetY = Math.abs(Math.sin(elapsed * cfg.speed)) * cfg.height * -1
    }

    // 疯狂尾巴
    if (loops.has('crazyTail') && tail) {
      const cfg = loops.get('crazyTail')
      tail.rotation = Math.sin(elapsed * cfg.speed) * cfg.angle
    }

    // 撒娇摇晃
    if (loops.has('sway') && body) {
      const cfg = loops.get('sway')
      body.rotation = Math.sin(elapsed * cfg.speed) * cfg.angle
    }

    // 兴奋尾巴
    if (loops.has('tailExcited') && tail) {
      const cfg = loops.get('tailExcited')
      tail.rotation = Math.sin(elapsed * cfg.speed) * cfg.angle
    }

    // 睡觉呼吸
    if (loops.has('sleepBreathe') && body) {
      const breatheValue = Math.sin(elapsed * 1.5) * 0.02
      body.scaleY = body.baseScaleY * (1 + breatheValue)
    }

    // 跑步爪子
    if (loops.has('run')) {
      const cfg = loops.get('run')
      const paws = [parts.value.paw_left, parts.value.paw_right]
      paws.forEach((paw, i) => {
        if (paw) {
          const offset = i === 0 ? 0 : Math.PI
          paw.rotation = Math.sin(elapsed * cfg.speed + offset) * cfg.angle
        }
      })
    }
  }

  // ============ 动画控制 ============
  async function animate(from, to, duration, easing = 'easeOutQuad') {
    return new Promise(resolve => {
      const startTime = performance.now()

      function step(now) {
        const elapsed = now - startTime
        const progress = Math.min(elapsed / duration, 1)
        const eased = easings[easing] ? easings[easing](progress) : progress

        const value = from + (to - from) * eased

        if (progress < 1) {
          requestAnimationFrame(step)
        }

        resolve(value)
      }

      requestAnimationFrame(step)
    })
  }

  async function animatePart(part, props, duration, easing) {
    const fromValues = {}
    const toValues = {}

    for (const [key, to] of Object.entries(props)) {
      fromValues[key] = part[key]
      toValues[key] = to
    }

    const startTime = performance.now()

    return new Promise(resolve => {
      function step(now) {
        const progress = Math.min((now - startTime) / duration, 1)
        const eased = easings[easing] ? easings[easing](progress) : progress

        for (const [key, from] of Object.entries(fromValues)) {
          part[key] = from + (toValues[key] - from) * eased
        }

        if (progress < 1) {
          requestAnimationFrame(step)
        } else {
          resolve()
        }
      }

      requestAnimationFrame(step)
    })
  }

  function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  // ============ 动作播放 ============
  async function play(actionName) {
    if (!isReady.value) {
      console.warn('[SpriteAnimator] Not ready')
      return
    }

    // 停止之前的动作
    stopCurrentAction()
    currentAction.value = actionName
    isPlaying.value = true

    const actionDef = actionDefinitions[actionName]
    if (!actionDef) {
      console.warn(`[SpriteAnimator] Unknown action: ${actionName}`)
      return
    }

    try {
      // 启动循环动画
      if (actionDef.loops) {
        for (const [loopName, params] of Object.entries(actionDef.loopsParams || {})) {
          loops.set(loopName, params)
        }
      }

      // 执行序列动画
      if (actionDef.sequence) {
        for (const step of actionDef.sequence) {
          await executeStep(step)
        }
      }

      // 持续循环直到被中断
      if (actionDef.duration) {
        await wait(actionDef.duration)
      }

    } catch (e) {
      console.error('[SpriteAnimator] Action error:', e)
    } finally {
      isPlaying.value = false
    }
  }

  async function executeStep(step) {
    const { part: partName, action, times = 1, duration, interval = 0, reverse } = step

    if (!partName || !action) return

    const part = parts.value[partName]
    if (!part) return

    for (let i = 0; i < times; i++) {
      const cfg = animationConfig[partName]?.[action]
      if (!cfg) continue

      switch (action) {
        case 'tilt':
          const angle = reverse ? 0 : cfg.angle
          await animatePart(part, { rotation: angle }, cfg.duration, cfg.ease)
          if (cfg.holdTime && !reverse) {
            await wait(cfg.holdTime)
            await animatePart(part, { rotation: 0 }, cfg.duration * 0.7, 'easeInOut')
          }
          break

        case 'lean':
          const offsetY = reverse ? 0 : cfg.offsetY
          await animatePart(part, { offsetY, rotationX: reverse ? 0 : cfg.offsetX ? 0 : 0.2 }, cfg.duration, cfg.ease)
          break

        case 'bounce':
          const height = cfg.height || 15
          await animatePart(part, { offsetY: -height }, duration || 150, 'easeOut')
          await animatePart(part, { offsetY: 0 }, duration || 150, 'easeIn')
          break

        case 'shake':
          await animatePart(part, { rotation: cfg.angle }, duration || 50, 'linear')
          await animatePart(part, { rotation: -cfg.angle }, duration || 50, 'linear')
          break

        case 'open':
          swapState(part, 'mouth_open')
          await wait(duration || 150)
          swapState(part, 'default')
          break

        case 'tongue':
          swapState(part, 'tongue_out')
          await wait(duration || 200)
          swapState(part, 'mouth_open')
          await wait(duration || 200)
          break

        case 'widen':
          await animatePart(part, { scaleX: part.baseScaleX * 1.4, scaleY: part.baseScaleY * 1.4 }, duration || 300)
          break
      }

      if (interval > 0) {
        await wait(interval)
      }
    }
  }

  function swapState(part, newState) {
    if (!part) return

    switch (part.name) {
      case 'eye_left':
      case 'eye_right':
        if (newState === 'default') {
          part.state = 'default'
          part.image = parts.value[part.name]?.image
        } else if (newState === 'closed') {
          part.state = 'closed'
          part.image = parts.value.states?.eye_closed
        }
        break
      case 'mouth':
        if (newState === 'default') {
          part.image = parts.value.mouth?.image
        } else if (parts.value.states?.[newState]) {
          part.image = parts.value.states[newState]
        }
        break
    }
  }

  // ============ 眨眼 ============
  function startBlinkLoop() {
    const cfg = animationConfig.eyes.blink

    blinkInterval = setInterval(() => {
      if (Math.random() < cfg.probability && !isPlaying.value) {
        blink()
      }
    }, cfg.interval)
  }

  async function blink() {
    const leftEye = parts.value.eye_left
    const rightEye = parts.value.eye_right
    const cfg = animationConfig.eyes.blink

    if (!leftEye || !rightEye) return

    // 闭眼
    swapState(leftEye, 'closed')
    swapState(rightEye, 'closed')
    await wait(cfg.duration)

    // 睁眼
    swapState(leftEye, 'default')
    swapState(rightEye, 'default')
  }

  // ============ 停止 ============
  function stopCurrentAction() {
    // 清除所有循环
    loops.clear()

    // 重置部位状态
    for (const part of Object.values(parts.value)) {
      if (part && part.baseScaleX !== undefined) {
        part.scaleX = part.baseScaleX
        part.scaleY = part.baseScaleY
        part.rotation = 0
        part.rotationX = 0
        part.offsetX = 0
        part.offsetY = 0
      }
    }

    // 重置嘴巴状态
    if (parts.value.mouth) {
      parts.value.mouth.image = parts.value.mouth?.image
    }
  }

  function stop() {
    stopCurrentAction()
    currentAction.value = 'IDLE'
    isPlaying.value = false
  }

  function transitionTo(actionName) {
    play(actionName)
  }

  // ============ 生命周期 ============
  function init(canvas) {
    canvasRef.value = canvas
    ctx.value = canvas.getContext('2d')

    // 设置画布尺寸
    canvas.width = layoutConfig.canvas.width
    canvas.height = layoutConfig.canvas.height

    // 启动渲染
    startRender()

    // 启动眨眼循环
    startBlinkLoop()

    // 默认播放待机
    play('IDLE')
  }

  onUnmounted(() => {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
    }
    if (blinkInterval) {
      clearInterval(blinkInterval)
    }
    stopCurrentAction()
  })

  return {
    // 状态
    isReady,
    currentAction,
    isPlaying,

    // 方法
    init,
    loadSprites,
    play,
    stop,
    transitionTo,
    blink,

    // 调试
    parts,
    loops
  }
}

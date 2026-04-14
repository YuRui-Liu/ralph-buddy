/**
 * usePoseAnimator — 来福 2D 姿势动画器
 *
 * 基于 SVG 整体姿势图 + Canvas 2D 程序化微动效
 * 支持道具叠加层（眼镜、放大镜等）、拖拽提颈状态
 */

import { ref, shallowRef, onUnmounted } from 'vue'

// ─── 姿势 → SVG 文件名映射 ──────────────────────────────────
const POSE_MAP = {
  idle:       'idle',
  walk:       'idle',
  happy_run:  'excited',
  bark:       'excited',
  cute_pose:  'sit',
  cuddle:     'sit',
  lick_screen:'lick',
  pee:        'pee',
  sleep:      'sleep',
  sad:        'sad',
  drag:       'held_neck',   // 拖拽时自动切换
  held_neck:  'held_neck',
  excited:    'excited',
}

// ─── 每种动画状态的微动效参数 ───────────────────────────────
const MICRO_ANIM = {
  idle:       { bobAmp: 3,   bobSpeed: 1.4, swayAmp: 0,   swaySpeed: 0,  bounceAmp: 0,  breathAmp: 0.012 },
  walk:       { bobAmp: 5,   bobSpeed: 3.0, swayAmp: 3,   swaySpeed: 3.0,bounceAmp: 0,  breathAmp: 0.008 },
  happy_run:  { bobAmp: 10,  bobSpeed: 6.0, swayAmp: 0,   swaySpeed: 0,  bounceAmp: 0,  breathAmp: 0.006 },
  bark:       { bobAmp: 8,   bobSpeed: 5.0, swayAmp: 0,   swaySpeed: 0,  bounceAmp: 0,  breathAmp: 0.006 },
  cute_pose:  { bobAmp: 2,   bobSpeed: 1.2, swayAmp: 2,   swaySpeed: 1.0,bounceAmp: 0,  breathAmp: 0.015 },
  cuddle:     { bobAmp: 2,   bobSpeed: 1.0, swayAmp: 4,   swaySpeed: 1.5,bounceAmp: 0,  breathAmp: 0.015 },
  lick_screen:{ bobAmp: 1,   bobSpeed: 1.0, swayAmp: 1.5, swaySpeed: 2.0,bounceAmp: 0,  breathAmp: 0.010 },
  pee:        { bobAmp: 1.5, bobSpeed: 2.0, swayAmp: 1,   swaySpeed: 2.5,bounceAmp: 0,  breathAmp: 0.008 },
  sleep:      { bobAmp: 0.5, bobSpeed: 0.6, swayAmp: 0,   swaySpeed: 0,  bounceAmp: 0,  breathAmp: 0.025 },
  sad:        { bobAmp: 1,   bobSpeed: 0.8, swayAmp: 0,   swaySpeed: 0,  bounceAmp: 0,  breathAmp: 0.018 },
  drag:       { bobAmp: 6,   bobSpeed: 3.0, swayAmp: 5,   swaySpeed: 2.0,bounceAmp: 0,  breathAmp: 0.006 },
  held_neck:  { bobAmp: 6,   bobSpeed: 3.0, swayAmp: 5,   swaySpeed: 2.0,bounceAmp: 0,  breathAmp: 0.006 },
}

// ─── 道具定义（纯 Canvas 代码绘制，无需图片）───────────────
const PROP_DRAWERS = {
  glasses(ctx, cx, cy) {
    // 眼镜戴在眼部位置（cy 基准在头部偏下，-20 上移到眼睛）
    const ey = cy - 20
    ctx.save()
    ctx.strokeStyle = '#555'
    ctx.lineWidth = 2.5
    ctx.fillStyle = 'rgba(150,200,255,0.18)'
    // 左镜片
    ctx.beginPath(); ctx.arc(cx - 18, ey, 11, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
    // 右镜片
    ctx.beginPath(); ctx.arc(cx + 18, ey, 11, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
    // 鼻梁
    ctx.beginPath(); ctx.moveTo(cx - 7, ey); ctx.lineTo(cx + 7, ey); ctx.stroke()
    // 左镜腿
    ctx.beginPath(); ctx.moveTo(cx - 29, ey); ctx.lineTo(cx - 42, ey - 4); ctx.stroke()
    // 右镜腿
    ctx.beginPath(); ctx.moveTo(cx + 29, ey); ctx.lineTo(cx + 42, ey - 4); ctx.stroke()
    ctx.restore()
  },

  magnifier(ctx, cx, cy, t) {
    // 放大镜举在眼部右侧（cy 基准在头部偏下，-12 上移到眼睛附近）
    const angle = Math.sin(t * 1.5) * 0.12
    ctx.save()
    ctx.translate(cx + 38, cy - 12)
    ctx.rotate(angle)
    ctx.strokeStyle = '#8B6914'
    ctx.lineWidth = 5
    ctx.lineCap = 'round'
    // 手柄
    ctx.beginPath(); ctx.moveTo(14, 14); ctx.lineTo(28, 28); ctx.stroke()
    // 镜框
    ctx.strokeStyle = '#555'
    ctx.lineWidth = 3
    ctx.fillStyle = 'rgba(180,220,255,0.22)'
    ctx.beginPath(); ctx.arc(0, 0, 18, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
    // 高光
    ctx.strokeStyle = 'rgba(255,255,255,0.5)'
    ctx.lineWidth = 2
    ctx.beginPath(); ctx.arc(-5, -5, 8, -Math.PI * 0.8, -Math.PI * 0.2); ctx.stroke()
    ctx.restore()
  },

  questionMark(ctx, cx, cy, t) {
    const bounce = Math.sin(t * 3) * 3
    ctx.save()
    ctx.font = 'bold 26px sans-serif'
    ctx.fillStyle = '#FFA500'
    ctx.textAlign = 'center'
    ctx.fillText('?', cx + 45, cy - 55 + bounce)
    ctx.restore()
  },

  hearts(ctx, cx, cy, t) {
    const positions = [[-45, -50], [45, -55], [-50, -30]]
    positions.forEach(([dx, dy], i) => {
      const alpha = 0.5 + Math.sin(t * 2 + i) * 0.3
      const scale = 0.7 + Math.sin(t * 1.5 + i) * 0.15
      ctx.save()
      ctx.globalAlpha = alpha
      ctx.font = `${Math.round(18 * scale)}px sans-serif`
      ctx.textAlign = 'center'
      ctx.fillText('♥', cx + dx, cy + dy)
      ctx.restore()
    })
  },

  peeStream(ctx, cx, cy, t) {
    // 从宠物后腿/臀部区域流出（cy 基准在头部，+90 到臀部，+140 到地面）
    const alpha = 0.7 + Math.sin(t * 8) * 0.1
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.strokeStyle = 'rgba(255,220,50,0.85)'
    ctx.lineWidth = 4
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(cx + 20, cy + 85)
    ctx.quadraticCurveTo(cx + 42, cy + 110, cx + 48, cy + 135)
    ctx.stroke()
    // 水坑
    ctx.fillStyle = 'rgba(255,220,50,0.35)'
    ctx.beginPath()
    ctx.ellipse(cx + 48, cy + 140, 18, 6, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  },

  sweatDrops(ctx, cx, cy, t) {
    const y = cy - 40 + Math.sin(t * 4) * 3
    ctx.save()
    ctx.fillStyle = 'rgba(100,160,230,0.75)'
    // 左汗滴
    ctx.beginPath()
    ctx.arc(cx - 52, y, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(cx - 52, y - 6)
    ctx.lineTo(cx - 56, y - 16)
    ctx.lineTo(cx - 48, y - 16)
    ctx.fill()
    // 右汗滴
    ctx.beginPath()
    ctx.arc(cx + 52, y, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(cx + 52, y - 5)
    ctx.lineTo(cx + 48, y - 14)
    ctx.lineTo(cx + 56, y - 14)
    ctx.fill()
    ctx.restore()
  },

  zzzs(ctx, cx, cy, t) {
    const letters = ['z', 'z', 'z']
    letters.forEach((z, i) => {
      const progress = ((t * 0.5 + i * 0.3) % 1.0)
      const alpha = progress < 0.7 ? progress / 0.7 : (1 - progress) / 0.3
      const x = cx + 20 + i * 12 + progress * 8
      const y = cy - 40 - i * 14 - progress * 6
      const size = 14 + i * 3
      ctx.save()
      ctx.globalAlpha = alpha * 0.8
      ctx.font = `bold ${size}px sans-serif`
      ctx.fillStyle = '#8AB'
      ctx.fillText(z.toUpperCase(), x, y)
      ctx.restore()
    })
  },
}

// ─── Composable ──────────────────────────────────────────────
export function usePoseAnimator(spritePath = '/rhyfu/sprites') {
  const canvasRef     = ref(null)
  const isReady       = ref(false)
  const currentState  = ref('idle')
  const isDragging    = ref(false)

  // 已加载的 Image 对象
  const poseImages    = shallowRef({})
  // 当前激活的道具列表
  const activeProps   = ref([])

  let ctx             = null
  let rafId           = null
  let startTime       = 0
  let canvasW         = 0
  let canvasH         = 0

  // ─── 加载 SVG 姿势图 ───────────────────────────────────────
  async function loadPoses() {
    const names = ['idle', 'sit', 'sleep', 'excited', 'sad', 'held_neck', 'pee', 'lick']
    const loaded = {}
    await Promise.all(
      names.map(name =>
        new Promise(resolve => {
          const img = new Image()
          img.crossOrigin = 'anonymous'
          img.onload  = () => { loaded[name] = img; resolve() }
          img.onerror = () => { console.warn(`[PoseAnimator] 加载失败: ${name}.svg`); resolve() }
          img.src = `${spritePath}/${name}.svg`
        })
      )
    )
    poseImages.value = loaded
    isReady.value = true
  }

  // ─── 初始化 ────────────────────────────────────────────────
  function init(canvas) {
    canvasRef.value = canvas
    ctx = canvas.getContext('2d')

    // clientWidth 在首次 mount 时 可能为 0（CSS 尚未布局），用 getBoundingClientRect 更可靠
    const rect = canvas.getBoundingClientRect()
    const dpr  = window.devicePixelRatio || 1
    const cssW = rect.width  || canvas.clientWidth  || 200
    const cssH = rect.height || canvas.clientHeight || 260

    canvas.width  = Math.round(cssW * dpr)
    canvas.height = Math.round(cssH * dpr)
    ctx.scale(dpr, dpr)
    canvasW = cssW
    canvasH = cssH

    startTime = performance.now()
    rafId = requestAnimationFrame(renderLoop)
  }

  // 窗口 resize 时重置画布尺寸
  function resize(canvas) {
    if (!canvas || !ctx) return
    const rect = canvas.getBoundingClientRect()
    const dpr  = window.devicePixelRatio || 1
    const cssW = rect.width  || 200
    const cssH = rect.height || 260
    canvas.width  = Math.round(cssW * dpr)
    canvas.height = Math.round(cssH * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    canvasW = cssW
    canvasH = cssH
  }

  // ─── 主渲染循环 ────────────────────────────────────────────
  function renderLoop(timestamp) {
    rafId = requestAnimationFrame(renderLoop)
    if (!ctx || !isReady.value) return

    const t = (timestamp - startTime) / 1000   // 秒
    const state = isDragging.value ? 'drag' : currentState.value

    ctx.clearRect(0, 0, canvasW, canvasH)

    // 取 SVG 图片
    const poseName = POSE_MAP[state] || 'idle'
    const img = poseImages.value[poseName]
    if (!img) return

    // 微动效参数
    const m = MICRO_ANIM[state] || MICRO_ANIM.idle

    // 计算变换值
    const bob   = Math.sin(t * m.bobSpeed)   * m.bobAmp
    const sway  = Math.sin(t * m.swaySpeed)  * m.swayAmp
    const scale = 1 + Math.sin(t * 1.8)      * m.breathAmp

    // 绘制姿势图（带微动效）
    const imgW = 200, imgH = 260
    const drawW = imgW * scale
    const drawH = imgH * scale
    const offsetX = (canvasW - drawW) / 2 + sway
    const offsetY = (canvasH - drawH) / 2 + bob

    ctx.save()
    ctx.drawImage(img, offsetX, offsetY, drawW, drawH)
    ctx.restore()

    // 绘制道具层
    const propCx = canvasW / 2
    const propCy = canvasH / 2 - 30   // 大致在头部附近
    activeProps.value.forEach(propName => {
      const drawer = PROP_DRAWERS[propName]
      if (drawer) drawer(ctx, propCx, propCy, t)
    })
  }

  // ─── 状态切换 ──────────────────────────────────────────────
  function transitionTo(state) {
    if (POSE_MAP[state] !== undefined || state in MICRO_ANIM) {
      currentState.value = state
    } else {
      currentState.value = 'idle'
    }
  }

  function play(state) {
    transitionTo(state)
  }

  function stop() {
    currentState.value = 'idle'
    activeProps.value = []
  }

  // ─── 道具控制 ──────────────────────────────────────────────
  function addProp(propName) {
    if (!activeProps.value.includes(propName)) {
      activeProps.value = [...activeProps.value, propName]
    }
  }

  function removeProp(propName) {
    activeProps.value = activeProps.value.filter(p => p !== propName)
  }

  function clearProps() {
    activeProps.value = []
  }

  // ─── 拖拽状态 ──────────────────────────────────────────────
  function setDragging(dragging) {
    isDragging.value = dragging
    if (dragging) {
      // 拖拽时显示惊恐汗滴
      addProp('sweatDrops')
    } else {
      removeProp('sweatDrops')
    }
  }

  // ─── 透明度检测（用于鼠标穿透）────────────────────────────
  function getPixelAlpha(cssX, cssY) {
    if (!ctx || !canvasRef.value) return 0
    const dpr = window.devicePixelRatio || 1
    try {
      const px = Math.floor(cssX * dpr)
      const py = Math.floor(cssY * dpr)
      const data = ctx.getImageData(px, py, 1, 1).data
      return data[3]
    } catch {
      return 255   // 出错时保守返回不透明
    }
  }

  // ─── 清理 ──────────────────────────────────────────────────
  onUnmounted(() => {
    if (rafId) cancelAnimationFrame(rafId)
  })

  return {
    isReady,
    currentState,
    isDragging,
    activeProps,
    poseImages,
    init,
    resize,
    loadPoses,
    transitionTo,
    play,
    stop,
    setDragging,
    addProp,
    removeProp,
    clearProps,
    getPixelAlpha,
    POSE_MAP,
    PROP_DRAWERS,
  }
}

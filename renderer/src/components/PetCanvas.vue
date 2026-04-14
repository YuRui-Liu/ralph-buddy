<template>
  <div ref="canvasContainer" class="pet-canvas" @mousedown="startDrag"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { usePetStore, PetState } from '../stores/pet'
import { useUiStore } from '../stores/ui'
import { usePetAnimationController } from '../composables/usePetAnimation'

// 预定义从 GLB 中提取的贴图路径
const TEXTURE_MAP = {
  baseColor: '/models/texture_pbr_20250901.png',
  normal: '/models/texture_pbr_20250901_normal.png',
  metallicRoughness: '/models/texture_pbr_20250901_metallic-texture_pbr_20250901_roughness.png',
}

const canvasContainer = ref(null)
const petStore = usePetStore()
const uiStore = useUiStore()

// Three.js 相关变量
let scene, camera, renderer
let petModel, mixer
let clock = new THREE.Clock()
let animations = {}
let tail = null  // 尾巴对象引用
let eyes = null  // 眼睛对象引用

let modelBaseY = -1

// 拖拽相关
let isDragging = false

// 鼠标穿透相关（已禁用，整个窗口均可点击）

// 动画控制器
let animationController = null

// 初始化场景
function initScene() {
  const container = canvasContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // 场景
  scene = new THREE.Scene()
  // 透明背景
  scene.background = null

  // 相机 - 调整位置和视角以适应更小的窗口
  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000)
  camera.position.set(0, 0.8, 4)
  camera.lookAt(0, 0, 0)

  // 渲染器 - 透明背景
  renderer = new THREE.WebGLRenderer({ 
    antialias: true, 
    alpha: true,
    premultipliedAlpha: false
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setClearColor(0x000000, 0)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  container.appendChild(renderer.domElement)

  // 光照
  const ambientLight = new THREE.AmbientLight(0xffffff, 1.2)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5)
  dirLight.position.set(3, 8, 5)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.width = 1024
  dirLight.shadow.mapSize.height = 1024
  scene.add(dirLight)

  // 补光（正面亮度）
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.5)
  fillLight.position.set(-3, 2, 5)
  scene.add(fillLight)

  // 阴影接收平面（透明）
  const planeGeometry = new THREE.PlaneGeometry(10, 10)
  const planeMaterial = new THREE.ShadowMaterial({ opacity: 0.1 })
  const plane = new THREE.Mesh(planeGeometry, planeMaterial)
  plane.rotation.x = -Math.PI / 2
  plane.position.y = -1
  plane.receiveShadow = true
  scene.add(plane)

  // 加载宠物模型（临时使用立方体代替）
  loadPetModel()

  // 开始渲染循环
  animate()
}

// 加载宠物模型（GLB，内置贴图材质和骨骼）
function loadPetModel() {
  const loader = new GLTFLoader()

  console.log('🔄 加载 GLB 模型: /models/rhyfu2.glb')

  loader.load(
    '/models/rhyfu2.glb',
    (gltf) => {
      console.log('✅ GLB 模型加载成功')
      petModel = gltf.scene

      // 手动加载贴图（规避 GLTFLoader blob URL 失败问题）
      const texLoader = new THREE.TextureLoader()
      const baseColorTex = texLoader.load(TEXTURE_MAP.baseColor)
      const normalTex = texLoader.load(TEXTURE_MAP.normal)
      const mrTex = texLoader.load(TEXTURE_MAP.metallicRoughness)
      baseColorTex.colorSpace = THREE.SRGBColorSpace
      baseColorTex.flipY = false
      normalTex.flipY = false
      mrTex.flipY = false

      // 开启阴影投射，应用正确的贴图，查找可动画部位
      petModel.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
          if (child.material) {
            child.material.map = baseColorTex
            child.material.normalMap = normalTex
            child.material.metalnessMap = mrTex
            child.material.roughnessMap = mrTex
            child.material.needsUpdate = true
          }
        }

        // 查找尾巴（用于程序化动画）
        if (child.name && (
          child.name.toLowerCase().includes('tail') ||
          child.name.toLowerCase().includes('wudao')
        )) {
          tail = child
          console.log(`[PetCanvas] 找到尾巴: ${child.name}`)
        }

        // 查找眼睛
        if (child.name && (
          child.name.toLowerCase().includes('eye') ||
          child.name.toLowerCase().includes('眼')
        )) {
          eyes = child
        }
      })

      // 自动缩放使模型适应视口
      const box = new THREE.Box3().setFromObject(petModel)
      const size = box.getSize(new THREE.Vector3())
      const maxDim = Math.max(size.x, size.y, size.z)
      const scale = 2 / maxDim
      petModel.scale.set(scale, scale, scale)

      // 居中并落在地面
      const box2 = new THREE.Box3().setFromObject(petModel)
      const center = box2.getCenter(new THREE.Vector3())
      modelBaseY = -box2.min.y - 1
      petModel.position.set(-center.x, modelBaseY, -center.z)

      scene.add(petModel)
      console.log(`📐 GLB 尺寸: ${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)}, 缩放: ${scale.toFixed(3)}`)

      // 加载动画
      if (gltf.animations.length > 0) {
        mixer = new THREE.AnimationMixer(petModel)
        gltf.animations.forEach((clip, index) => {
          animations[clip.name || `anim_${index}`] = mixer.clipAction(clip)
        })
        console.log(`🎬 加载了 ${gltf.animations.length} 个动画`)
      }

      // 初始化动画控制器
      initAnimationController()
    },
    (progress) => {
      const mb = (progress.loaded / 1024 / 1024).toFixed(1)
      const pct = progress.total > 0 ? (progress.loaded / progress.total * 100).toFixed(0) + '%' : mb + 'MB'
      console.log(`GLB 加载进度: ${pct}`)
    },
    (error) => {
      console.error('❌ GLB 加载失败:', error.message)
      createDefaultPet()
    }
  )
}

// 创建默认宠物（加载失败时使用）
function createDefaultPet() {
  console.log('创建默认宠物...')

  // 身体
  const bodyGeo = new THREE.BoxGeometry(1, 0.8, 1.2)
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0xD2691E })
  const body = new THREE.Mesh(bodyGeo, bodyMat)
  body.position.y = 0

  // 头
  const headGeo = new THREE.BoxGeometry(0.7, 0.7, 0.7)
  const head = new THREE.Mesh(headGeo, bodyMat)
  head.position.set(0, 0.8, 0.5)

  // 耳朵
  const earGeo = new THREE.BoxGeometry(0.2, 0.3, 0.1)
  const leftEar = new THREE.Mesh(earGeo, bodyMat)
  leftEar.position.set(-0.25, 1.2, 0.5)
  const rightEar = new THREE.Mesh(earGeo, bodyMat)
  rightEar.position.set(0.25, 1.2, 0.5)

  // 眼睛
  const eyeGeo = new THREE.SphereGeometry(0.08, 16, 16)
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x000000 })
  const leftEye = new THREE.Mesh(eyeGeo, eyeMat)
  leftEye.position.set(-0.2, 0.85, 0.85)
  const rightEye = new THREE.Mesh(eyeGeo, eyeMat)
  rightEye.position.set(0.2, 0.85, 0.85)

  // 鼻子
  const noseGeo = new THREE.SphereGeometry(0.06, 16, 16)
  const nose = new THREE.Mesh(noseGeo, eyeMat)
  nose.position.set(0, 0.75, 0.9)

  // 尾巴
  const tailGeo = new THREE.CylinderGeometry(0.05, 0.1, 0.4)
  const tailMesh = new THREE.Mesh(tailGeo, bodyMat)
  tailMesh.position.set(0, 0.3, -0.7)
  tailMesh.rotation.x = 0.5
  tail = tailMesh

  // 眼睛组
  eyes = new THREE.Group()
  eyes.add(leftEye, rightEye)

  // 组合
  petModel = new THREE.Group()
  petModel.add(body, head, leftEar, rightEar, nose, tailMesh)
  petModel.scale.set(0.5, 0.5, 0.5)
  petModel.position.y = -1

  scene.add(petModel)
  console.log('✅ 默认宠物创建完成')

  // 初始化动画控制器
  initAnimationController()
}

// ========== 动画控制器初始化 ==========

function initAnimationController() {
  // 创建 threeObj 对象
  const threeObj = {
    model: petModel,
    mixer,
    animations,
    tail,
    eyes,
    baseY: modelBaseY
  }

  // 初始化统一动画控制器
  animationController = usePetAnimationController()
  animationController.init(threeObj)

  console.log('[PetCanvas] 动画系统初始化完成')
}

// 动画状态机（兼容旧接口，同时使用新动画控制器）
function transitionTo(state, duration = 0.3) {
  if (!petModel) return

  petStore.setState(state)

  // 使用新的动画控制器
  if (animationController) {
    animationController.transitionTo(state, duration)
  }
}

// 渲染循环
function animate() {
  requestAnimationFrame(animate)

  const delta = clock.getDelta()
  const time = clock.getElapsedTime()

  // 更新骨骼动画混合器
  if (mixer) {
    mixer.update(delta)
  }

  // 更新程序化/骨骼动画控制器
  if (animationController) {
    animationController.update(time, petStore.currentState)
  }

  renderer.render(scene, camera)
}



// 拖拽处理（主进程轮询模式，整个拖拽只需 2 次 IPC）
function startDrag(e) {
  if (uiStore.focusMode) return

  isDragging = true

  window.electronAPI.startDrag()

  document.addEventListener('mouseup', stopDrag)
}

function stopDrag() {
  isDragging = false
  window.electronAPI.stopDrag()
  document.removeEventListener('mouseup', stopDrag)
}

// 窗口大小调整
function onResize() {
  if (!camera || !renderer) return
  
  const container = canvasContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

onMounted(() => {
  initScene()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (renderer) {
    renderer.dispose()
  }
})

// 监听睡眠状态变化
watch(() => petStore.isSleepy, (isSleepy) => {
  if (isSleepy) {
    console.log('[PetCanvas] 宠物进入睡眠')
    transitionTo(PetState.SLEEP)
  } else if (petStore.currentState === PetState.SLEEP) {
    console.log('[PetCanvas] 宠物醒来')
    if (animationController) {
      animationController.wakeUp()
    }
  }
})

// 暴露方法给父组件
defineExpose({
  transitionTo,
  play: (action) => animationController ? animationController.play(action) : null,
  stop: () => animationController?.stop(),
  wakeUp: () => animationController ? animationController.wakeUp() : Promise.resolve(),
  getAnimationMode: () => animationController?.currentMode,
  setAnimationMode: (mode) => animationController?.setMode(mode)
})
</script>

<style scoped>
.pet-canvas {
  width: 100%;
  height: 100%;
  cursor: grab;
  background: transparent;
}

.pet-canvas:active {
  cursor: grabbing;
}
</style>

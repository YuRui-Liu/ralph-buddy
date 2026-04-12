<template>
  <div ref="canvasContainer" class="pet-canvas" @mousedown="startDrag"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader'
import { usePetStore, PetState } from '../stores/pet'
import { useUiStore } from '../stores/ui'

const canvasContainer = ref(null)
const petStore = usePetStore()
const uiStore = useUiStore()

// Three.js 相关变量
let scene, camera, renderer
let petModel, mixer
let clock = new THREE.Clock()
let animations = {}
let currentAction = null

// 拖拽相关
let isDragging = false
let dragStart = { x: 0, y: 0 }

// 初始化场景
function initScene() {
  const container = canvasContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // 场景
  scene = new THREE.Scene()
  // 透明背景
  scene.background = null

  // 相机
  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000)
  camera.position.set(0, 1, 5)
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
  container.appendChild(renderer.domElement)

  // 光照
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight.position.set(5, 10, 7)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.width = 1024
  dirLight.shadow.mapSize.height = 1024
  scene.add(dirLight)

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

// 加载宠物模型（FBX，内置贴图材质和骨骼）
function loadPetModel() {
  const loader = new FBXLoader()

  console.log('🔄 加载 FBX 模型: /models/rhyfu2.fbx')

  loader.load(
    '/models/rhyfu2.fbx',
    (object) => {
      console.log('✅ FBX 模型加载成功')
      petModel = object

      // 开启阴影投射
      petModel.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })

      // 自动缩放使模型适应视口
      const box = new THREE.Box3().setFromObject(petModel)
      const size = box.getSize(new THREE.Vector3())
      const maxDim = Math.max(size.x, size.y, size.z)
      const scale = 2 / maxDim
      petModel.scale.set(scale, scale, scale)

      // 居中并落在地面
      const center = box.getCenter(new THREE.Vector3())
      petModel.position.set(-center.x * scale, -box.min.y * scale - 1, -center.z * scale)

      scene.add(petModel)
      console.log(`📐 FBX 尺寸: ${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)}, 缩放: ${scale.toFixed(3)}`)

      // 加载动画
      if (object.animations.length > 0) {
        mixer = new THREE.AnimationMixer(petModel)
        object.animations.forEach((clip, index) => {
          animations[clip.name || `anim_${index}`] = mixer.clipAction(clip)
        })
        console.log(`🎬 加载了 ${object.animations.length} 个动画`)
      }
    },
    (progress) => {
      const mb = (progress.loaded / 1024 / 1024).toFixed(1)
      const pct = progress.total > 0 ? (progress.loaded / progress.total * 100).toFixed(0) + '%' : mb + 'MB'
      console.log(`FBX 加载进度: ${pct}`)
    },
    (error) => {
      console.error('❌ FBX 加载失败:', error.message)
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
  const tail = new THREE.Mesh(tailGeo, bodyMat)
  tail.position.set(0, 0.3, -0.7)
  tail.rotation.x = 0.5
  
  // 组合
  petModel = new THREE.Group()
  petModel.add(body, head, leftEar, rightEar, leftEye, rightEye, nose, tail)
  petModel.scale.set(0.5, 0.5, 0.5)
  petModel.position.y = -1
  
  scene.add(petModel)
  console.log('✅ 默认宠物创建完成')
}

// 动画状态机
function transitionTo(state, duration = 0.3) {
  if (!petModel) return

  // 根据状态执行不同的动画
  switch (state) {
    case PetState.IDLE:
      // 待机动画 - 轻微呼吸起伏
      petStore.setState(PetState.IDLE)
      break
    case PetState.WALK:
      // 行走动画
      petStore.setState(PetState.WALK)
      break
    case PetState.SLEEP:
      // 睡觉 - 趴下
      petModel.rotation.x = -Math.PI / 2
      petModel.position.y = -0.5
      petStore.setState(PetState.SLEEP)
      break
    case PetState.LICK:
      // 舔屏 - 前倾
      petModel.rotation.x = 0.3
      petStore.setState(PetState.LICK)
      setTimeout(() => transitionTo(PetState.IDLE), 2000)
      break
    case PetState.CUDDLE:
      // 撒娇 - 左右摇摆
      petStore.setState(PetState.CUDDLE)
      setTimeout(() => transitionTo(PetState.IDLE), 3000)
      break
    case PetState.CUTE:
      // 卖萌 - 歪头
      petModel.rotation.z = 0.3
      petStore.setState(PetState.CUTE)
      setTimeout(() => {
        petModel.rotation.z = 0
        transitionTo(PetState.IDLE)
      }, 2000)
      break
    case PetState.BARK:
      // 汪汪叫 - 上下跳动
      petStore.setState(PetState.BARK)
      setTimeout(() => transitionTo(PetState.IDLE), 1000)
      break
  }
}

// 渲染循环
function animate() {
  requestAnimationFrame(animate)

  const delta = clock.getDelta()

  // 更新动画混合器
  if (mixer) {
    mixer.update(delta)
  }

  // 待机动画 - 呼吸效果
  if (petStore.currentState === PetState.IDLE && petModel) {
    const time = clock.getElapsedTime()
    petModel.position.y = Math.sin(time * 2) * 0.05
    petModel.scale.y = 1 + Math.sin(time * 2) * 0.02
    petModel.scale.x = 1 - Math.sin(time * 2) * 0.01
    petModel.scale.z = 1 - Math.sin(time * 2) * 0.01
  }

  // 行走动画
  if (petStore.currentState === PetState.WALK && petModel) {
    const time = clock.getElapsedTime()
    petModel.position.y = Math.abs(Math.sin(time * 8)) * 0.1
    petModel.rotation.z = Math.sin(time * 8) * 0.05
  }

  renderer.render(scene, camera)
}

// 拖拽处理
function startDrag(e) {
  if (uiStore.focusMode) return
  
  isDragging = true
  dragStart = { x: e.screenX, y: e.screenY }
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  if (!isDragging) return

  const dpr = window.devicePixelRatio || 1
  const deltaX = Math.round((e.screenX - dragStart.x) * dpr)
  const deltaY = Math.round((e.screenY - dragStart.y) * dpr)

  if (window.electronAPI) {
    window.electronAPI.moveWindow({ x: deltaX, y: deltaY })
  }

  dragStart = { x: e.screenX, y: e.screenY }
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
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
  
  // 监听宠物状态变化
  transitionTo(PetState.IDLE)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (renderer) {
    renderer.dispose()
  }
})

// 暴露方法给父组件
defineExpose({
  transitionTo
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

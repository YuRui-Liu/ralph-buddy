<template>
  <div class="settings-overlay" @click.self="close">
    <div class="settings-panel">
      <!-- 头部 -->
      <div class="panel-header">
        <h2>⚙️ 设置</h2>
        <button class="close-btn" @click="close">✕</button>
      </div>

      <!-- 内容区 -->
      <div class="panel-content">
        <!-- 动画模式设置 -->
        <section class="settings-section">
          <h3>🎭 动画模式</h3>
          <div class="mode-selector">
            <button
              v-for="mode in animationModes"
              :key="mode.value"
              :class="['mode-btn', { active: settings.animationMode === mode.value }]"
              @click="setAnimationMode(mode.value)"
            >
              <span class="mode-icon">{{ mode.icon }}</span>
              <span class="mode-name">{{ mode.name }}</span>
              <span class="mode-desc">{{ mode.desc }}</span>
            </button>
          </div>
        </section>

        <!-- 动作强度 -->
        <section class="settings-section">
          <h3>💪 动作强度</h3>
          <div class="slider-control">
            <input
              type="range"
              v-model.number="intensityValue"
              min="0.5"
              max="1.5"
              step="0.1"
              @change="updateIntensity"
            />
            <span class="slider-value">{{ intensityValue.toFixed(1) }}x</span>
          </div>
          <p class="hint">调整动作幅度大小</p>
        </section>

        <!-- 皮肤选择 -->
        <section class="settings-section">
          <h3>🎨 皮肤</h3>
          <div class="skin-selector">
            <button
              v-for="skin in skins"
              :key="skin.id"
              :class="['skin-btn', { active: settings.currentSkin === skin.id }]"
              @click="setSkin(skin.id)"
            >
              <span class="skin-icon">{{ skin.icon }}</span>
              <span class="skin-name">{{ skin.name }}</span>
            </button>
          </div>
        </section>

        <!-- 主题设置 -->
        <section class="settings-section">
          <h3>🌈 主题</h3>
          <div class="theme-selector">
            <button
              v-for="theme in themes"
              :key="theme.value"
              :class="['theme-btn', { active: settings.themeMode === theme.value }]"
              @click="setTheme(theme.value)"
            >
              {{ theme.icon }}
            </button>
          </div>
        </section>

        <!-- 声音设置 -->
        <section class="settings-section">
          <h3>🔊 声音</h3>
          <div class="setting-row">
            <span>启用语音合成</span>
            <label class="toggle">
              <input type="checkbox" v-model="settings.ttsEnabled" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="slider-control" v-if="settings.ttsEnabled">
            <span>音量</span>
            <input
              type="range"
              v-model.number="settings.ttsVolume"
              min="0"
              max="1"
              step="0.1"
            />
            <span class="slider-value">{{ Math.round(settings.ttsVolume * 100) }}%</span>
          </div>
        </section>

        <!-- 窗口设置 -->
        <section class="settings-section">
          <h3>🪟 窗口</h3>
          <div class="setting-row">
            <span>始终置顶</span>
            <label class="toggle">
              <input type="checkbox" v-model="settings.alwaysOnTop" @change="toggleAlwaysOnTop" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="slider-control">
            <span>透明度</span>
            <input
              type="range"
              v-model.number="settings.windowOpacity"
              min="0.3"
              max="1"
              step="0.1"
              @change="updateOpacity"
            />
            <span class="slider-value">{{ Math.round(settings.windowOpacity * 100) }}%</span>
          </div>
        </section>

        <!-- 天性模式 -->
        <section class="settings-section">
          <h3>🎲 天性模式</h3>
          <div class="setting-row">
            <span>启用天性行为</span>
            <label class="toggle">
              <input type="checkbox" v-model="settings.natureModeEnabled" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <p class="hint">会主动尝试和主人对话，会做动作，会调皮</p>
        </section>

        <!-- 专注模式 -->
        <section class="settings-section">
          <h3>🎯 专注模式</h3>
          <div class="setting-row">
            <span>启用专注模式</span>
            <label class="toggle">
              <input type="checkbox" :checked="uiStore.focusMode" @change="toggleFocus" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <p class="hint">主人工作时不发起语音，信息显示在桌面聊天框内</p>
        </section>

        <!-- 情绪观察 -->
        <section class="settings-section">
          <h3>👁️ 情绪观察</h3>
          <div class="setting-row">
            <div>
              <span>让来福观察你</span>
              <p class="hint" style="margin: 2px 0 0 0;">通过摄像头感知你的心情</p>
            </div>
            <label class="toggle">
              <input type="checkbox" v-model="emotionToggle" @change="onEmotionToggle" />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <template v-if="settings.emotionEnabled && petStore.emotionObserver.enabled">
            <div class="slider-control" style="margin-top: 12px;">
              <span>偷看频率</span>
              <input
                type="range"
                v-model.number="settings.emotionInterval"
                min="5"
                max="30"
                step="5"
                @change="settings.saveSettings()"
              />
              <span class="slider-value">{{ settings.emotionInterval }}分钟</span>
            </div>

            <button class="manual-detect-btn" @click="manualDetect">
              让来福看看你
            </button>

            <p class="hint" v-if="petStore.emotionObserver.lastEmotion" style="margin-top: 8px;">
              上次观察: {{ emotionLabel[petStore.emotionObserver.lastEmotion] || petStore.emotionObserver.lastEmotion }}
              ({{ Math.round(petStore.emotionObserver.lastConfidence * 100) }}%)
            </p>
          </template>
        </section>

        <!-- 引导弹窗 -->
        <div v-if="showOnboarding" class="onboarding-overlay" @click.self="cancelOnboarding">
          <div class="onboarding-dialog">
            <p class="onboarding-text">汪？主人，来福想看看你的样子！可以让来福偷偷看你吗？</p>
            <p class="hint" style="text-align: center;">深度分析时图像会发送给 AI 服务</p>
            <div class="onboarding-buttons">
              <button class="btn-accept" @click="acceptOnboarding">好呀！</button>
              <button class="btn-reject" @click="cancelOnboarding">不要</button>
            </div>
          </div>
        </div>

        <!-- 关于 -->
        <section class="settings-section about">
          <p>DogBuddy v1.0.0</p>
          <p class="hint">你的桌面 AI 陪伴宠物 🐕</p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useSettingsStore, AnimationMode } from '@/stores/settings'
import { useUiStore } from '@/stores/ui'
import { usePetStore } from '@/stores/pet'

const settings = useSettingsStore()
const uiStore = useUiStore()
const petStore = usePetStore()

const intensityValue = ref(settings.animationIntensity)

const emotionToggle = ref(settings.emotionEnabled && petStore.emotionObserver.enabled)
const showOnboarding = ref(false)

const emotionLabel = {
  happy: '开心', sad: '难过', angry: '生气',
  surprise: '惊讶', neutral: '平静', fear: '紧张', disgust: '厌恶'
}

function onEmotionToggle () {
  if (emotionToggle.value) {
    if (!petStore.emotionObserver.enabled) {
      showOnboarding.value = true
    } else {
      settings.emotionEnabled = true
      settings.saveSettings()
    }
  } else {
    settings.emotionEnabled = false
    petStore.emotionObserver.enabled = false
    settings.saveSettings()
  }
}

async function acceptOnboarding () {
  showOnboarding.value = false
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    stream.getTracks().forEach(t => t.stop())
    petStore.emotionObserver.enabled = true
    settings.emotionEnabled = true
    settings.saveSettings()
  } catch {
    emotionToggle.value = false
    petStore.emotionObserver.enabled = false
  }
}

function cancelOnboarding () {
  showOnboarding.value = false
  emotionToggle.value = false
}

async function manualDetect () {
  const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' }
    })
    const track = stream.getVideoTracks()[0]
    const imageCapture = new ImageCapture(track)
    const bitmap = await imageCapture.grabFrame()
    stream.getTracks().forEach(t => t.stop())

    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    canvas.getContext('2d').drawImage(bitmap, 0, 0)

    const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.8))
    const formData = new FormData()
    formData.append('image', blob, 'frame.jpg')
    formData.append('deep', 'true')

    const res = await fetch(`http://127.0.0.1:${pythonPort}/api/emotion`, {
      method: 'POST', body: formData
    })
    if (res.ok) {
      const result = await res.json()
      if (result.has_face && result.local) {
        petStore.emotionObserver.lastEmotion = result.local.emotion
        petStore.emotionObserver.lastConfidence = result.local.confidence
        petStore.emotionObserver.lastDetectTime = Date.now()
        if (result.deep) petStore.emotionObserver.lastDeepDesc = result.deep.description || ''
      }
    }
  } catch (err) {
    console.error('[Settings] 手动检测失败:', err)
  }
}

// 动画模式选项
const animationModes = [
  {
    value: AnimationMode.BONE,
    name: '骨骼动画',
    icon: '🎮',
    desc: '3D模型 + 动画文件'
  },
  {
    value: AnimationMode.RHYFU,
    name: '来福2D',
    icon: '🐕',
    desc: 'SVG姿势图 + 自组织行为'
  }
]

// 皮肤选项
const skins = [
  { id: 'dog', name: '田园犬', icon: '🐕' },
  { id: 'corgi', name: '柯基', icon: '🐶' },
  { id: 'shiba', name: '柴犬', icon: '🦊' }
]

// 主题选项
const themes = [
  { value: 'light', icon: '☀️' },
  { value: 'dark', icon: '🌙' },
  { value: 'system', icon: '💻' }
]

function setAnimationMode(mode) {
  settings.setAnimationMode(mode)
  settings.saveSettings()
}

function updateIntensity() {
  settings.setAnimationIntensity(intensityValue.value)
  settings.saveSettings()
}

function setSkin(skinId) {
  settings.currentSkin = skinId
  settings.saveSettings()
}

function setTheme(theme) {
  settings.setThemeMode(theme)
  settings.saveSettings()
}

function updateOpacity() {
  settings.saveSettings()
}

function toggleAlwaysOnTop() {
  settings.saveSettings()
}

function toggleFocus() {
  uiStore.toggleFocusMode()
  // 专注模式和天性模式互斥
  if (uiStore.focusMode) {
    settings.natureModeEnabled = false
    uiStore.setNatureMode(false)
  }
  if (window.electronAPI?.syncModeState) {
    window.electronAPI.syncModeState({
      natureMode: uiStore.natureMode,
      focusMode:  uiStore.focusMode,
    })
  }
}

function close() {
  uiStore.closeSettings()
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.settings-panel {
  width: 380px;
  max-height: 85vh;
  background: var(--bg-panel, #ffffff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.panel-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.panel-content {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
}

.settings-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.2);
}

.settings-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.settings-section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

/* 动画模式选择器 */
.mode-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-secondary, #f5f5f5);
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.mode-btn:hover {
  background: var(--bg-hover, #e8e8e8);
}

.mode-btn.active {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

.mode-icon {
  font-size: 24px;
}

.mode-name {
  font-weight: 600;
  color: var(--text-primary, #333);
  flex: 1;
}

.mode-desc {
  font-size: 11px;
  color: var(--text-secondary, #888);
}

/* 滑动条控制 */
.slider-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-control input[type="range"] {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  background: var(--bg-secondary, #e0e0e0);
  border-radius: 2px;
  outline: none;
}

.slider-control input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #667eea;
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  min-width: 40px;
  text-align: right;
  font-weight: 600;
  color: #667eea;
}

/* 皮肤选择 */
.skin-selector {
  display: flex;
  gap: 8px;
}

.skin-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: var(--bg-secondary, #f5f5f5);
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.skin-btn:hover {
  background: var(--bg-hover, #e8e8e8);
}

.skin-btn.active {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

.skin-icon {
  font-size: 24px;
}

.skin-name {
  font-size: 12px;
  color: var(--text-primary, #333);
}

/* 主题选择 */
.theme-selector {
  display: flex;
  gap: 8px;
}

.theme-btn {
  flex: 1;
  padding: 10px;
  background: var(--bg-secondary, #f5f5f5);
  border: 2px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.2s;
}

.theme-btn:hover {
  background: var(--bg-hover, #e8e8e8);
}

.theme-btn.active {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

/* 设置行 */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.setting-row span {
  color: var(--text-primary, #333);
}

/* 开关 */
.toggle {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 26px;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: 0.3s;
  border-radius: 26px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

.toggle input:checked + .toggle-slider {
  background-color: #667eea;
}

.toggle input:checked + .toggle-slider:before {
  transform: translateX(22px);
}

/* 提示文字 */
.hint {
  font-size: 12px;
  color: var(--text-secondary, #888);
  margin: 8px 0 0 0;
}

/* 关于 */
.about {
  text-align: center;
  color: var(--text-secondary, #888);
}

.about p {
  margin: 4px 0;
}

/* 暗色主题支持 */
[data-theme="dark"] .settings-panel {
  --bg-panel: #2a2a2a;
  --bg-secondary: #3a3a3a;
  --bg-hover: #444;
  --text-primary: #fff;
  --text-secondary: #aaa;
}

/* 手动检测按钮 */
.manual-detect-btn {
  width: 100%;
  margin-top: 12px;
  padding: 10px;
  background: rgba(102, 126, 234, 0.1);
  border: 1px dashed #667eea;
  border-radius: 8px;
  color: #667eea;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.manual-detect-btn:hover {
  background: rgba(102, 126, 234, 0.2);
}

/* 引导弹窗 */
.onboarding-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.onboarding-dialog {
  background: var(--bg-panel, #fff);
  border-radius: 16px;
  padding: 24px;
  max-width: 300px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.onboarding-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary, #333);
  margin: 0 0 12px 0;
}

.onboarding-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}

.btn-accept {
  padding: 8px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-accept:hover { background: #5a6fd6; }

.btn-reject {
  padding: 8px 24px;
  background: var(--bg-secondary, #eee);
  color: var(--text-secondary, #666);
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
}
</style>

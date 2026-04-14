const { contextBridge, ipcRenderer } = require('electron')

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Python 服务
  getPythonPort: () => ipcRenderer.invoke('get-python-port'),

  // VAD/WASM 路径（file:// 协议，让 ORT 跳过 streaming compile）
  getVadBasePath: () => ipcRenderer.invoke('get-vad-base-path'),
  
  // 窗口拖拽（主进程轮询模式，只需 2 次 IPC）
  startDrag: () => ipcRenderer.send('start-drag'),
  stopDrag: () => ipcRenderer.send('stop-drag'),
  setIgnoreMouseEvents: (ignore) => ipcRenderer.invoke('set-ignore-mouse-events', ignore),
  
  // 事件监听
  onOpenSettings: (callback) => ipcRenderer.on('open-settings', callback),
  onOpenVoiceManager: (callback) => ipcRenderer.on('open-voice-manager', callback),
  onToggleFocusMode: (callback) => ipcRenderer.on('toggle-focus-mode', callback),
  onSetFocusMode: (callback) => ipcRenderer.on('set-focus-mode', (event, enabled) => callback(enabled)),
  onToggleNatureMode: (callback) => ipcRenderer.on('toggle-nature-mode', (event, enabled) => callback(enabled)),
  onOpenMemory: (callback) => ipcRenderer.on('open-memory', callback),
  onOpenAttributes: (callback) => ipcRenderer.on('open-attributes', callback),
  onOpenDreamDiary: (callback) => ipcRenderer.on('open-dream-diary', () => callback()),
  onSetAutoVAD: (callback) => ipcRenderer.on('set-auto-vad', (event, enabled) => callback(enabled)),
  onToggleRecording: (callback) => ipcRenderer.on('toggle-recording', callback),
  onCloseSettings: (callback) => ipcRenderer.on('close-settings', callback),
  syncModeState: (state) => ipcRenderer.send('sync-mode-state', state),
  removeAllAppListeners: () => {
    ipcRenderer.removeAllListeners('open-settings')
    ipcRenderer.removeAllListeners('open-voice-manager')
    ipcRenderer.removeAllListeners('toggle-focus-mode')
    ipcRenderer.removeAllListeners('set-focus-mode')
    ipcRenderer.removeAllListeners('toggle-nature-mode')
    ipcRenderer.removeAllListeners('open-memory')
    ipcRenderer.removeAllListeners('open-attributes')
    ipcRenderer.removeAllListeners('set-auto-vad')
    ipcRenderer.removeAllListeners('toggle-recording')
    ipcRenderer.removeAllListeners('close-settings')
    ipcRenderer.removeAllListeners('trigger-behavior')
    ipcRenderer.removeAllListeners('open-dream-diary')
    ipcRenderer.removeAllListeners('open-plugin-request')
    ipcRenderer.removeAllListeners('plugin-window-closed')
  },

  // 插件系统
  openPlugin: (pluginId, manifest) => ipcRenderer.send('open-plugin', { pluginId, manifest }),
  registerPluginShortcuts: (plugins) => ipcRenderer.send('register-plugin-shortcuts', plugins),
  onOpenPluginRequest: (callback) => ipcRenderer.on('open-plugin-request', (event, pluginId) => callback(pluginId)),
  onPluginWindowClosed: (callback) => ipcRenderer.on('plugin-window-closed', (event, pluginId) => callback(pluginId)),

  // 来福特技触发（rhyfu 模式行为序列）
  onTriggerBehavior: (callback) => ipcRenderer.on('trigger-behavior', (event, id) => callback(id)),

  // 显式关闭设置
  closeSettings: () => ipcRenderer.send('close-settings'),

  // 窗口控制
  hideWindow: () => ipcRenderer.send('hide-window'),

  // 移除监听器
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel)
})

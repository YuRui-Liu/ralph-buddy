const { contextBridge, ipcRenderer } = require('electron')

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Python 服务
  getPythonPort: () => ipcRenderer.invoke('get-python-port'),

  // VAD/WASM 路径（file:// 协议，让 ORT 跳过 streaming compile）
  getVadBasePath: () => ipcRenderer.invoke('get-vad-base-path'),
  
  // 窗口控制
  moveWindow: (delta) => ipcRenderer.send('move-window', delta),
  setIgnoreMouseEvents: (ignore) => ipcRenderer.invoke('set-ignore-mouse-events', ignore),
  
  // 事件监听
  onOpenSettings: (callback) => ipcRenderer.on('open-settings', callback),
  onOpenVoiceManager: (callback) => ipcRenderer.on('open-voice-manager', callback),
  onToggleFocusMode: (callback) => ipcRenderer.on('toggle-focus-mode', callback),
  onToggleNatureMode: (callback) => ipcRenderer.on('toggle-nature-mode', (event, enabled) => callback(enabled)),
  onOpenMemory: (callback) => ipcRenderer.on('open-memory', callback),
  onCloseSettings: (callback) => ipcRenderer.on('close-settings', callback),
  removeAllAppListeners: () => {
    ipcRenderer.removeAllListeners('open-settings')
    ipcRenderer.removeAllListeners('open-voice-manager')
    ipcRenderer.removeAllListeners('toggle-focus-mode')
    ipcRenderer.removeAllListeners('toggle-nature-mode')
    ipcRenderer.removeAllListeners('open-memory')
    ipcRenderer.removeAllListeners('close-settings')
  },

  // 显式关闭设置
  closeSettings: () => ipcRenderer.send('close-settings'),

  // 窗口控制
  hideWindow: () => ipcRenderer.send('hide-window'),

  // 移除监听器
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel)
})

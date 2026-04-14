const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('pluginAPI', {
  getPluginId: () => ipcRenderer.invoke('get-plugin-id'),
  getPythonPort: () => ipcRenderer.invoke('get-python-port'),
  closeWindow: () => ipcRenderer.send('close-plugin-window'),
})

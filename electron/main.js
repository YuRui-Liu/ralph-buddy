const { app, BrowserWindow, ipcMain, screen, Tray, Menu, session, globalShortcut } = require('electron')
const path = require('path')
const { pathToFileURL } = require('url')
const { spawn } = require('child_process')

// 修复 Intel 智音技术 (SST) 麦克风在 Chromium 音频沙箱下 muted=true 的问题
// 必须在 app.whenReady() 之前调用
app.commandLine.appendSwitch('disable-features', 'AudioServiceSandbox')
app.commandLine.appendSwitch('use-fake-ui-for-media-stream')  // 跳过权限弹窗，直接授权

// 保持窗口和托盘的全局引用
let mainWindow = null
let tray = null
let pythonProcess = null

// 插件窗口管理
const pluginWindows = new Map()

function openPluginWindow(pluginId, manifest) {
  if (pluginWindows.has(pluginId)) {
    const existing = pluginWindows.get(pluginId)
    if (!existing.isDestroyed()) {
      existing.focus()
      return
    }
    pluginWindows.delete(pluginId)
  }

  const winCfg = manifest.window || { width: 480, height: 600 }
  const pluginWin = new BrowserWindow({
    width: winCfg.width,
    height: winCfg.height,
    title: manifest.name,
    frame: true,
    resizable: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'plugin-preload.js'),
      webSecurity: false,
    }
  })

  const isDev = process.argv.includes('--dev')
  if (isDev) {
    pluginWin.loadURL(`http://localhost:5173/plugin.html?id=${pluginId}`)
  } else {
    pluginWin.loadFile(path.join(__dirname, '../dist/plugin.html'), {
      query: { id: pluginId }
    })
  }

  pluginWin.on('close', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('plugin-window-closed', pluginId)
    }
  })

  pluginWin.on('closed', () => {
    pluginWindows.delete(pluginId)
  })

  pluginWindows.set(pluginId, pluginWin)
}

ipcMain.handle('get-plugin-id', (event) => {
  const url = event.sender.getURL()
  const match = url.match(/[?&]id=([^&]+)/)
  return match ? match[1] : null
})

ipcMain.on('close-plugin-window', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (win) win.close()
})

ipcMain.on('open-plugin', (event, { pluginId, manifest }) => {
  openPluginWindow(pluginId, manifest)
})

// 创建主窗口
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  
  // 窗口尺寸 - 只包裹宠物本身，不要多余空白
  const windowWidth = 280
  const windowHeight = 320
  
  // 初始位置：屏幕右下角
  const x = width - windowWidth - 20
  const y = height - windowHeight - 20

  mainWindow = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    x: x,
    y: y,
    frame: false,              // 无边框
    transparent: true,         // 透明背景
    alwaysOnTop: true,         // 始终置顶
    skipTaskbar: true,         // 不显示在任务栏
    resizable: false,          // 不可调整大小
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: false       // 允许加载本地资源
    }
  })

  // 加载应用
  const isDev = process.argv.includes('--dev')
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
  
  // 兜底：确保 .wasm 文件的 MIME 类型正确（dev 和 prod 均生效）
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    if (details.url.includes('.wasm')) {
      const headers = { ...details.responseHeaders }
      headers['content-type'] = ['application/wasm']
      headers['cross-origin-resource-policy'] = ['cross-origin']
      callback({ responseHeaders: headers })
    } else {
      callback({ responseHeaders: details.responseHeaders })
    }
  })

  // 始终打开 DevTools 以便调试
  mainWindow.webContents.openDevTools({ mode: 'detach' })

  // 当前模式状态（由渲染进程同步过来）
  let currentNatureMode = true
  let currentFocusMode  = false
  let currentAutoVAD    = true

  ipcMain.on('sync-mode-state', (event, { natureMode, focusMode, autoVAD }) => {
    currentNatureMode = natureMode
    currentFocusMode  = focusMode
    if (autoVAD !== undefined) currentAutoVAD = autoVAD
  })

  // 右键菜单（直接右键来福）
  mainWindow.webContents.on('context-menu', () => {
    Menu.buildFromTemplate([
      {
        label: '来福特技',
        submenu: [
          { label: '戴眼镜学究',   click: () => mainWindow.webContents.send('trigger-behavior', 'scholar') },
          { label: '拿放大镜侦探', click: () => mainWindow.webContents.send('trigger-behavior', 'investigate') },
          { label: '谄媚讨好',     click: () => mainWindow.webContents.send('trigger-behavior', 'flatter') },
          { label: '舔屏',         click: () => mainWindow.webContents.send('trigger-behavior', 'lickScreen') },
          { label: '撒尿',         click: () => mainWindow.webContents.send('trigger-behavior', 'pee') },
          { label: '难过',         click: () => mainWindow.webContents.send('trigger-behavior', 'sad') },
          { label: '睡前仪式',     click: () => mainWindow.webContents.send('trigger-behavior', 'bedtime') },
        ]
      },
      { type: 'separator' },
      { label: '宠物属性', click: () => mainWindow.webContents.send('open-attributes') },
      { type: 'separator' },
      {
        label: '天性模式',
        type: 'checkbox',
        checked: currentNatureMode,
        click: (menuItem) => {
          // 天性模式和专注模式互斥
          if (menuItem.checked) {
            currentNatureMode = true
            currentFocusMode  = false
            mainWindow.webContents.send('toggle-nature-mode', true)
            mainWindow.webContents.send('set-focus-mode', false)
          } else {
            currentNatureMode = false
            mainWindow.webContents.send('toggle-nature-mode', false)
          }
        }
      },
      {
        label: '专注模式',
        type: 'checkbox',
        checked: currentFocusMode,
        click: (menuItem) => {
          if (menuItem.checked) {
            currentFocusMode  = true
            currentNatureMode = false
            mainWindow.webContents.send('set-focus-mode', true)
            mainWindow.webContents.send('toggle-nature-mode', false)
          } else {
            currentFocusMode = false
            mainWindow.webContents.send('set-focus-mode', false)
          }
        }
      },
      { type: 'separator' },
      {
        label: '语音自动检测',
        type: 'checkbox',
        checked: currentAutoVAD,
        click: (menuItem) => {
          currentAutoVAD = menuItem.checked
          mainWindow.webContents.send('set-auto-vad', menuItem.checked)
        }
      },
      { type: 'separator' },
      {
        label: '工具箱',
        submenu: [
          { label: '💕 撩妹助手', click: () => mainWindow.webContents.send('open-plugin-request', 'flirt') },
          { label: '🔍 搜索助手', click: () => mainWindow.webContents.send('open-plugin-request', 'search') },
        ]
      },
      { label: '梦境日记', click: () => mainWindow.webContents.send('open-dream-diary') },
      { label: '记忆管理', click: openMemoryPanel },
      { type: 'separator' },
      { label: '显示/隐藏', click: toggleWindow },
      { label: '退出', click: quitApp }
    ]).popup({ window: mainWindow })
  })

  // 窗口关闭时清理
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// 创建系统托盘
function createTray() {
  // 使用简单的图标路径（需要准备图标文件）
  const iconPath = path.join(__dirname, '../dist/favicon.ico')
  
  tray = new Tray(iconPath)
  
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示/隐藏', click: toggleWindow },
    { label: '设置', click: openSettings },
    { label: '🧠 记忆管理', click: openMemoryPanel },
    { type: 'separator' },
    { label: '退出', click: quitApp }
  ])
  
  tray.setToolTip('DogBuddy - 来福')
  tray.setContextMenu(contextMenu)
  
  tray.on('click', toggleWindow)
}

// 切换窗口显示
function toggleWindow() {
  if (mainWindow) {
    if (mainWindow.isVisible()) {
      mainWindow.hide()
    } else {
      mainWindow.show()
    }
  } else {
    createWindow()
  }
}

// 打开设置
function openSettings() {
  if (mainWindow) {
    mainWindow.webContents.send('open-settings')
  }
}

// 打开记忆管理面板
function openMemoryPanel() {
  if (mainWindow) {
    mainWindow.webContents.send('open-memory')
  }
}

// 启动 Python 后端服务
function startPythonService() {
  // 检查是否在开发模式
  const isDev = process.argv.includes('--dev')
  
  if (isDev) {
    console.log('开发模式：请手动启动 Python 服务')
    console.log('运行: cd python-service && python main.py')
    return
  }
  
  // 生产模式：启动打包的 Python 服务
  const pythonServicePath = path.join(process.resourcesPath, 'python-service', 'dogbuddy-service.exe')
  
  console.log('启动 Python 服务:', pythonServicePath)
  
  pythonProcess = spawn(pythonServicePath, [], {
    detached: false,
    windowsHide: true
  })
  
  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python: ${data}`)
  })
  
  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python Error: ${data}`)
  })
  
  pythonProcess.on('close', (code) => {
    console.log(`Python 服务退出，代码: ${code}`)
  })
}

// 退出应用
function quitApp() {
  // 终止 Python 进程
  if (pythonProcess) {
    pythonProcess.kill()
  }
  
  app.quit()
}

// 拖拽状态（主进程侧轮询光标位置，整个拖拽过程零额外 IPC）
let dragOffset = null

// IPC 通信：开始拖拽（渲染进程只需调用一次）
// 直接用屏幕坐标计算偏移，避免 CSS 像素与物理像素的 DPI 缩放不一致
ipcMain.on('start-drag', () => {
  if (!mainWindow) return
  const [winX, winY] = mainWindow.getPosition()
  const cursor = screen.getCursorScreenPoint()
  dragOffset = {
    x: cursor.x - winX,
    y: cursor.y - winY,
    width: mainWindow.getBounds().width,
    height: mainWindow.getBounds().height,
  }
})

// IPC 通信：结束拖拽
ipcMain.on('stop-drag', () => {
  dragOffset = null
})

// 高频轮询：拖拽期间每帧读取光标位置并移动窗口
// 注意：Windows 透明窗口上 setPosition 会导致尺寸被 DWM 撑大，
// 必须每次移动后强制 setSize 恢复原始尺寸
function updateDrag() {
  if (dragOffset && mainWindow) {
    const cursor = screen.getCursorScreenPoint()
    mainWindow.setPosition(cursor.x - dragOffset.x, cursor.y - dragOffset.y)
    mainWindow.setSize(dragOffset.width, dragOffset.height)
  }
  setImmediate(updateDrag)
}
setImmediate(updateDrag)

// IPC 通信：获取 Python 端口
ipcMain.handle('get-python-port', () => {
  return 18765  // 默认端口
})

// IPC 通信：获取 VAD 目录的 file:// URL
// 渲染进程用此路径初始化 ORT/VAD，file:// 协议下 Chromium 正确处理 WASM
// ORT 内部 ja(b) 检测到 file:// 直接走 ArrayBuffer 路径，不触发 streaming compile 报错
ipcMain.handle('get-vad-base-path', () => {
  const isDev = process.argv.includes('--dev')
  const vadDir = isDev
    ? path.join(__dirname, '../renderer/public/vad')
    : path.join(process.resourcesPath, 'vad')
  // pathToFileURL 在 Windows/Linux/Mac 下均生成正确的 file:// 路径
  return pathToFileURL(vadDir).href + '/'
})

// IPC 通信：设置鼠标穿透（已禁用穿透功能，仅保留 no-op 以防调用崩溃）
ipcMain.handle('set-ignore-mouse-events', (event, ignore) => {
  // 不做任何操作——穿透功能已移除
})

// IPC 通信：隐藏窗口
ipcMain.on('hide-window', () => {
  if (mainWindow) {
    mainWindow.hide()
  }
})

// IPC 通信：关闭设置（通知渲染进程）
ipcMain.on('close-settings', () => {
  if (mainWindow) {
    mainWindow.webContents.send('close-settings')
  }
})

// 应用就绪
app.whenReady().then(() => {
  // 显式授权麦克风 / 摄像头等媒体权限
  // Electron 默认可能拦截 getUserMedia，导致返回"活跃但无数据"的流
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ['media', 'audioCapture', 'microphone', 'camera']
    callback(allowed.includes(permission))
  })
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    const allowed = ['media', 'audioCapture', 'microphone', 'camera']
    return allowed.includes(permission)
  })

  createWindow()
  createTray()

  // Ctrl+P 全局快捷键：切换录音（开始/停止）
  globalShortcut.register('CommandOrControl+P', () => {
    if (mainWindow) {
      mainWindow.webContents.send('toggle-recording')
    }
  })

  ipcMain.on('register-plugin-shortcuts', (event, plugins) => {
    for (const p of plugins) {
      if (p.shortcut) {
        try {
          globalShortcut.register(p.shortcut, () => {
            openPluginWindow(p.id, p)
          })
        } catch (e) {
          console.log(`[plugin] shortcut ${p.shortcut} failed:`, e.message)
        }
      }
    }
  })

  // 只在生产模式启动 Python 服务
  if (!process.argv.includes('--dev')) {
    startPythonService()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 所有窗口关闭时
app.on('window-all-closed', () => {
  // macOS 上通常不退出应用
  if (process.platform !== 'darwin') {
    // 保留托盘，不退出
  }
})

// 应用退出前
app.on('before-quit', () => {
  globalShortcut.unregisterAll()
  if (pythonProcess) {
    pythonProcess.kill()
  }
})

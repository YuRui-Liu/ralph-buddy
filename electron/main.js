const { app, BrowserWindow, ipcMain, screen, Tray, Menu, session } = require('electron')
const path = require('path')
const { pathToFileURL } = require('url')
const { spawn } = require('child_process')

// 保持窗口和托盘的全局引用
let mainWindow = null
let tray = null
let pythonProcess = null

// 创建主窗口
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  
  // 窗口尺寸
  const windowWidth = 400
  const windowHeight = 400
  
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

  // 右键菜单（直接右键来福）
  mainWindow.webContents.on('context-menu', () => {
    Menu.buildFromTemplate([
      { label: '🧠 记忆管理', click: openMemoryPanel },
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

// IPC 通信：移动窗口
ipcMain.on('move-window', (event, { x, y }) => {
  if (mainWindow) {
    const [currentX, currentY] = mainWindow.getPosition()
    mainWindow.setPosition(currentX + x, currentY + y)
  }
})

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

// IPC 通信：设置鼠标穿透
ipcMain.handle('set-ignore-mouse-events', (event, ignore) => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(ignore, { forward: true })
  }
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
  createWindow()
  createTray()
  
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
  if (pythonProcess) {
    pythonProcess.kill()
  }
})

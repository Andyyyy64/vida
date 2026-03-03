import { app, BrowserWindow, Tray, Menu, shell, nativeImage } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import { createConnection } from 'net'
import { existsSync } from 'fs'
import path from 'path'

// Pass `--dev` to load the Vite dev server (http://localhost:5173) instead of Hono
const isDev = process.argv.includes('--dev')
const WEB_PORT = 3001

// When running `electron .` from web/, getAppPath() returns the web/ directory
const WEB_DIR = app.getAppPath()
const REPO_ROOT = path.join(WEB_DIR, '..')

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let daemonProcess: ChildProcess | null = null
let webProcess: ChildProcess | null = null
let isQuitting = false

// ── Path helpers ────────────────────────────────────────────────────────────

function getPythonPath(): string {
  const binDir = process.platform === 'win32' ? 'Scripts' : 'bin'
  const pyBin = process.platform === 'win32' ? 'python.exe' : 'python'
  return path.join(REPO_ROOT, '.venv', binDir, pyBin)
}

function getTsxPath(): string {
  const bin = process.platform === 'win32' ? 'tsx.cmd' : 'tsx'
  return path.join(WEB_DIR, 'node_modules', '.bin', bin)
}

// ── Port readiness check ─────────────────────────────────────────────────────

function waitForPort(port: number, timeoutMs = 20_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs
    const attempt = () => {
      const sock = createConnection(port, '127.0.0.1')
      sock.on('connect', () => { sock.destroy(); resolve() })
      sock.on('error', () => {
        sock.destroy()
        if (Date.now() >= deadline) {
          reject(new Error(`localhost:${port} did not become ready within ${timeoutMs}ms`))
        } else {
          setTimeout(attempt, 300)
        }
      })
    }
    attempt()
  })
}

// ── Subprocess management ────────────────────────────────────────────────────

function startDaemon() {
  const python = getPythonPath()
  if (!existsSync(python)) {
    console.warn(`[daemon] Python venv not found at ${python}`)
    console.warn('[daemon] Run "uv sync" in the repo root first.')
    return
  }
  daemonProcess = spawn(python, ['-m', 'daemon', 'start'], {
    cwd: REPO_ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env },
  })
  daemonProcess.stdout?.on('data', (d: Buffer) => process.stdout.write(`[daemon] ${d}`))
  daemonProcess.stderr?.on('data', (d: Buffer) => process.stderr.write(`[daemon] ${d}`))
  daemonProcess.on('exit', (code: number | null) => console.log(`[daemon] exited (${code})`))
  console.log('[daemon] started')
}

function startWebServer() {
  const tsx = getTsxPath()
  if (!existsSync(tsx)) {
    console.warn(`[server] tsx not found at ${tsx}. Run "npm install" in web/.`)
    return
  }
  webProcess = spawn(tsx, ['server/index.ts'], {
    cwd: WEB_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, NODE_ENV: 'production' },
  })
  webProcess.stdout?.on('data', (d: Buffer) => process.stdout.write(`[server] ${d}`))
  webProcess.stderr?.on('data', (d: Buffer) => process.stderr.write(`[server] ${d}`))
  webProcess.on('exit', (code: number | null) => console.log(`[server] exited (${code})`))
  console.log('[server] started')
}

function cleanup() {
  if (daemonProcess && !daemonProcess.killed) {
    console.log('Stopping daemon...')
    daemonProcess.kill('SIGTERM')
    daemonProcess = null
  }
  if (webProcess && !webProcess.killed) {
    console.log('Stopping web server...')
    webProcess.kill('SIGTERM')
    webProcess = null
  }
}

// ── Window ───────────────────────────────────────────────────────────────────

async function createWindow() {
  // Always wait for the Hono server (API backend)
  console.log(`[app] Waiting for Hono server on port ${WEB_PORT}...`)
  await waitForPort(WEB_PORT).catch((e: Error) => {
    console.warn('[app]', e.message)
  })

  const url = isDev ? 'http://localhost:5173' : `http://localhost:${WEB_PORT}`
  console.log(`[app] Loading ${url}`)

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'homelife.ai',
    backgroundColor: '#0f172a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.loadURL(url)

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  // macOS: hide window on close rather than quitting
  mainWindow.on('close', (e) => {
    if (process.platform === 'darwin' && !isQuitting) {
      e.preventDefault()
      mainWindow?.hide()
    }
  })

  mainWindow.on('closed', () => { mainWindow = null })
}

// ── System tray ──────────────────────────────────────────────────────────────

function createTray() {
  // Provide a 16x16 tray-icon.png in web/electron/ to use a custom icon.
  const iconPath = path.join(__dirname, '..', 'tray-icon.png')
  const icon = existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()

  tray = new Tray(icon)
  tray.setToolTip('homelife.ai')

  const menu = Menu.buildFromTemplate([
    {
      label: 'Open homelife.ai',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        } else {
          createWindow()
        }
      },
    },
    {
      label: 'Open in Browser',
      click: () => shell.openExternal(`http://localhost:${WEB_PORT}`),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => { isQuitting = true; app.quit() },
    },
  ])

  tray.setContextMenu(menu)
  tray.on('double-click', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startDaemon()
  startWebServer()
  createTray()
  await createWindow()

  // macOS: re-open window when clicking dock icon
  app.on('activate', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    } else {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  // On macOS keep the app running in the tray
  if (process.platform !== 'darwin') {
    isQuitting = true
    app.quit()
  }
})

app.on('before-quit', cleanup)

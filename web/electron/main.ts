import { app, BrowserWindow, Tray, Menu, shell, nativeImage, dialog } from 'electron'
import { spawn, ChildProcess, execFileSync } from 'child_process'
import { createConnection } from 'net'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import path from 'path'

const isDev = process.argv.includes('--dev')
const WEB_PORT = 3001
const WEB_DIR = app.getAppPath()

// ── WSL2 bridge mode (Windows launcher → WSL2) ──────────────────────────────
const IS_WSL2_BRIDGE = process.env.HOMELIFE_WSL2_BRIDGE === '1'

// ── Runtime paths (set during boot) ─────────────────────────────────────────
let PYTHON_BIN = ''   // path to venv python
let CONFIG_DIR = ''   // where life.toml and .env live
let DATA_DIR   = ''   // where data/ lives
let DAEMON_SRC = ''   // parent dir containing daemon/ package (for PYTHONPATH)

// Development mode: repo root is one level above web/
const DEV_REPO_ROOT = path.join(WEB_DIR, '..')

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let daemonProcess: ChildProcess | null = null
let webProcess: ChildProcess | null = null
let isQuitting = false

// ── Default config written on first launch ───────────────────────────────────

const DEFAULT_TOML = `[llm]
provider = "gemini"
gemini_model = "gemini-3.1-flash-lite-preview"

[capture]
interval_sec = 30

[presence]
enabled = true
`

// ── Path helpers ─────────────────────────────────────────────────────────────

function getPythonBin(venvDir: string): string {
  return process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python')
}

function getTsxPath(): string {
  const bin = process.platform === 'win32' ? 'tsx.cmd' : 'tsx'
  return path.join(WEB_DIR, 'node_modules', '.bin', bin)
}

// ── Packaged app first-run setup ─────────────────────────────────────────────

async function setupPackaged(): Promise<boolean> {
  const userData = app.getPath('userData')
  const resources = process.resourcesPath

  CONFIG_DIR  = userData
  DATA_DIR    = path.join(userData, 'data')
  DAEMON_SRC  = path.join(resources, 'daemon-src')
  const venvDir = path.join(userData, '.venv')
  PYTHON_BIN  = getPythonBin(venvDir)
  const uvBin = path.join(resources, process.platform === 'win32' ? 'uv.exe' : 'uv')

  mkdirSync(DATA_DIR, { recursive: true })

  // Write default life.toml on first run
  const tomlPath = path.join(CONFIG_DIR, 'life.toml')
  if (!existsSync(tomlPath)) {
    writeFileSync(tomlPath, DEFAULT_TOML)
  }

  // First run: create Python venv using bundled uv
  if (!existsSync(PYTHON_BIN)) {
    if (!existsSync(uvBin)) {
      dialog.showErrorBox(
        'Setup error',
        `Bundled uv not found at: ${uvBin}\n\nThis is a packaging issue. Please report it.`,
      )
      return false
    }

    await dialog.showMessageBox({
      type: 'info',
      title: 'homelife.ai — First Launch',
      message: 'Setting up Python environment…\nThis will take about a minute.',
      buttons: ['Continue'],
    })

    try {
      execFileSync(uvBin, ['sync', '--project', DAEMON_SRC], {
        env: {
          ...process.env,
          UV_PROJECT_ENVIRONMENT: venvDir,
          // Suppress interactive prompts
          UV_NO_PROGRESS: '1',
        },
        timeout: 5 * 60 * 1000, // 5 min
      })
    } catch (e) {
      dialog.showErrorBox(
        'Setup failed',
        `Failed to set up Python environment:\n${e}\n\nCheck your internet connection and try again.`,
      )
      return false
    }
  }

  if (!existsSync(PYTHON_BIN)) {
    dialog.showErrorBox('Setup error', `Python not found at ${PYTHON_BIN} after uv sync.`)
    return false
  }

  return true
}

// ── Development mode paths ────────────────────────────────────────────────────

function setupDev() {
  CONFIG_DIR = DEV_REPO_ROOT
  DATA_DIR   = path.join(DEV_REPO_ROOT, 'data')
  DAEMON_SRC = DEV_REPO_ROOT
  const binDir = process.platform === 'win32' ? 'Scripts' : 'bin'
  const pyBin  = process.platform === 'win32' ? 'python.exe' : 'python'
  PYTHON_BIN = path.join(DEV_REPO_ROOT, '.venv', binDir, pyBin)
}

// ── Port readiness ────────────────────────────────────────────────────────────

function waitForPort(port: number, timeoutMs = 30_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs
    const attempt = () => {
      const sock = createConnection(port, '127.0.0.1')
      sock.on('connect', () => { sock.destroy(); resolve() })
      sock.on('error', () => {
        sock.destroy()
        if (Date.now() >= deadline) {
          reject(new Error(`localhost:${port} not ready after ${timeoutMs}ms`))
        } else {
          setTimeout(attempt, 500)
        }
      })
    }
    attempt()
  })
}

// ── Subprocess management ─────────────────────────────────────────────────────

function startDaemon() {
  if (IS_WSL2_BRIDGE) {
    const repo = process.env.HOMELIFE_REPO || ''
    console.log('[daemon] WSL2 bridge mode')
    daemonProcess = spawn(
      'wsl.exe',
      ['-e', 'bash', '-c', `cd "${repo}" && .venv/bin/python -m daemon start`],
      { stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env } },
    )
  } else {
    if (!existsSync(PYTHON_BIN)) {
      dialog.showErrorBox('Python not found', `${PYTHON_BIN}\n\nRun "uv sync" in ${CONFIG_DIR} and restart.`)
      return
    }
    daemonProcess = spawn(PYTHON_BIN, ['-m', 'daemon', 'start'], {
      cwd: CONFIG_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONPATH: DAEMON_SRC,
        DATA_DIR,
      },
    })
  }
  daemonProcess.stdout?.on('data', (d: Buffer) => process.stdout.write(`[daemon] ${d}`))
  daemonProcess.stderr?.on('data', (d: Buffer) => process.stderr.write(`[daemon] ${d}`))
  daemonProcess.on('exit', (code: number | null) => console.log(`[daemon] exited (${code})`))
  console.log('[daemon] started')
}

function startWebServer() {
  if (IS_WSL2_BRIDGE) {
    const repo = process.env.HOMELIFE_REPO || ''
    console.log('[server] WSL2 bridge mode')
    webProcess = spawn(
      'wsl.exe',
      ['-e', 'bash', '-c', `cd "${repo}/web" && NODE_ENV=production node_modules/.bin/tsx server/index.ts`],
      { stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env } },
    )
  } else {
    const tsx = getTsxPath()
    if (!existsSync(tsx)) {
      dialog.showErrorBox('tsx not found', `${tsx}\n\nRun "npm install" in web/ and restart.`)
      return
    }
    webProcess = spawn(tsx, ['server/index.ts'], {
      cwd: WEB_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        NODE_ENV: 'production',
        DATA_DIR,
        HOMELIFE_CONFIG_DIR: CONFIG_DIR,
        HOMELIFE_PYTHON: PYTHON_BIN,
        HOMELIFE_DAEMON_SRC: DAEMON_SRC,
      },
    })
  }
  webProcess.stdout?.on('data', (d: Buffer) => process.stdout.write(`[server] ${d}`))
  webProcess.stderr?.on('data', (d: Buffer) => process.stderr.write(`[server] ${d}`))
  webProcess.on('exit', (code: number | null) => console.log(`[server] exited (${code})`))
  console.log('[server] started')
}

function cleanup() {
  if (daemonProcess && !daemonProcess.killed) {
    daemonProcess.kill('SIGTERM'); daemonProcess = null
  }
  if (webProcess && !webProcess.killed) {
    webProcess.kill('SIGTERM'); webProcess = null
  }
}

// ── Window ────────────────────────────────────────────────────────────────────

async function createWindow() {
  console.log(`[app] Waiting for Hono server on port ${WEB_PORT}…`)
  await waitForPort(WEB_PORT).catch((e: Error) => console.warn('[app]', e.message))

  const url = isDev ? 'http://localhost:5173' : `http://localhost:${WEB_PORT}`
  const iconPath = path.join(__dirname, '..', 'icon.png')

  mainWindow = new BrowserWindow({
    width: 1400, height: 900,
    minWidth: 900, minHeight: 600,
    title: 'homelife.ai',
    backgroundColor: '#0f172a',
    icon: existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.loadURL(url)
  if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' })

  mainWindow.on('close', (e) => {
    if (process.platform === 'darwin' && !isQuitting) {
      e.preventDefault(); mainWindow?.hide()
    }
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

// ── System tray ───────────────────────────────────────────────────────────────

function createTray() {
  const iconPath = path.join(__dirname, '..', 'tray-icon.png')
  const icon = existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()

  tray = new Tray(icon)
  tray.setToolTip('homelife.ai')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open homelife.ai', click: () => { mainWindow ? (mainWindow.show(), mainWindow.focus()) : createWindow() } },
    { label: 'Open in Browser', click: () => shell.openExternal(`http://localhost:${WEB_PORT}`) },
    { type: 'separator' },
    { label: 'Quit', click: () => { isQuitting = true; app.quit() } },
  ]))
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  if (IS_WSL2_BRIDGE) {
    // WSL2 bridge: paths are managed by start.ps1 env vars, no setup needed
  } else if (app.isPackaged) {
    const ok = await setupPackaged()
    if (!ok) { app.quit(); return }
  } else {
    setupDev()
  }

  startDaemon()
  startWebServer()
  createTray()
  await createWindow()

  app.on('activate', () => {
    mainWindow ? (mainWindow.show(), mainWindow.focus()) : createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') { isQuitting = true; app.quit() }
})

app.on('before-quit', cleanup)

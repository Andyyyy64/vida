# Getting Started

**English** | [日本語](getting-started.ja.md)

- [Windows (Native)](#windows-native)
- [Windows (WSL2)](#windows-wsl2)
- [Mac](#mac)
- [Common Configuration](#common-configuration)
- [Running](#running)

---

## Windows (Native)

Runs directly on Windows — no WSL2 required. Camera uses DirectShow, audio uses WASAPI via sounddevice, screen capture and window tracking use PowerShell. The Tauri desktop app runs as a native Windows process.

### 1. Python 3.12+

Download and install from [python.org](https://www.python.org/downloads/) or via winget:

```powershell
winget install Python.Python.3.12
```

### 2. uv (Python package manager)

```powershell
winget install astral-sh.uv
```

Or with PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Node.js 22+

```powershell
winget install OpenJS.NodeJS.LTS
```

### 4. Repository setup

```powershell
git clone <repo-url> homelife.ai
cd homelife.ai

# Python dependencies (includes sounddevice for WASAPI audio)
uv sync

# Web UI
cd web
npm install
cd ..
```

### 5. Windows Privacy Permissions

Go to **Settings → Privacy & Security** and allow the following for your terminal app (PowerShell, Windows Terminal, etc.):

| Permission | Used for |
|---|---|
| Camera | Built-in / USB camera capture |
| Microphone | Built-in / USB microphone recording |

> Screen capture and window tracking are done through PowerShell — no additional permissions required.

---

## Windows (WSL2)

Runs on Ubuntu inside WSL2. Screen capture and window tracking operate on the Windows side via PowerShell. Camera and microphone are passed through from USB using usbipd.

### 1. WSL2 + Ubuntu

In PowerShell (Administrator):

```powershell
wsl --install -d Ubuntu-24.04
```

Launch Ubuntu and set up your username and password.

### 2. Python 3.12+

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### 3. uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 4. Node.js 22+

```bash
curl -fsSL https://fnm.vercel.app/install | bash
source ~/.bashrc
fnm install 22
fnm use 22
```

### 5. alsa-utils (audio recording)

```bash
sudo apt install -y alsa-utils
# Add yourself to the audio group (takes effect after re-login)
sudo usermod -aG audio $USER
```

### 6. Connecting the camera via usbipd

Install **usbipd-win** on the Windows side (PowerShell, Administrator):

```powershell
winget install usbipd
```

Find your camera's bus ID and attach it to WSL2:

```powershell
usbipd list
usbipd bind --busid <BUSID>        # e.g. 2-3
usbipd attach --wsl --busid <BUSID>
```

> `usbipd attach` must be re-run each time you restart Windows or WSL2. To automate it, set up a Task Scheduler job that runs on login.

Verify the device is visible inside WSL2:

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```

### 7. Repository setup

```bash
git clone <repo-url> homelife.ai
cd homelife.ai

# Python dependencies
uv sync

# Web UI
cd web && npm install && cd ..
```

---

## Mac

Uses the built-in camera and microphone directly — no USB passthrough or external devices required. Screen capture uses `screencapture` and window tracking uses `osascript`, both built into macOS.

### 1. Python 3.12+

Via [pyenv](https://github.com/pyenv/pyenv) (recommended):

```bash
brew install pyenv
pyenv install 3.12
pyenv global 3.12
```

Or directly via Homebrew:

```bash
brew install python@3.12
```

### 2. uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc
```

### 3. Node.js 22+

```bash
brew install fnm
fnm install 22
fnm use 22
```

Or directly:

```bash
brew install node@22
```

### 4. Repository setup

```bash
git clone <repo-url> homelife.ai
cd homelife.ai

# Python dependencies (includes sounddevice for CoreAudio)
uv sync

# Web UI
cd web && npm install && cd ..
```

### 5. macOS Privacy Permissions

You can pre-grant permissions before first launch to avoid mid-run prompts. Go to **System Settings → Privacy & Security** and enable the following for your terminal app (Terminal, iTerm2, etc.):

| Permission | Used for |
|---|---|
| Camera | Built-in camera capture |
| Microphone | Built-in microphone recording |
| Accessibility | Window tracking via osascript |
| Screen Recording | Screen capture via screencapture |

> **Screen Recording on macOS Sequoia+**: Without this permission, `screencapture` produces a black image. Grant it explicitly even if the capture command doesn't prompt for it.

After changing permissions, **restart your terminal** before running `life start`.

---

## Common Configuration

### API key

**Desktop app (recommended):** Launch the app, open **Settings**, and enter your Gemini API key there. Settings are stored in the SQLite database (`data/life.db`).

**CLI-only fallback:** If running the daemon without the desktop app, set the API key via `.env`:

```bash
echo "GEMINI_API_KEY=your-key-here" > .env
```

Get a Gemini API key at [Google AI Studio](https://aistudio.google.com/).

### Configuration

**Desktop app:** All settings are managed via the **Settings UI** in the app. Defaults are applied on first launch.

**CLI-only fallback:** For headless/CLI usage, you can configure settings via `life.toml`:

```toml
[llm]
provider = "gemini"
gemini_model = "gemini-3.1-flash-lite-preview"

[capture]
interval_sec = 30

[presence]
enabled = true
```

See the [Configuration section in README.md](README.md#configuration) for all options.

### User profile (optional, recommended)

Helps the LLM understand who you are and what you typically do.

```bash
mkdir -p data
cat > data/context.md << 'EOF'
Name: (your name)
Occupation: (what you do)
Environment: (home/office, primary language, etc.)
Notes: (habits, recurring activities)
EOF
```

---

## Running

### Desktop app (recommended)

Download the installer from [Releases](https://github.com/Andyyyy64/vida/releases) and run it. The Python environment is set up automatically on first launch.

For development mode:

```bash
cd web && npx tauri dev
```

The app manages the daemon automatically. It minimizes to the system tray when you close the window.

### CLI mode

```bash
life start -d       # Start daemon in background
```

- Live feed: http://localhost:3002

### Verify it's working

```bash
# Capture and analyze a single frame immediately
life look

# Show recent frame analyses
life recent

# Check daemon status
life status
```

### Windows: camera not detected

```powershell
# Re-attach from Windows side
usbipd attach --wsl --busid <BUSID>
```

```bash
# Check device number inside WSL2
v4l2-ctl --list-devices
# Update device in Settings UI, or in life.toml for CLI-only use:
# [capture]
# device = 1   # if camera is /dev/video1
```

### Mac: permission errors

| Symptom | Fix |
|---|---|
| Screenshot is black | Grant Screen Recording permission |
| Camera fails to open | Grant Camera permission |
| Window title not captured | Grant Accessibility permission |

Go to System Settings → Privacy & Security, check the relevant entry for your terminal, then restart the terminal and re-run `life start`.

# Getting Started — 日本語

[English](getting-started.md) | **日本語**

- [Windows（ネイティブ）](#windows-native)
- [Windows (WSL2)](#windows-wsl2)
- [Mac](#mac)
- [共通設定](#共通設定)
- [起動](#起動)

---

## Windows Native

WSL2 不要。カメラは DirectShow、音声は WASAPI（sounddevice）、画面キャプチャとウィンドウ監視は PowerShell を使用。Tauri デスクトップアプリがネイティブ Windows プロセスとして動作します。

### 1. Python 3.12+

[python.org](https://www.python.org/downloads/) からインストール、または winget で:

```powershell
winget install Python.Python.3.12
```

### 2. uv（Python パッケージマネージャー）

```powershell
winget install astral-sh.uv
```

または PowerShell で:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Node.js 22+

```powershell
winget install OpenJS.NodeJS.LTS
```

### 4. リポジトリのセットアップ

```powershell
git clone <repo-url> homelife.ai
cd homelife.ai

# Python 依存関係（sounddevice も含まれます）
uv sync

# Web UI
cd web
npm install
cd ..
```

### 5. Windows プライバシー設定

**設定 → プライバシーとセキュリティ** で、ターミナルアプリ（PowerShell、Windows Terminal など）に以下を許可してください:

| 権限 | 用途 |
|---|---|
| カメラ | 内蔵 / USB カメラの撮影 |
| マイク | 内蔵 / USB マイクの録音 |

> 画面キャプチャとウィンドウ監視は PowerShell 経由のため、追加の権限は不要です。

---

## Windows (WSL2)

WSL2 上の Ubuntu で動作します。スクリーンキャプチャとウィンドウ監視は PowerShell 経由で Windows 側を操作し、カメラ・マイクは usbipd で USB デバイスを WSL2 に渡します。

### 1. WSL2 + Ubuntu のセットアップ

PowerShell（管理者）で実行:

```powershell
wsl --install -d Ubuntu-24.04
```

インストール後、Ubuntu を起動してユーザー名・パスワードを設定します。

### 2. Python 3.12+

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### 3. uv（Python パッケージマネージャ）

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

### 5. alsa-utils（音声録音）

```bash
sudo apt install -y alsa-utils
# audio グループに追加（再ログイン後に有効）
sudo usermod -aG audio $USER
```

### 6. カメラの WSL2 への接続（usbipd）

**Windows 側**（PowerShell 管理者）に usbipd をインストール:

```powershell
winget install usbipd
```

カメラを接続して USB バス ID を確認し、WSL2 にアタッチ:

```powershell
usbipd list
usbipd bind --busid <BUSID>       # 例: 2-3
usbipd attach --wsl --busid <BUSID>
```

> PCを再起動したり WSL2 を再起動するたびに `usbipd attach` が必要です。自動化したい場合は Task Scheduler でログイン時に実行するよう設定してください。

WSL2 側でデバイスが認識されているか確認:

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```

### 7. リポジトリのセットアップ

```bash
git clone <repo-url> homelife.ai
cd homelife.ai

# Python 依存関係
uv sync

# Web UI
cd web && npm install && cd ..
```

---

## Mac

カメラ・マイクは内蔵のものをそのまま使います。外付けデバイスや USB パススルーは不要です。スクリーンキャプチャは `screencapture`、ウィンドウ監視は `osascript` を使用します（どちらも macOS 内蔵）。

### 1. Python 3.12+

[pyenv](https://github.com/pyenv/pyenv) 経由が推奨:

```bash
brew install pyenv
pyenv install 3.12
pyenv global 3.12
```

または Homebrew で直接:

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

または Homebrew で直接:

```bash
brew install node@22
```

### 4. リポジトリのセットアップ

```bash
git clone <repo-url> homelife.ai
cd homelife.ai

# Python 依存関係（sounddevice も含む）
uv sync

# Web UI
cd web && npm install && cd ..
```

### 5. macOS のプライバシー権限

初回起動時にダイアログが出ますが、**事前に手動で許可**しておくとスムーズです。

**システム設定 → プライバシーとセキュリティ** で以下を許可してください。

- ターミナルから `vida` を動かす場合: Terminal / iTerm2 などのターミナルアプリ
- 配布版デスクトップアプリを使う場合: `vida`

| 項目 | 対象アプリ | 用途 |
|---|---|---|
| カメラ | Terminal（または使用するターミナル） | 内蔵カメラ |
| マイク | Terminal（または使用するターミナル） | 内蔵マイク |
| アクセシビリティ | Terminal（または使用するターミナル） | ウィンドウ監視（osascript） |
| 画面収録 | Terminal（または使用するターミナル） | スクリーンキャプチャ |

> **画面収録権限**について: macOS Sequoia 以降、`screencapture` コマンドにも画面収録の許可が必要です。許可していない場合、スクリーンキャプチャが黒画像になります。

権限を変更したあとは、対象アプリを再起動してください。

- **CLI / ターミナル運用**: ターミナルを再起動してから `life start`
- **デスクトップアプリ**: `vida.app` を終了して再起動

---

## 共通設定

### API キー

**デスクトップアプリ（推奨）:** アプリを起動し、**設定**パネルでGemini APIキーを入力してください。設定はSQLiteデータベース（`data/life.db`）に保存されます。

**CLIのみのフォールバック:** デスクトップアプリなしでデーモンを実行する場合は、`.env`でAPIキーを設定します:

```bash
echo "GEMINI_API_KEY=your-key-here" > .env
```

Gemini API キーは [Google AI Studio](https://aistudio.google.com/) で取得できます。

### 設定

**デスクトップアプリ:** すべての設定はアプリ内の**設定UI**で管理されます。初回起動時にデフォルト値が自動適用されます。

**CLIのみのフォールバック:** ヘッドレス/CLI使用の場合は、`life.toml`で設定できます:

```toml
[llm]
provider = "gemini"
gemini_model = "gemini-3.1-flash-lite-preview"

[capture]
interval_sec = 30

[presence]
enabled = true
```

全オプションは [README.md の Configuration セクション](README.md#configuration) を参照。

### ユーザープロファイル（任意・推奨）

LLM がユーザーの名前・職業・環境を把握するためのコンテキストファイル。

```bash
mkdir -p data
cat > data/context.md << 'EOF'
名前: （あなたの名前）
職業: （職業・やっていること）
環境: （自宅/オフィス、使用言語など）
その他: （習慣やよくやること）
EOF
```

---

## 起動

### デスクトップアプリ（推奨）

[Releases](https://github.com/Andyyyy64/vida/releases) からインストーラーをダウンロードして実行。初回起動時にPython環境が自動セットアップされます。

開発モードで起動する場合:

```bash
cd web && npx tauri dev
```

アプリがデーモンを自動管理します。ウィンドウを閉じるとシステムトレイに格納されます。

### CLI モード

```bash
life start -d       # デーモンをバックグラウンドで起動
```

- ライブフィード: http://localhost:3002

### 動作確認

```bash
# 単体でフレーム解析（カメラ・画面・LLM が動くか確認）
life look

# 最近のフレーム確認
life recent

# デーモンの状態確認
life status
```

### Windows: カメラが認識されない場合

```powershell
# Windows 側で再アタッチ
usbipd attach --wsl --busid <BUSID>
```

```bash
# WSL2 側でデバイス確認
v4l2-ctl --list-devices
# 設定UIでdevice番号を変更、またはCLIのみの場合はlife.tomlで変更:
# [capture]
# device = 1   # /dev/video1 なら 1
```

### Mac: 権限エラーが出る場合

```
# スクリーンキャプチャが真っ黒 → 画面収録権限
# カメラが開けない → カメラ権限
# ウィンドウ名が取得できない → アクセシビリティ権限
```

システム設定 → プライバシーとセキュリティ で該当項目を確認し、ターミナルアプリにチェックを入れてください。変更後はターミナルを再起動してから `life start` を実行してください。

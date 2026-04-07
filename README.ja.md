# vida

> *vida* — スペイン語で「人生」。あなたの毎日を、記憶する。

[![CI](https://github.com/Andyyyy64/vida/actions/workflows/ci.yml/badge.svg)](https://github.com/Andyyyy64/vida/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/Andyyyy64/vida/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

[English](README.md) | **日本語**

あなたの日常をそっと見守り、すべてを記憶し、時間の使い方を可視化するパーソナルAI。

## クイックスタート

> **前提条件:** Python 3.12+、Node.js 22+、[uv](https://docs.astral.sh/uv/)、[Gemini APIキー](https://aistudio.google.com/)
> 未インストールの場合は[セットアップガイド](getting-started.ja.md)を参照してください。

<details>
<summary><b>Windows（PowerShell）— 5分</b></summary>

```powershell
# 1. クローン & インストール
git clone https://github.com/Andyyyy64/vida.git
cd vida
uv sync
cd web; npm install; cd ..

# 2. APIキーを設定
"GEMINI_API_KEY=your-key-here" | Out-File -Encoding utf8 .env
# 初回起動後は、アプリ内の設定パネルからもAPIキーを設定できます。

# 3. デスクトップアプリを起動
cd web; npx tauri dev
```

> **権限:** 起動時にカメラ・マイクへのアクセスを求められたら、**設定 → プライバシーとセキュリティ**で許可してください。

</details>

<details>
<summary><b>macOS（ターミナル）— 5分</b></summary>

```bash
# 1. クローン & インストール
git clone https://github.com/Andyyyy64/vida.git
cd vida
uv sync
cd web && npm install && cd ..

# 2. APIキーを設定
echo "GEMINI_API_KEY=your-key-here" > .env
# 初回起動後は、アプリ内の設定パネルからもAPIキーを設定できます。

# 3. デスクトップアプリを起動
cd web && npx tauri dev
```

> **権限:** ターミナルアプリに対して、**システム設定 → プライバシーとセキュリティ**でカメラ・マイク・画面収録・アクセシビリティを許可してください。詳細は[macOS権限ガイド](getting-started.ja.md#5-macos-のプライバシー権限)を参照。

</details>

<details>
<summary><b>Linux / WSL2</b></summary>

```bash
git clone https://github.com/Andyyyy64/vida.git
cd vida
uv sync
cd web && npm install && cd ..
echo "GEMINI_API_KEY=your-key-here" > .env
# 初回起動後は、アプリ内の設定パネルからもAPIキーを設定できます。

# デーモン + Web UIを起動
./start.sh
# デスクトップアプリが自動で開きます
```

WSL2でのカメラ設定（usbipd）については[セットアップガイド](getting-started.ja.md#windows-wsl2)を参照。

</details>

**動作確認:**

```bash
life look      # フレームを1枚撮影して分析
life status    # デーモンの状態確認
```

デスクトップアプリが自動的に開きます。ビルド済みインストーラーは [Releases](https://github.com/Andyyyy64/vida/releases) からダウンロードできます。

---

## 目次

- [ビジョン](#ビジョン)
- [機能](#機能)
- [アーキテクチャ](#アーキテクチャ)
- [プロジェクト構造](#プロジェクト構造)
- [セットアップ](#セットアップ) — 必要要件、設定、Docker
- [CLIコマンド](#cliコマンド)
- [設定リファレンス](#設定)
- [IPCコマンド](#ipcコマンド)
- [データベーススキーマ](#データベーススキーマ)
- [技術スタック](#技術スタック)

## ビジョン

**「人生を監視し、管理し、分析する。」**

3つの柱:

1. **監視** — カメラ・画面・音声・アプリフォーカスを継続的に自動記録。手動入力は一切不要。
2. **管理** — 「あのとき何してた？」に即答できる外部化された記憶。日記不要の全文検索可能なログ。
3. **分析** — 「どれだけ集中できた？」「時間をどこに使った？」を日次・週次・月次のパターンで可視化。

## 機能

### キャプチャ・センシング

- **インターバルキャプチャ** — ウェブカメラ・画面・音声を30秒ごとに記録（設定変更可）。その間も1秒ごとに変化を検出し、大きな変化があれば追加フレームを保存（画面: 10%閾値、カメラ: 15%知覚ハッシュ差）。
- **フォアグラウンドウィンドウ追跡** — Win32 P/Invoke（`GetForegroundWindow`）を使ったPowerShellプロセスで500msごとにアプリのフォーカス変化を記録。プロセス名とウィンドウタイトルを取得し、アプリ別の正確な使用時間を算出。
- **在席検出** — Haarカスケード顔検出 + MOG2モーション解析によるヒステリシス状態機械（在席 → 離席 → 就寝）。3回連続で顔未検出になるまで遷移しない。設定した夜間時間帯に画面が暗い場合は就寝と判定。
- **音声キャプチャ・文字起こし** — ALSAで自動デバイス検出・録音。無音トリミング（振幅500閾値、最低0.3秒の発話）で意味のある音声のみ保存。LLMがユーザーコンテキストを踏まえて文字起こし。
- **ライブフィード** — ポート3002でMJPEGストリーミング（約30fps）。メインキャプチャとは独立して動作。

### AI分析

- **フレーム分析** — 毎ティックにカメラ画像・画面キャプチャ・音声・ウィンドウ情報をLLM（GeminiまたはClaude）に送信。アクティビティカテゴリと自然言語説明をJSON形式で取得。
- **アクティビティ分類** — LLMが既知カテゴリから選択（新カテゴリは自動登録）。LCS類似度（≥0.7）でファジーマッチング・正規化。アクティビティ→メタカテゴリのマッピングは`activity_mappings`テーブルで管理。`life consolidate-activities`コマンドでLLMが類義語・表記ゆれをまとめてマージ可能。
- **メタカテゴリ** — アクティビティを6つのメタカテゴリに動的マッピング: **focus（集中作業）**, **communication（コミュニケーション）**, **entertainment（エンタメ）**, **browsing（ブラウジング）**, **break（休憩）**, **idle（アイドル）**。
- **マルチスケールサマリー** — 階層的に生成: 10分（生フレームから）→ 30分 → 1時間 → 6時間 → 12時間 → 24時間（キーフレーム画像・文字起こし・改善提案含む）。
- **日次レポート** — 日付変更時に自動生成。アクティビティ内訳・タイムライン・集中度（集中フレーム/アクティブフレーム）・イベント一覧を含む。Webhookで配信。
- **コンテキスト認識** — ユーザープロファイル（`data/context.md`）と直近5フレームの履歴を毎回のLLMプロンプトに注入。

### Web UI

- **タイムライン** — フレームを時間帯でグループ化、モーションスコアでサイズ調整、メタカテゴリで色付け。キーボード（矢印キー）とスクロールホイールでフレーム切り替え。
- **詳細パネル** — カメラ画像（クリックで拡大）、画面キャプチャ（メイン + 変化検出分のサムネイルストリップ）、音声プレイヤー + 文字起こし、ウィンドウ情報、全メタデータ。
- **サマリーパネル** — スケール別（10分〜24時間）に展開・折りたたみ。サマリーをクリックするとタイムライン上の対応時間帯をハイライト。
- **ダッシュボード** — 集中スコア%、メタカテゴリ別円グラフ、アクティビティ一覧（継続時間バー）、アプリ使用時間TOP10（切り替え回数付き）、週次スタックバーチャート、ガントスタイルセッションタイムライン。
- **検索** — フレーム説明・文字起こし・アクティビティ・ウィンドウタイトル・サマリーをFTS5トライグラム全文検索。結果クリックで対象日時・フレームにジャンプ。
- **アクティビティヒートマップ** — 24時間×フレーム数の強度ヒートマップ。
- **ライブフィード** — LIVE/OFFLINEインジケーター付きリアルタイムMJPEGストリーム、フルスクリーンモーダルに拡大可能。
- **モバイル対応** — 狭い画面ではタブ切り替え（サマリー / タイムライン / 詳細）のレスポンシブレイアウト。
- **自動更新** — 今日のデータ表示時は30秒ごとにフレーム・サマリー・イベントをポーリング。

### チャットプラットフォーム連携

チャットの会話を収集して「外部化された記憶」を強化します。何を誰と話していたかという情報は、日常の活動記録に不可欠な次元を加えます。

**アーキテクチャ:** 統一された`ChatSource`インターフェースによるアダプターパターン。`life.toml`で使うプラットフォームのみ有効化。

| プラットフォーム | 状態 | 方式 | DM | サーバー/グループ |
|---|---|---|---|---|
| **Discord** | 実装済み | REST APIポーリング（ユーザートークン） | ✓ | ✓ |
| **LINE** | 計画中 | チャット履歴エクスポート | ✓ | ✓ |
| **Slack** | 計画中 | Botトークン + Events API | — | ✓ |
| **Telegram** | 計画中 | Bot API / TDLib | ✓ | ✓ |
| **WhatsApp** | 計画中 | チャット履歴エクスポート | ✓ | ✓ |
| **Teams** | 計画中 | Microsoft Graph API | ✓ | ✓ |

**動作フロー:**
1. プラットフォームアダプターがバックグラウンドスレッドで新着メッセージをポーリング
2. メッセージを`chat_messages`テーブルに統一スキーマで保存
3. 直近の会話をLLMプロンプトに注入 — フレーム分析が「Discordでこの話題を議論していた」という情報を受け取る
4. 日次レポートにチャット活動サマリー（チャンネル別メッセージ数）を含む

## アーキテクチャ

```
daemon/ (Python)         tauri/ (Rust)             frontend (React)
  ├─ カメラキャプチャ      ├─ IPCコマンド             ├─ タイムライン
  ├─ 画面キャプチャ        ├─ rusqliteクエリ          ├─ フレーム詳細
  ├─ 音声キャプチャ        ├─ アセットプロトコル       ├─ サマリーパネル
  ├─ ウィンドウ監視        ├─ デーモン管理            ├─ ライブフィード
  ├─ 在席検出             └─ システムトレイ           ├─ ダッシュボード
  ├─ LLM分析                                        ├─ 検索
  ├─ サマリー生成                                    ├─ ヒートマップ
  ├─ レポート生成                                    └─ モバイル対応
  ├─ チャット連携
  ├─ 変化検出
  ├─ SQLite 書き込み
  └─ MJPEGライブサーバー (port 3002)
```

- デーモンがSQLiteに書き込み、WebサーバーがWALモードで読み取り（同時アクセス対応）
- ウィンドウモニターは独立したSQLite接続を持つ永続PowerShellプロセスで動作
- 共有`data/`ディレクトリ: `frames/`, `screens/`, `audio/`, `life.db`
- LLMプロバイダーは抽象化: Gemini または Claude、`life.toml`で設定

### スレッドモデル

| スレッド | 役割 | レート |
|---|---|---|
| メインループ | キャプチャ + 分析 + サマリー生成 | 30秒ごと（設定可） |
| ライブフィード | ウェブカメラ → MJPEGストリーム | 約30fps |
| 音声録音 | インターバル中のALSA録音 | ティックごと |
| ウィンドウモニター | PowerShell → `window_events`テーブル | 500msポーリング |
| 変化検出 | 画面/カメラのハッシュ比較 | ティック間で1秒ごと |
| チャットポーラー | Discord等 → `chat_messages`テーブル | 60秒ごと（設定可） |
| ライブHTTPサーバー | MJPEGをクライアントに配信 | オンデマンド |

## プロジェクト構造

<details>
<summary>クリックして展開</summary>

```
daemon/                  # Pythonパッケージ
  ├─ cli.py              # CLIエントリポイント (Click)
  ├─ daemon.py           # メイン観測ループ
  ├─ config.py           # TOML設定読み込み
  ├─ analyzer.py         # フレーム分析 + サマリー生成
  ├─ activity.py         # ActivityManager: DB管理の正規化 + メタカテゴリマッピング
  ├─ report.py           # 日次レポート生成
  ├─ notify.py           # Discord / LINE Webhook通知
  ├─ live.py             # MJPEGストリーミングサーバー
  ├─ chat/               # チャットプラットフォーム連携
  │   ├─ base.py         # 抽象ChatSourceインターフェース
  │   ├─ discord.py      # Discordアダプター（ユーザートークン、RESTポーリング）
  │   └─ manager.py      # ChatManager: アダプターを統括
  ├─ llm/                # LLMプロバイダー抽象化
  │   ├─ base.py         # 抽象基底クラス
  │   ├─ gemini.py       # Google Gemini（画像・音声対応）
  │   └─ claude.py       # Anthropic Claude（CLI経由）
  ├─ capture/            # データキャプチャモジュール
  │   ├─ camera.py       # ウェブカメラ（V4L2 / AVFoundation）
  │   ├─ screen.py       # 画面キャプチャ（PowerShell / screencapture）
  │   ├─ audio.py        # 音声録音（ALSA / sounddevice）
  │   ├─ window.py       # フォアグラウンドウィンドウ監視（PowerShell+Win32 / osascript）
  │   └─ frame_store.py  # JPEGファイルストレージ
  ├─ analysis/           # ローカル分析（LLM不使用）
  │   ├─ motion.py       # MOG2背景差分
  │   ├─ scene.py        # 輝度分類
  │   ├─ change.py       # 知覚ハッシュ変化検出
  │   ├─ presence.py     # 顔検出 + 状態機械
  │   └─ transcribe.py   # 音声 → テキスト（LLM経由）
  ├─ summary/            # サマリーフォーマット
  │   ├─ formatter.py    # CLI出力フォーマット
  │   └─ timeline.py     # タイムラインデータ構築
  ├─ claude/             # Claude固有機能
  │   ├─ analyzer.py     # レビュー分析
  │   └─ review.py       # 日次レビューパッケージ生成
  └─ storage/            # データベース層
      ├─ database.py     # SQLiteスキーマ、マイグレーション、クエリ
      └─ models.py       # Frame, Event, Summary, Report データクラス

web/                     # Tauri v2 デスクトップアプリ
  ├─ src-tauri/
  │   ├─ src/lib.rs      # アプリ設定、daemon管理、トレイ
  │   ├─ src/db.rs       # SQLite接続、設定、キャッシュ
  │   ├─ src/commands/   # IPCコマンドハンドラー（18モジュール）
  │   └─ tauri.conf.json # アプリ設定、バンドルリソース
  └─ src/
      ├─ App.tsx         # メインSPAオーケストレーター
      ├─ components/     # Reactコンポーネント
      ├─ hooks/          # 30秒ポーリングのデータフェッチ
      └─ lib/            # IPCクライアント、型、アクティビティモジュール、ユーティリティ

data/                    # 実行時データ（gitignore済み）
  ├─ frames/             # カメラJPEG (YYYY-MM-DD/*.jpg)
  ├─ screens/            # 画面PNG (YYYY-MM-DD/*.png)
  ├─ audio/              # 音声WAV (YYYY-MM-DD/*.wav)
  ├─ live/               # 現在のMJPEGストリームフレーム
  ├─ context.md          # LLM用ユーザープロファイル
  ├─ life.db             # SQLiteデータベース（WALモード）
  └─ life.pid            # デーモンPIDファイル
```

</details>

## セットアップ

プラットフォーム別の詳細手順は **[getting-started.ja.md](getting-started.ja.md)** を参照してください。

| プラットフォーム | ガイド |
|---|---|
| Windows（ネイティブ） | [getting-started.ja.md#windows-native](getting-started.ja.md#windows-native) |
| Windows (WSL2) | [getting-started.ja.md#windows-wsl2](getting-started.ja.md#windows-wsl2) |
| Mac | [getting-started.ja.md#mac](getting-started.ja.md#mac) |

### 必要要件

| | Windows（ネイティブ） | Windows (WSL2) | Mac |
|---|---|---|---|
| Python | 3.12+（Windows） | 3.12+（WSL2内） | 3.12+ |
| Node.js | 22+（Windows） | 22+（WSL2内） | 22+ |
| カメラ | 内蔵 / USB（DirectShow） | 外付けUSB（usbipd経由） | 内蔵カメラ |
| マイク | 内蔵 / USB（WASAPI） | 外付けUSB（usbipd経由） | 内蔵マイク |
| 画面キャプチャ | PowerShell + Windows Forms | PowerShell + Windows Forms | `screencapture`（内蔵） |
| ウィンドウ監視 | PowerShell + Win32 API | PowerShell + Win32 API | `osascript`（内蔵） |
| Gemini APIキー | 必要 | 必要 | 必要 |

### 設定

設定はデスクトップアプリの**設定UI**で管理されます（`data/life.db`の`settings`テーブルに保存）。初回起動時にデフォルト値が自動適用されます。CLIのみで使用する場合は、`life.toml`と`.env`がフォールバックとして機能します。

**ヒント:** `data/context.md`に名前・職業・習慣を書くと、AIがより正確なアクティビティ説明を生成します。

全オプションは[下記の設定リファレンス](#設定-1)を参照してください。

### Docker

```bash
docker compose up
```

カメラ・音声デバイスのパススルーは`docker-compose.override.yml`で設定。詳細は[セットアップガイド](getting-started.ja.md)を参照。

## CLIコマンド

| コマンド | 説明 |
|---|---|
| `life start [-d]` | 観測デーモンを起動（`-d`でバックグラウンド） |
| `life stop` | デーモンを停止 |
| `life status` | 状態を表示（フレーム数、サマリー数、ディスク使用量） |
| `life capture` | テストフレームを1枚撮影 |
| `life look` | フレームを撮影してすぐに分析 |
| `life recent [-n 5]` | 直近のフレーム分析を表示 |
| `life today [DATE]` | その日のタイムラインを表示 |
| `life stats [DATE]` | 日次統計を表示 |
| `life summaries [DATE] [--scale 1h]` | サマリーを表示（10m/30m/1h/6h/12h/24h） |
| `life events [DATE]` | 検出イベントを一覧表示 |
| `life report [DATE]` | 日次日記レポートを生成 |
| `life review [DATE] [--json]` | レビューパッケージを生成 |
| `life consolidate-activities` | LLMでアクティビティカテゴリの類義語をマージ |
| `life notify-test` | Webhook通知のテスト送信 |

## 設定

設定はデスクトップアプリの**設定UI**で管理されます（`data/life.db`の`settings`テーブルに保存）。CLIのみで使用する場合は`life.toml`と`.env`がフォールバックとして機能します。以下は利用可能な設定キー（DBキー名）です:

| キー | デフォルト | 説明 |
|------|-----------|------|
| `data_dir` | `"data"` | データディレクトリパス |
| `capture.device` | `0` | カメラデバイスID (/dev/videoN) |
| `capture.interval_sec` | `30` | キャプチャ間隔（秒） |
| `capture.width` | `640` | キャプチャ幅 |
| `capture.height` | `480` | キャプチャ高さ |
| `capture.jpeg_quality` | `85` | JPEG品質 |
| `capture.audio_device` | `""` | 音声デバイス（空欄 = 自動検出） |
| `capture.audio_sample_rate` | `44100` | 音声サンプルレート |
| `analysis.motion_threshold` | `0.02` | MOG2前景ピクセル比率 |
| `analysis.brightness_dark` | `40.0` | これ以下 = DARK |
| `analysis.brightness_bright` | `180.0` | これ以上 = BRIGHT |
| `llm.provider` | `"gemini"` | "gemini" または "claude" |
| `llm.claude_model` | `"haiku"` | Claudeモデル名 |
| `llm.gemini_model` | `"gemini-3.1-flash-lite-preview"` | Geminiモデル名 |
| `presence.enabled` | `true` | 在席検出の有効化 |
| `presence.absent_threshold_ticks` | `3` | 離席判定までのティック数 |
| `presence.sleep_start_hour` | `23` | 就寝検出開始時刻 |
| `presence.sleep_end_hour` | `8` | 就寝検出終了時刻 |
| `notify.provider` | `"discord"` | "discord" または "line" |
| `notify.webhook_url` | `""` | Webhook URL |
| `notify.enabled` | `false` | 通知の有効化 |
| `chat.enabled` | `false` | チャット連携のマスタースイッチ |
| `chat.discord.enabled` | `false` | Discordアダプターの有効化 |
| `chat.discord.user_token` | `""` | Discordユーザートークン |
| `chat.discord.user_id` | `""` | DiscordユーザーID |
| `chat.discord.poll_interval` | `60` | ポーリング間隔（秒） |
| `chat.discord.backfill_months` | `3` | 初回起動時の過去履歴取得月数（0でスキップ） |

## IPCコマンド

フロントエンドはHTTPエンドポイントではなく、Tauriの`invoke()`コマンドでRustバックエンドと通信します。コマンドは`web/src-tauri/src/commands/`で定義されています。

| コマンド | モジュール | 説明 |
|---------|----------|------|
| `get_frames` | frames | 指定日のフレーム一覧 |
| `get_frame` | frames | IDでフレームを取得 |
| `get_latest_frame` | frames | 最新フレームを取得 |
| `get_summaries` | summaries | 日付・スケール別サマリー一覧 |
| `get_events` | events | 指定日のイベント一覧 |
| `get_stats` | stats | 日次統計（カウント、平均、時間別アクティビティ） |
| `get_activities` | stats | アクティビティ別内訳（継続時間・時間別詳細） |
| `get_apps` | stats | ウィンドウイベントからのアプリ使用時間（切り替え回数付き） |
| `get_dates` | stats | データのある日付一覧 |
| `get_range_stats` | stats | 期間別日次統計（メタカテゴリ内訳付き） |
| `get_sessions` | sessions | アクティビティセッション（連続フレームのグループ化） |
| `get_report` | reports | 日次レポート取得 |
| `list_reports` | reports | 最近のレポート一覧 |
| `list_activities` | activities | アクティビティカテゴリ一覧（メタカテゴリ付き） |
| `get_activity_mappings` | activities | アクティビティ → メタカテゴリ マッピングテーブル |
| `search_text` | search | 全文検索（フレーム + サマリー） |
| `export_frames_csv` | export | フレームをCSVでエクスポート |
| `export_summaries_csv` | export | サマリーをCSVでエクスポート |
| `export_report` | export | 日次レポートをJSONでエクスポート |
| `get_live_frame` | live | ライブフィードのJPEGスナップショット |
| `get_settings` | settings | DB設定を取得 |
| `put_settings` | settings | DB設定を更新 |
| `get_memo` | memos | 指定日のメモを取得 |
| `put_memo` | memos | 指定日のメモを保存 |
| `get_context` | context | ユーザープロファイルを取得 |
| `put_context` | context | ユーザープロファイルを更新 |
| `get_devices` | devices | カメラ・音声デバイスの列挙 |
| `get_status` | status | デーモン状態・データディレクトリ情報 |
| `get_data_dir` | status | データディレクトリパスを取得 |
| `get_chat` | chat | 指定日のチャットメッセージを取得 |
| `ask_rag` | rag | RAGベースの質問応答 |
| `get_data_stats` | data | データストレージ統計 |
| `export_table` | data | データベーステーブルのエクスポート |

## データベーススキーマ

<details>
<summary>クリックして展開</summary>

### frames
コアキャプチャデータ: タイムスタンプ、カメラパス、画面パス、追加画面パス、音声パス、文字起こし、輝度、モーションスコア、シーンタイプ、LLM説明、アクティビティカテゴリ、フォアグラウンドウィンドウ。

### window_events
ウィンドウモニターが記録するフォーカス変化イベント: タイムスタンプ、プロセス名、ウィンドウタイトル。`LEAD()`ウィンドウ関数で正確なアプリ使用時間を算出。

### summaries
マルチスケールサマリー（10分〜24時間）: タイムスタンプ、スケール、内容、フレーム数。

### events
検出イベント: シーン変化、モーションスパイク、在席状態変化。元フレームに紐付け。

### activity_mappings
動的なアクティビティ → メタカテゴリマッピング。アクティビティ名が主キー。`meta_category`、初回記録時刻、フレーム数を保持。マイグレーション時に既存フレームからシード。LLMが新アクティビティを生成するたびに自動更新。

### reports
日次自動生成レポート: 内容、フレーム数、集中度%。

### chat_messages
チャットプラットフォームから収集したメッセージ: プラットフォーム、プラットフォーム固有メッセージID、チャンネル/サーバー情報、著者、is_selfフラグ、内容、タイムスタンプ、添付ファイル/埋め込みのJSONメタデータ。(platform, platform_message_id)でユニーク制約。

### memos
日次ユーザーメモ: 日付（主キー）、内容、更新日時。当日のみ編集可、過去は読み取り専用。

### FTSインデックス
`frames_fts`（トライグラム）: description, transcription, activity, foreground_window。`summaries_fts`（トライグラム）: content。

</details>

## 技術スタック

- **デーモン**: Python 3.12 / Click / OpenCV / SQLite（WALモード）
- **LLM**: Google Gemini（画像・音声）/ Anthropic Claude（CLI経由）
- **ウィンドウ追跡**: PowerShell / Win32 P/Invoke（`GetForegroundWindow`）/ osascript（macOS）
- **デスクトップ**: Tauri v2 / Rust / rusqlite / WebView2 (Windows) / WebKitGTK (Linux) / WKWebView (macOS)
- **フロントエンド**: React 19 / TypeScript / Vite 6
- **インフラ**: Docker Compose / WSL2 / macOS

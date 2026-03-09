# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- i18n localization with Japanese and English language support

## [0.1.0] - 2026-03-04

### Added

- Camera, screen, and audio capture with change-detection based triggering
- Screen burst capture with activity classification
- Real-time MJPEG live feed (~10fps) on port 3002
- Audio capture with speech-to-text transcription (Gemini-based)
- Foreground window detection and app time tracking
- Presence detection with face detection and idle activity categories
- MediaPipe pose detection with live skeleton overlay
- LLM-powered frame analysis and multi-scale summary generation (10m to 24h)
- Abstracted LLM provider layer supporting both Claude and Gemini
- Activity category normalization with DB-driven dynamic meta-categories
- Full-text search with FTS5 trigram tokenizer
- Daily report generation pipeline
- Discord/LINE notification support for daily reports
- Knowledge profile generation from accumulated data
- Chat platform integration with Discord adapter and backfill
- Daily memo feature with auto-save and LLM context injection
- Web UI with React frontend: timeline view, frame detail, summary panel, live feed
- Dashboard with focus score, pie charts, app usage, and session timeline
- Date range stats API for weekly/monthly views
- Activity session calculation API
- Search with inline layout
- Mobile responsive design with panel switching
- Scroll-based frame navigation
- Detail panel redesign with sections and image modal
- Color-coded timeline dots with auto-polling
- Settings modal with device selection dropdowns
- Device enumeration API for camera and audio
- Electron desktop app wrapper with app icon and tray support
- WSL2 bridge mode for Windows native support
- Windows native support for all capture modules
- macOS support for all capture modules
- Cross-platform camera and audio device enumeration
- Docker Compose setup for daemon and web services
- GitHub Actions release workflow with first-run setup
- Standalone binary distribution bundling uv and daemon source
- Health endpoint with poll-based live feed status
- Japanese README and bilingual getting-started guide

### Changed

- Replaced Whisper with Gemini for audio transcription
- Replaced hardcoded activity aliases with fuzzy matching
- Replaced hardcoded activity categories with DB-driven dynamic system
- Improved activity classification accuracy (prioritize physical state over screen content)
- Improved live feed performance with expand modal
- Improved audio capture quality and reliability
- Renamed product from life.ai to homelife.ai
- Renamed life/ package to daemon/ for clarity
- Refined timeline dot ring styles
- Updated global CSS variables and styles
- Changed default Gemini model to gemini-3.1-flash-lite-preview

### Fixed

- Gemini response parsing for NoneType parts
- Gemini 2.5 thinking token filtering
- Custom seekable audio player replacing native controls
- Local timezone handling for dates with header clock
- Session timeline rendering in Dashboard
- Rich markup error in notify-test CLI output
- FrameViewer image loading and tab reset on frame switch
- Summary cascade prevention on daemon startup
- LiveFeed fallback and context-aware analysis
- Time context in summary prompts to prevent duration hallucination
- Screen capture encoding
- Electron-builder arch flag syntax
- App icon resized to 512x512 for electron-builder Mac builds
- Daemon process restart on unexpected stop
- Sounddevice device selection on Mac and Windows

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from life.storage.database import Database
from life.storage.models import Frame, Summary

log = logging.getLogger(__name__)

CLAUDE_CMD = "claude"


def _load_context(data_dir: Path) -> str:
    """Load user context from data/context.md if it exists."""
    ctx_path = data_dir / "context.md"
    if not ctx_path.exists():
        return ""
    try:
        return ctx_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _find_claude() -> str | None:
    return shutil.which(CLAUDE_CMD)


def _clean_env() -> dict[str, str]:
    """Remove Claude Code session markers so subprocess doesn't think it's nested."""
    env = os.environ.copy()
    for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        env.pop(key, None)
    return env


def _call_claude(prompt: str, timeout: int = 120, model: str = "haiku") -> str | None:
    claude = _find_claude()
    if not claude:
        log.error("claude CLI not found in PATH")
        return None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as out_f, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as err_f:
            out_path, err_path = out_f.name, err_f.name

        result = subprocess.run(
            [claude, "-p", prompt, "--model", model],
            stdin=subprocess.DEVNULL,
            stdout=open(out_path, "w"),
            stderr=open(err_path, "w"),
            timeout=timeout,
            env=_clean_env(),
        )

        stdout = Path(out_path).read_text().strip()
        stderr = Path(err_path).read_text().strip()
        Path(out_path).unlink(missing_ok=True)
        Path(err_path).unlink(missing_ok=True)

        if result.returncode != 0:
            log.warning("claude returned %d: %s", result.returncode, stderr[:200])
            return None
        return stdout if stdout else None
    except subprocess.TimeoutExpired:
        log.warning("claude timed out after %ds", timeout)
        Path(out_path).unlink(missing_ok=True)
        Path(err_path).unlink(missing_ok=True)
        return None
    except Exception:
        log.exception("Failed to call claude")
        return None


class FrameAnalyzer:
    """Calls Claude Code CLI to analyze webcam frames + screen captures."""

    def analyze(self, frame: Frame, data_dir: Path) -> str:
        cam_path = (data_dir / frame.path).resolve() if frame.path else None
        screen_path = (data_dir / frame.screen_path).resolve() if frame.screen_path else None

        has_cam = cam_path and cam_path.exists()
        has_screen = screen_path and screen_path.exists()

        if not has_cam and not has_screen:
            log.warning("No images to analyze")
            return ""

        # Load user context
        context = _load_context(data_dir)
        parts = []

        if context:
            parts.append(
                f"あなたは継続的なライフログ記録システムです。以下はユーザーの背景情報です:\n"
                f"---\n{context}\n---\n"
                f"この情報を踏まえて、人物を名前で呼び、継続的な観察として記述してください。\n"
            )

        # Build image instructions
        if has_cam and has_screen:
            parts.append(
                f"以下の2つの画像を読んで、この人が今何をしているか1-2文で日本語で説明してください。\n"
                f"1. ウェブカメラ映像: {cam_path}\n"
                f"2. PC画面キャプチャ: {screen_path}\n"
                f"ウェブカメラからは人物の物理的な状態を、画面キャプチャからはPC上での活動内容を読み取ってください。"
            )
        elif has_cam:
            parts.append(
                f"画像ファイル {cam_path} を読んで、ウェブカメラに写っているものを"
                f"1-2文で簡潔に日本語で説明してください。"
            )
        else:
            parts.append(
                f"画像ファイル {screen_path} を読んで、PC画面に表示されている内容を"
                f"1-2文で簡潔に日本語で説明してください。"
            )

        # Add transcription context if available
        if frame.transcription:
            parts.append(
                f"\nまた、この30秒間に以下の音声が録音されています:\n"
                f"「{frame.transcription}」\n"
                f"映像と音声の両方を踏まえて説明してください。"
            )

        parts.append("説明だけを出力してください。")

        prompt = "\n".join(parts)
        result = _call_claude(prompt)
        return result or ""


class SummaryGenerator:
    """Generates multi-scale summaries by aggregating frame descriptions and lower-level summaries."""

    def __init__(self, db: Database, data_dir: Path):
        self._db = db
        self._data_dir = data_dir
        self._context = _load_context(data_dir)

    def _context_prefix(self) -> str:
        """Return context preamble for summary prompts."""
        if not self._context:
            return ""
        return (
            f"あなたは継続的なライフログ記録システムです。以下はユーザーの背景情報です:\n"
            f"---\n{self._context}\n---\n"
            f"人物を名前で呼び、継続的な観察として記述してください。\n\n"
        )

    def _time_context(self, now: datetime, subs_or_frames: list) -> str:
        """Build time context string from actual data timestamps."""
        if not subs_or_frames:
            return f"現在時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        first = subs_or_frames[0]
        last = subs_or_frames[-1]
        t_first = first.timestamp if hasattr(first, "timestamp") else first.start_time
        t_last = last.timestamp if hasattr(last, "timestamp") else last.start_time
        actual_minutes = (t_last - t_first).total_seconds() / 60
        return (
            f"現在時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"データ範囲: {t_first.strftime('%H:%M:%S')} ～ {t_last.strftime('%H:%M:%S')} "
            f"(実際の観測時間: 約{actual_minutes:.0f}分, {len(subs_or_frames)}件)\n"
        )

    _GROUND_RULE = "重要: 実際のデータ範囲・件数に基づいてのみ記述してください。スケール名から時間を推測して水増ししないこと。\n\n"

    def generate_10m(self, now: datetime) -> Summary | None:
        """10-minute summary from recent frame descriptions."""
        since = now - timedelta(minutes=10)
        frames = self._db.get_frames_since(since)
        if not frames:
            return None

        ctx = self._time_context(now, frames)
        descriptions = self._format_frame_list(frames)
        prompt = (
            f"{self._context_prefix()}"
            f"{self._GROUND_RULE}"
            f"{ctx}\n"
            f"以下はウェブカメラ+画面キャプチャの観察記録です。\n\n"
            f"{descriptions}\n\n"
            f"この期間の活動を2-3文で日本語で要約してください。要約だけを出力してください。"
        )
        content = _call_claude(prompt)
        if not content:
            return None

        summary = Summary(
            timestamp=now, scale="10m", content=content, frame_count=len(frames)
        )
        summary.id = self._db.insert_summary(summary)
        return summary

    def generate_30m(self, now: datetime) -> Summary | None:
        since = now - timedelta(minutes=30)
        subs = self._db.get_summaries_since(since, "10m")
        if not subs:
            return None
        return self._aggregate(now, "30m", subs)

    def generate_1h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=1)
        subs = self._db.get_summaries_since(since, "30m")
        if not subs:
            return None
        return self._aggregate(now, "1h", subs)

    def generate_6h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=6)
        subs = self._db.get_summaries_since(since, "1h")
        if not subs:
            return None
        return self._aggregate(now, "6h", subs)

    def generate_12h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=12)
        subs = self._db.get_summaries_since(since, "6h")
        if not subs:
            return None
        return self._aggregate(now, "12h", subs)

    def generate_24h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=24)
        subs = self._db.get_summaries_since(since, "12h")
        if not subs:
            return None

        frames = self._db.get_frames_since(since)
        keyframes = self._select_keyframes(frames, max_frames=10)
        keyframe_section = ""
        if keyframes:
            paths = [str((self._data_dir / f.path).resolve()) for f in keyframes if (self._data_dir / f.path).exists()]
            if paths:
                keyframe_section = (
                    "\n\nまた、以下のキーフレーム画像も参照してください:\n"
                    + "\n".join(f"- {p}" for p in paths)
                )

        ctx = self._time_context(now, subs)
        sub_text = self._format_summaries(subs)
        prompt = (
            f"{self._context_prefix()}"
            f"{self._GROUND_RULE}"
            f"{ctx}\n"
            f"以下はこの期間の活動サマリーです。\n\n"
            f"{sub_text}"
            f"{keyframe_section}\n\n"
            f"上記のデータ範囲に基づいて、生活パターンを分析し以下を日本語で出力してください:\n"
            f"1. 実際の観測時間内で何が起きたかの自然な要約\n"
            f"2. 活動パターン（集中作業の時間帯、休憩、離席など）\n"
            f"3. 気になる点や改善提案があれば\n"
        )
        content = _call_claude(prompt, timeout=180)
        if not content:
            return None

        total_frames = sum(s.frame_count for s in subs)
        summary = Summary(
            timestamp=now, scale="24h", content=content, frame_count=total_frames
        )
        summary.id = self._db.insert_summary(summary)
        return summary

    def _aggregate(
        self, now: datetime, scale: str, subs: list[Summary],
    ) -> Summary | None:
        ctx = self._time_context(now, subs)
        sub_text = self._format_summaries(subs)
        prompt = (
            f"{self._context_prefix()}"
            f"{self._GROUND_RULE}"
            f"{ctx}\n"
            f"以下はこの期間の活動記録です。\n\n"
            f"{sub_text}\n\n"
            f"上記のデータ範囲に基づいて、活動パターンを2-3文で日本語で要約してください。"
            f"要約だけを出力してください。"
        )
        content = _call_claude(prompt)
        if not content:
            return None

        total_frames = sum(s.frame_count for s in subs)
        summary = Summary(
            timestamp=now, scale=scale, content=content, frame_count=total_frames
        )
        summary.id = self._db.insert_summary(summary)
        return summary

    @staticmethod
    def _format_frame_list(frames: list[Frame]) -> str:
        lines = []
        for f in frames:
            desc = f.claude_description or "(未分析)"
            line = (
                f"[{f.timestamp.strftime('%H:%M:%S')}] "
                f"明るさ={f.brightness:.0f} 動き={f.motion_score:.3f} "
                f"| {desc}"
            )
            if f.transcription:
                line += f"\n  🎤 音声: 「{f.transcription}」"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_summaries(summaries: list[Summary]) -> str:
        lines = []
        for s in summaries:
            lines.append(f"[{s.timestamp.strftime('%H:%M')}] ({s.scale}, {s.frame_count}フレーム): {s.content}")
        return "\n".join(lines)

    @staticmethod
    def _select_keyframes(frames: list[Frame], max_frames: int = 10) -> list[Frame]:
        if len(frames) <= max_frames:
            return frames
        step = len(frames) // max_frames
        return [frames[i] for i in range(0, len(frames), step)][:max_frames]

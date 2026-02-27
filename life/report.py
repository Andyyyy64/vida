"""Daily report generation — diary-style summaries of each day."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from life.activity import get_meta_category
from life.llm.base import LLMProvider
from life.storage.database import Database
from life.storage.models import Report

log = logging.getLogger(__name__)


def _load_context(data_dir: Path) -> str:
    ctx_path = data_dir / "context.md"
    if not ctx_path.exists():
        return ""
    try:
        return ctx_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


class ReportGenerator:
    """Generates daily diary-style reports."""

    def __init__(self, provider: LLMProvider, db: Database, data_dir: Path):
        self._provider = provider
        self._db = db
        self._data_dir = data_dir
        self._context = _load_context(data_dir)

    def generate(self, target_date: date) -> Report | None:
        """Generate a daily report for the given date."""
        frames = self._db.get_frames_for_date(target_date)
        if not frames:
            log.info("No frames for %s, skipping report", target_date)
            return None

        summaries = self._db.get_summaries_for_date(target_date)
        events = self._db.get_events_for_date(target_date)

        # Calculate focus percentage (exclude idle frames from denominator)
        focus_frames = sum(
            1 for f in frames
            if f.activity and get_meta_category(f.activity) == "focus"
        )
        active_frames = sum(
            1 for f in frames
            if not f.activity or get_meta_category(f.activity) != "idle"
        )
        focus_pct = (focus_frames / active_frames * 100) if active_frames else 0

        # Build activity breakdown
        activity_counts: dict[str, int] = {}
        for f in frames:
            if f.activity:
                activity_counts[f.activity] = activity_counts.get(f.activity, 0) + 1

        activity_lines = []
        for act, count in sorted(activity_counts.items(), key=lambda x: -x[1]):
            minutes = count * 30 // 60  # rough estimate
            meta = get_meta_category(act)
            activity_lines.append(f"- {act}: ~{minutes}分 [{meta}]")
        activity_summary = "\n".join(activity_lines)

        # Collect hourly summaries
        hourly_sums = [s for s in summaries if s.scale in ("1h", "30m")]
        hourly_sums.sort(key=lambda s: s.timestamp)
        summary_text = "\n".join(
            f"[{s.timestamp.strftime('%H:%M')}] {s.content}" for s in hourly_sums
        )

        # Event summary
        event_text = ""
        if events:
            event_text = "\n".join(
                f"[{e.timestamp.strftime('%H:%M')}] {e.event_type}: {e.description}"
                for e in events
            )

        # Build prompt for diary-style report
        context_prefix = ""
        if self._context:
            context_prefix = (
                f"ユーザー背景情報:\n---\n{self._context}\n---\n\n"
            )

        prompt = (
            f"{context_prefix}"
            f"以下は {target_date.isoformat()} の1日の記録です。\n\n"
            f"## アクティビティ内訳\n{activity_summary}\n\n"
            f"## 時系列サマリー\n{summary_text}\n\n"
        )
        if event_text:
            prompt += f"## イベント\n{event_text}\n\n"

        prompt += (
            f"フレーム数: {len(frames)}, 集中率: {focus_pct:.0f}%\n\n"
            "上記の記録に基づいて、この日の日記を書いてください。\n"
            "ルール:\n"
            "- 2-3段落の読みやすい日本語で書くこと\n"
            "- 事実に基づき、データにない内容を創作しないこと\n"
            "- 人物は名前で呼ぶこと\n"
            "- 1日の流れ、主な活動、印象的だった出来事を含めること\n"
            "- 最後に短い振り返り（良かった点や改善点）を添えること\n"
            "- タイトルや日付は不要。本文だけを出力すること\n"
        )

        content = self._provider.generate_text(prompt, timeout=120)
        if not content:
            return None

        report = Report(
            date=target_date.isoformat(),
            content=content,
            generated_at=datetime.now(),
            frame_count=len(frames),
            focus_pct=focus_pct,
        )
        report.id = self._db.insert_report(report)
        log.info("Generated daily report for %s (%d frames, %.0f%% focus)",
                 target_date, len(frames), focus_pct)
        return report

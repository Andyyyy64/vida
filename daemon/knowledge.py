"""Knowledge profile generator — distills accumulated data into a structured profile."""

from __future__ import annotations

import logging
from pathlib import Path

from daemon.llm.base import LLMProvider
from daemon.storage.database import Database

log = logging.getLogger(__name__)


class KnowledgeGenerator:
    """Generates a knowledge profile by distilling all accumulated data via LLM."""

    def __init__(self, provider: LLMProvider, db: Database, data_dir: Path):
        self._provider = provider
        self._db = db
        self._data_dir = data_dir

    def generate(self) -> str | None:
        """Collect data from all sources, build a prompt, and generate a knowledge profile.

        Returns the generated knowledge content, or None if generation fails.
        """
        sections: list[str] = []

        # 1. Chat channel stats + samples
        chat_section = self._build_chat_section()
        if chat_section:
            sections.append(chat_section)

        # 2. Recent daily summaries (24h scale)
        summary_section = self._build_summary_section()
        if summary_section:
            sections.append(summary_section)

        # 3. Recent reports
        report_section = self._build_report_section()
        if report_section:
            sections.append(report_section)

        # 4. Recent memos
        memo_section = self._build_memo_section()
        if memo_section:
            sections.append(memo_section)

        # 5. Activity stats (top activities + meta-category)
        activity_section = self._build_activity_section()
        if activity_section:
            sections.append(activity_section)

        # 6. Hourly activity distribution
        hourly_section = self._build_hourly_section()
        if hourly_section:
            sections.append(hourly_section)

        if not sections:
            log.info("No data available for knowledge generation")
            return None

        data_block = "\n\n".join(sections)

        prompt = (
            "あなたはライフログ分析AIです。以下はユーザーの蓄積データ（チャット、行動記録、メモなど）です。\n"
            "このデータから「知識プロファイル」を生成してください。\n\n"
            "## 入力データ\n\n"
            f"{data_block}\n\n"
            "## 出力フォーマット\n\n"
            "以下のセクションで構造化された知識プロファイルを日本語で出力してください。\n"
            "データに該当がないセクションは省略してください。\n\n"
            "### 人間関係\n"
            "- 名前: 関係性、主な交流チャンネル、頻度\n\n"
            "### 進行中のプロジェクト・話題\n"
            "- プロジェクト名や話題（関連する人物、チャンネル）\n\n"
            "### 行動パターン\n"
            "- 時間帯ごとの傾向（午前、午後、夜など）\n\n"
            "### よく使うツール\n"
            "- ツール名: 用途、使用頻度\n\n"
            "### その他の特徴\n"
            "- 上記に収まらない特筆事項\n\n"
            "ルール:\n"
            "- データに基づいた事実のみを記述すること\n"
            "- 推測や創作は禁止\n"
            "- 簡潔に、箇条書きで\n"
            "- セクションヘッダーは「## 」で始めること\n"
        )

        log.info("Generating knowledge profile...")
        content = self._provider.generate_text(prompt, timeout=180)
        if not content:
            log.warning("Knowledge generation returned empty result")
            return None

        # Build source summary for metadata
        source_parts = []
        chat_stats = self._db.get_chat_channel_stats(limit=5)
        if chat_stats:
            total_msgs = sum(s["msg_count"] for s in chat_stats)
            source_parts.append(f"chat:{total_msgs}msgs")
        reports = self._db.get_reports(limit=7)
        if reports:
            source_parts.append(f"reports:{len(reports)}")
        memos = self._db.get_recent_memos(limit=14)
        if memos:
            source_parts.append(f"memos:{len(memos)}")
        source_summary = ", ".join(source_parts)

        self._db.insert_knowledge(content, source_summary, period_days=14)
        log.info("Knowledge profile generated and saved (%d chars)", len(content))
        return content

    def _build_chat_section(self) -> str:
        """Build chat data section: channel stats + message samples."""
        stats = self._db.get_chat_channel_stats(limit=15)
        if not stats:
            return ""

        lines = ["## チャットデータ\n", "### チャンネル別統計"]
        for s in stats:
            guild = f"{s['guild_name']}/" if s["guild_name"] else ""
            lines.append(
                f"- {s['platform']}/{guild}{s['channel_name']}: "
                f"{s['msg_count']}件, {s['author_count']}人, "
                f"最終: {s['last_active']}"
            )

        # Sample messages from top channels
        lines.append("\n### 主要チャンネルの最新メッセージサンプル")
        for s in stats[:5]:
            if not s["channel_name"]:
                continue
            msgs = self._db.get_chat_samples_by_channel(s["channel_name"], limit=8)
            if not msgs:
                continue
            guild = f"{s['guild_name']}/" if s["guild_name"] else ""
            lines.append(f"\n**{s['platform']}/{guild}{s['channel_name']}**:")
            for m in msgs:
                sender = "自分" if m.is_self else m.author_name
                ts = m.timestamp.strftime("%m/%d %H:%M")
                content = m.content[:150]
                lines.append(f"  [{ts}] {sender}: {content}")

        return "\n".join(lines)

    def _build_summary_section(self) -> str:
        """Build section from recent 24h summaries."""
        summaries = self._db.get_recent_summaries_by_scale("24h", limit=7)
        if not summaries:
            return ""

        lines = ["## 直近の日次サマリー"]
        for s in summaries:
            d = s.timestamp.strftime("%Y-%m-%d")
            lines.append(f"\n**{d}** ({s.frame_count}フレーム):")
            lines.append(s.content[:500])

        return "\n".join(lines)

    def _build_report_section(self) -> str:
        """Build section from recent daily reports."""
        reports = self._db.get_reports(limit=5)
        if not reports:
            return ""

        lines = ["## 直近の日次レポート"]
        for r in reports:
            lines.append(f"\n**{r.date}** (集中率{r.focus_pct:.0f}%):")
            lines.append(r.content[:500])

        return "\n".join(lines)

    def _build_memo_section(self) -> str:
        """Build section from recent memos."""
        memos = self._db.get_recent_memos(limit=14)
        if not memos:
            return ""

        lines = ["## ユーザーメモ"]
        for m in memos:
            lines.append(f"- {m['date']}: {m['content'][:200]}")

        return "\n".join(lines)

    def _build_activity_section(self) -> str:
        """Build section from activity mappings (top activities)."""
        mappings = self._db.get_all_activity_mappings()
        if not mappings:
            return ""

        lines = ["## アクティビティ頻度 (上位)"]
        for m in mappings[:15]:
            lines.append(f"- {m['activity']}: {m['frame_count']}回 [{m['meta_category']}]")

        return "\n".join(lines)

    def _build_hourly_section(self) -> str:
        """Build section from hourly activity distribution."""
        dist = self._db.get_hourly_activity_distribution(days=14)
        if not dist:
            return ""

        # Group by hour, pick top activity per hour
        by_hour: dict[int, list[dict]] = {}
        for d in dist:
            by_hour.setdefault(d["hour"], []).append(d)

        lines = ["## 時間帯別アクティビティ傾向 (過去2週間)"]
        for hour in sorted(by_hour.keys()):
            activities = by_hour[hour]
            top = activities[:3]
            top_str = ", ".join(f"{a['activity']}({a['cnt']})" for a in top)
            lines.append(f"- {hour:02d}時: {top_str}")

        return "\n".join(lines)

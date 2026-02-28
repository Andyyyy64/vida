from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from datetime import date as date_type

from daemon.activity import ActivityManager
from daemon.llm.base import LLMProvider
from daemon.storage.database import Database
from daemon.storage.models import Frame, Summary

log = logging.getLogger(__name__)


def _load_context(data_dir: Path) -> str:
    """Load user context from data/context.md if it exists."""
    ctx_path = data_dir / "context.md"
    if not ctx_path.exists():
        return ""
    try:
        return ctx_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


class FrameAnalyzer:
    """Analyzes webcam frames + screen captures via an LLM provider."""

    def __init__(self, provider: LLMProvider, data_dir: Path, db: Database, activity_mgr: ActivityManager):
        self._provider = provider
        self._data_dir = data_dir
        self._db = db
        self._activity_mgr = activity_mgr

    def analyze(
        self,
        frame: Frame,
        extra_screen_paths: list[str] | None = None,
        extra_cam_paths: list[str] | None = None,
        has_face: bool | None = None,
    ) -> tuple[str, str]:
        """Analyze frame and return (description, activity).

        Args:
            frame: Frame to analyze (with path, screen_path, etc.)
            extra_screen_paths: Change-detected extra screen captures
            extra_cam_paths: Change-detected extra camera captures
            has_face: Face detection result (True/False/None if disabled)

        Returns:
            Tuple of (description, activity_category)
        """
        cam_path = (self._data_dir / frame.path).resolve() if frame.path else None
        screen_path = (self._data_dir / frame.screen_path).resolve() if frame.screen_path else None

        has_cam = cam_path and cam_path.exists()
        has_screen = screen_path and screen_path.exists()

        if not has_cam and not has_screen:
            log.warning("No images to analyze")
            return "", ""

        # Resolve extra paths
        extra_screens: list[Path] = []
        if extra_screen_paths:
            for sp in extra_screen_paths:
                p = (self._data_dir / sp).resolve()
                if p.exists():
                    extra_screens.append(p)

        extra_cams: list[Path] = []
        if extra_cam_paths:
            for cp in extra_cam_paths:
                p = (self._data_dir / cp).resolve()
                if p.exists():
                    extra_cams.append(p)

        context = _load_context(self._data_dir)
        parts: list[str] = []

        if context:
            parts.append(
                "あなたは継続的なライフログ記録システムです。以下はユーザーの背景情報です:\n"
                f"---\n{context}\n---\n"
                "この情報を踏まえて、人物を名前で呼び、継続的な観察として記述してください。\n"
            )

        # Inject today's memo if available
        today_memo = self._db.get_memo(date_type.today())
        if today_memo:
            parts.append(
                "【今日のメモ】ユーザーが記入した本日のメモ:\n"
                f"「{today_memo}」\n"
                "※参考情報として活用してください。\n"
            )

        # Recent context: pass last few frame analyses for continuity
        recent = self._db.get_recent_frames(limit=5)
        if recent:
            lines = []
            for rf in recent:
                if rf.claude_description:
                    ts = rf.timestamp.strftime("%H:%M:%S")
                    act = rf.activity or "?"
                    lines.append(f"  [{ts}] {act}: {rf.claude_description}")
            if lines:
                parts.append(
                    "【直近の観察記録】（時系列の連続性を踏まえて分析してください）\n"
                    + "\n".join(lines) + "\n"
                )

        # Build image list and prompt
        image_paths: list[Path] = []
        img_idx = 1

        # Camera images (main + change-detected)
        cam_labels: list[str] = []
        if has_cam:
            image_paths.append(cam_path)
            cam_labels.append(f"画像{img_idx}: ウェブカメラ（メイン）")
            img_idx += 1
        for i, ecp in enumerate(extra_cams):
            image_paths.append(ecp)
            cam_labels.append(f"画像{img_idx}: ウェブカメラ（変化検出{i+1}）")
            img_idx += 1
        cam_desc = "\n".join(cam_labels) if cam_labels else ""

        # Screen images (main + change-detected)
        screen_labels: list[str] = []
        if has_screen:
            image_paths.append(screen_path)
            screen_labels.append(f"画像{img_idx}: PC画面（メイン）")
            img_idx += 1
        for i, esp in enumerate(extra_screens):
            image_paths.append(esp)
            screen_labels.append(f"画像{img_idx}: PC画面（変化検出{i+1}）")
            img_idx += 1
        screen_desc = "\n".join(screen_labels) if screen_labels else ""

        total_images = len(image_paths)
        if total_images == 0:
            return "", ""

        parts.append(f"以下の{total_images}つの画像を分析してください。")
        if cam_desc:
            parts.append(cam_desc)
        if screen_desc:
            parts.append(screen_desc)

        change_note = ""
        if extra_screens or extra_cams:
            change_note = (
                "「変化検出」の画像は、この30秒間に画面やカメラに大きな変化があった瞬間のスナップショットです。"
                "変化が多いほど、活動が活発だったことを意味します。"
                "時系列で変化を読み取り、この期間中の活動を把握してください。"
            )
            parts.append(change_note)

        if (has_cam or extra_cams) and (has_screen or extra_screens):
            parts.append(
                "ウェブカメラからは人物の物理的な状態を、画面キャプチャからはPC上での活動内容を読み取り、"
                "この人が今何をしているか1-2文で日本語で説明してください。"
            )
        elif has_cam or extra_cams:
            parts.append(
                "写っているものを1-2文で簡潔に日本語で説明してください。"
            )
        else:
            parts.append(
                "表示されている内容を1-2文で簡潔に日本語で説明してください。"
            )

        # Foreground window info
        if frame.foreground_window:
            fw_proc, _, fw_title = frame.foreground_window.partition("|")
            if fw_proc:
                parts.append(
                    f"\n【アクティブウィンドウ】プロセス: {fw_proc} | タイトル: {fw_title}\n"
                    "この情報も踏まえてアクティビティを判定してください。"
                )

        if frame.transcription:
            parts.append(
                f"\nまた、この30秒間に以下の音声が録音されています:\n"
                f"「{frame.transcription}」\n"
                "映像と音声の両方を踏まえて説明してください。"
            )

        # Presence detection hint
        if has_face is not None:
            if has_face:
                parts.append(
                    "\n【センサー情報】顔検出: 人物の存在を確認しました。"
                )
            else:
                parts.append(
                    "\n【センサー情報】顔検出: 人物は検出されませんでした。"
                    "ただし画面上でアクティブな操作（コード編集、ブラウジングなど）が確認できる場合は、"
                    "カメラの画角外にいるだけなので、画面の内容に基づいて活動を分類してください。"
                    "画面にも変化がない場合のみ「睡眠」または「不在」と分類してください。"
                )

        # Activity classification with dynamic examples
        frequent = self._activity_mgr.get_frequent(limit=15)

        if frequent:
            examples = "、".join(frequent)
            parts.append(
                f"\n【アクティビティ分類】\n"
                f"これまでに使用されたカテゴリ: {examples}\n"
                "上記のカテゴリに当てはまる場合はそのまま使ってください。\n"
                "当てはまらない場合は、簡潔な日本語で新しいカテゴリ名を付けてください。\n"
                "複数の活動が同時に行われている場合は、メインの活動を1つだけ選んでください。"
            )
        else:
            parts.append(
                "\n【アクティビティ分類】\n"
                "この人の活動を簡潔な日本語カテゴリ名で表してください（例: プログラミング、休憩、ブラウジング）。"
            )

        parts.append(
            '\n以下のJSON形式で出力してください（JSON以外は出力しないこと）:\n'
            '{"activity": "カテゴリ名", "meta_category": "focus|communication|entertainment|browsing|break|idle", "description": "説明文"}\n'
            "meta_categoryは上記6つのいずれか1つを選んでください。\n"
        )

        prompt = "\n".join(parts)
        raw = self._provider.analyze_images(prompt, image_paths)
        desc, activity, meta = self._parse_analysis(raw or "")

        # Normalize and register via ActivityManager
        if activity:
            activity, _ = self._activity_mgr.normalize_and_register(activity, meta)

        return desc, activity

    @staticmethod
    def _parse_analysis(raw: str) -> tuple[str, str, str]:
        """Parse JSON analysis response. Returns (description, activity, meta_category)."""
        raw = raw.strip()
        if not raw:
            return "", "", "other"

        # Try to extract JSON from the response
        # Handle cases where LLM wraps JSON in markdown code blocks
        if "```" in raw:
            lines = raw.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            if json_lines:
                raw = "\n".join(json_lines).strip()

        def _extract(data: dict) -> tuple[str, str, str]:
            desc = data.get("description", "")
            act = data.get("activity", "")
            meta = data.get("meta_category", "other")
            return desc, act, meta

        try:
            return _extract(json.loads(raw))
        except json.JSONDecodeError:
            pass

        # Fallback: try to find JSON object in the text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return _extract(json.loads(raw[start:end]))
            except json.JSONDecodeError:
                pass

        # Final fallback: treat entire text as description
        log.warning("Could not parse JSON from analysis, using raw text")
        return raw, "", "other"


class SummaryGenerator:
    """Generates multi-scale summaries by aggregating frame descriptions."""

    def __init__(self, provider: LLMProvider, db: Database, data_dir: Path):
        self._provider = provider
        self._db = db
        self._data_dir = data_dir
        self._context = _load_context(data_dir)

    def _context_prefix(self) -> str:
        parts: list[str] = []
        if self._context:
            parts.append(
                "あなたは継続的なライフログ記録システムです。以下はユーザーの背景情報です:\n"
                f"---\n{self._context}\n---\n"
                "人物を名前で呼び、継続的な観察として記述してください。\n"
            )
        today_memo = self._db.get_memo(date_type.today())
        if today_memo:
            parts.append(
                "【今日のメモ】ユーザーが記入した本日のメモ:\n"
                f"「{today_memo}」\n"
                "※参考情報として活用してください。\n"
            )
        return "\n".join(parts) + ("\n" if parts else "")

    def _time_context(self, now: datetime, subs_or_frames: list) -> str:
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

    _GROUND_RULE = (
        "重要なルール:\n"
        "- 提供されたデータに書かれている内容だけを要約してください\n"
        "- データに存在しない会話内容・話題・行動を絶対に創作しないでください\n"
        "- 音声の内容はそのまま引用するか、正確に言い換えてください\n"
        "- スケール名から時間を推測して水増ししないこと\n"
        "- 「夜遅い」「朝早い」など時間帯の印象を勝手に付けないこと\n\n"
    )

    def generate_10m(self, now: datetime) -> Summary | None:
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
            "以下はウェブカメラ+画面キャプチャの観察記録です。\n\n"
            f"{descriptions}\n\n"
            "上記の記録だけに基づいて、この期間の活動を2-3文で日本語で要約してください。"
            "記録にない内容を追加しないでください。要約だけを出力してください。"
        )
        content = self._provider.generate_text(prompt)
        if not content:
            return None

        summary = Summary(
            timestamp=now, scale="10m", content=content, frame_count=len(frames),
        )
        summary.id = self._db.insert_summary(summary)
        return summary

    def generate_30m(self, now: datetime) -> Summary | None:
        since = now - timedelta(minutes=30)
        subs = self._db.get_summaries_since(since, "10m")
        if not subs:
            return None
        return self._aggregate(now, "30m", subs, since)

    def generate_1h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=1)
        subs = self._db.get_summaries_since(since, "30m")
        if not subs:
            return None
        return self._aggregate(now, "1h", subs, since)

    def generate_6h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=6)
        subs = self._db.get_summaries_since(since, "1h")
        if not subs:
            return None
        return self._aggregate(now, "6h", subs, since)

    def generate_12h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=12)
        subs = self._db.get_summaries_since(since, "6h")
        if not subs:
            return None
        return self._aggregate(now, "12h", subs, since)

    def generate_24h(self, now: datetime) -> Summary | None:
        since = now - timedelta(hours=24)
        subs = self._db.get_summaries_since(since, "12h")
        if not subs:
            return None

        # 24h summary includes keyframe images
        frames = self._db.get_frames_since(since)
        keyframes = self._select_keyframes(frames, max_frames=10)
        image_paths: list[Path] = []
        if keyframes:
            for f in keyframes:
                p = self._data_dir / f.path
                if p.exists():
                    image_paths.append(p.resolve())

        # Collect transcriptions
        transcriptions = self._collect_transcriptions(since)
        audio_section = ""
        if transcriptions:
            audio_section = (
                "\n## この期間の音声書き起こし（原文）\n"
                f"{transcriptions}\n\n"
                "上記の音声内容も踏まえて分析してください。\n"
            )

        ctx = self._time_context(now, subs)
        sub_text = self._format_summaries(subs)
        prompt = (
            f"{self._context_prefix()}"
            f"{self._GROUND_RULE}"
            f"{ctx}\n"
            "以下はこの期間の活動サマリーです。\n\n"
            f"{sub_text}\n\n"
            f"{audio_section}"
            "上記のデータ範囲に基づいて、生活パターンを分析し以下を日本語で出力してください:\n"
            "1. 実際の観測時間内で何が起きたかの自然な要約\n"
            "2. 活動パターン（集中作業の時間帯、休憩、離席など）\n"
            "3. 気になる点や改善提案があれば\n"
        )

        if image_paths:
            content = self._provider.analyze_images(prompt, image_paths, timeout=180)
        else:
            content = self._provider.generate_text(prompt, timeout=180)

        if not content:
            return None

        total_frames = sum(s.frame_count for s in subs)
        summary = Summary(
            timestamp=now, scale="24h", content=content, frame_count=total_frames,
        )
        summary.id = self._db.insert_summary(summary)
        return summary

    def _collect_transcriptions(self, since: datetime) -> str:
        """Collect all transcriptions from frames in the time range."""
        frames = self._db.get_frames_since(since)
        lines = []
        for f in frames:
            if f.transcription:
                ts = f.timestamp.strftime("%H:%M:%S")
                lines.append(f"  [{ts}] 「{f.transcription}」")
        return "\n".join(lines)

    def _aggregate(
        self, now: datetime, scale: str, subs: list[Summary],
        since: datetime | None = None,
    ) -> Summary | None:
        ctx = self._time_context(now, subs)
        sub_text = self._format_summaries(subs)

        # Collect raw transcriptions from this time range
        audio_section = ""
        if since:
            transcriptions = self._collect_transcriptions(since)
            if transcriptions:
                audio_section = (
                    "\n## この期間の音声書き起こし（原文）\n"
                    f"{transcriptions}\n\n"
                    "上記の音声内容も踏まえて要約してください。"
                    "音声の内容はそのまま引用するか、正確に言い換えてください。\n"
                )

        prompt = (
            f"{self._context_prefix()}"
            f"{self._GROUND_RULE}"
            f"{ctx}\n"
            "以下はこの期間の活動記録です。\n\n"
            f"{sub_text}\n\n"
            f"{audio_section}"
            "上記の記録だけに基づいて、活動パターンを2-3文で日本語で要約してください。"
            "記録にない会話内容や行動を創作しないでください。要約だけを出力してください。"
        )
        content = self._provider.generate_text(prompt)
        if not content:
            return None

        total_frames = sum(s.frame_count for s in subs)
        summary = Summary(
            timestamp=now, scale=scale, content=content, frame_count=total_frames,
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
                line += f"\n  音声: 「{f.transcription}」"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_summaries(summaries: list[Summary]) -> str:
        lines = []
        for s in summaries:
            lines.append(
                f"[{s.timestamp.strftime('%H:%M')}] ({s.scale}, {s.frame_count}フレーム): {s.content}"
            )
        return "\n".join(lines)

    @staticmethod
    def _select_keyframes(frames: list[Frame], max_frames: int = 10) -> list[Frame]:
        if len(frames) <= max_frames:
            return frames
        step = len(frames) // max_frames
        return [frames[i] for i in range(0, len(frames), step)][:max_frames]

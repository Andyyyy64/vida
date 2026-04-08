from __future__ import annotations

import json
import logging
from datetime import date, datetime

from daemon.config import Config
from daemon.embedding import Embedder
from daemon.llm import create_provider
from daemon.llm.base import LLMProvider
from daemon.storage.database import Database

log = logging.getLogger(__name__)

# System prompt for the RAG chat
SYSTEM_PROMPT = """あなたはvidaのアシスタントです。ユーザーの日常生活を記録・分析するシステムのデータにアクセスできます。

以下のコンテキストはユーザーの生活記録データです（フレーム分析、チャットメッセージ、サマリーなど）。
このデータをもとに、ユーザーの質問に自然な日本語で答えてください。

ルール:
- データに基づいて正確に答える。推測する場合は「おそらく」「〜かもしれません」と明示する
- 時間や日付は具体的に答える
- フレンドリーだが簡潔に
- データがない場合は正直に「その期間のデータがありません」と答える
"""

DATE_EXTRACTION_PROMPT = """\
今日は {today} です。

ユーザーの質問から、データを検索すべき日付をすべて抽出してください。
相対的な表現（今日、昨日、3日前、先週の月曜、など）は具体的な日付に変換してください。
日付が含まれない質問の場合は空配列を返してください。

JSON配列のみを返してください。他のテキストは不要です。
フォーマット: ["YYYY-MM-DD", ...]

質問: {query}"""


def _extract_dates_with_llm(provider: LLMProvider, query: str) -> list[date]:
    """Use LLM to extract dates from a query string."""
    today = date.today()
    prompt = DATE_EXTRACTION_PROMPT.format(today=today.isoformat(), query=query)

    try:
        response = provider.generate_text(prompt)
        if not response:
            return []
        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        dates_raw = json.loads(text)
        if not isinstance(dates_raw, list):
            return []
        dates: list[date] = []
        for d in dates_raw:
            try:
                dates.append(date.fromisoformat(d))
            except (ValueError, TypeError):
                continue
        return list(dict.fromkeys(dates))  # dedupe preserving order
    except Exception:
        log.exception("LLM date extraction failed for query: %s", query)
        return []


class RagEngine:
    """RAG (Retrieval Augmented Generation) engine for life data chat."""

    def __init__(self, config: Config):
        self._config = config
        self._db = Database(config.db_path, embedding_dimensions=config.embedding.dimensions)
        self._embedder = Embedder(model=config.embedding.model, dimensions=config.embedding.dimensions)
        self._provider = create_provider(
            config.llm.provider,
            claude_model=config.llm.claude_model,
            gemini_model=config.llm.gemini_model,
        )

    def ask(self, query: str, history: list[dict] | None = None) -> dict:
        """Answer a question using RAG over life data."""

        # 1. Date-aware retrieval: LLM extracts dates from query
        target_dates = _extract_dates_with_llm(self._provider, query)
        date_context: list[str] = []
        date_sources: list[dict] = []

        for d in target_dates:
            ctx, src = self._fetch_date_data(d)
            date_context.extend(ctx)
            date_sources.extend(src)

        # 2. Vector search (semantic similarity)
        vec_context: list[str] = []
        vec_sources: list[dict] = []

        query_embedding = self._embedder.embed_text(query)
        if query_embedding:
            results = self._db.search_similar(query_embedding, limit=10)
            seen_keys = {(s["type"], s["timestamp"]) for s in date_sources}

            for r in results:
                key = (r["item_type"], r["timestamp"])
                if key in seen_keys:
                    continue  # skip duplicates from date retrieval
                seen_keys.add(key)

                detail = self._fetch_source_detail(r["item_type"], r["source_id"])
                if detail:
                    vec_context.append(detail)
                vec_sources.append(
                    {
                        "type": r["item_type"],
                        "timestamp": r["timestamp"],
                        "preview": r["preview"][:150] if r["preview"] else "",
                        "distance": round(r["distance"], 4),
                    }
                )

        # 3. Combine contexts
        all_context = date_context + vec_context
        all_sources = date_sources + vec_sources

        if not all_context:
            return {
                "response": "関連するデータが見つかりませんでした。",
                "sources": [],
            }

        # 4. Build prompt
        context_block = "\n\n---\n\n".join(all_context)
        now = datetime.now()

        prompt = SYSTEM_PROMPT + f"\n\n現在時刻: {now.strftime('%Y-%m-%d %H:%M')}\n"

        if target_dates:
            prompt += f"対象日付: {', '.join(d.isoformat() for d in target_dates)}\n"

        prompt += f"\n## コンテキスト\n\n{context_block}\n\n"

        if history:
            prompt += "## 会話履歴\n\n"
            for msg in history[-6:]:
                role = "ユーザー" if msg["role"] == "user" else "アシスタント"
                prompt += f"{role}: {msg['content']}\n\n"

        prompt += f"## ユーザーの質問\n\n{query}"

        # 5. Generate response
        try:
            response = self._provider.generate_text(prompt)
            if not response:
                response = "回答を生成できませんでした。もう一度お試しください。"
        except Exception:
            log.exception("RAG generation failed")
            response = "エラーが発生しました。もう一度お試しください。"

        return {
            "response": response,
            "sources": all_sources,
        }

    def _fetch_date_data(self, d: date) -> tuple[list[str], list[dict]]:
        """Fetch summaries, frames, and chat for a specific date directly from DB."""
        context: list[str] = []
        sources: list[dict] = []

        # Summaries (most informative, largest scale first)
        summaries = self._db.get_summaries_for_date(d)
        # Prefer larger scales for context
        for scale in ("24h", "12h", "6h", "1h", "30m", "10m"):
            for s in summaries:
                if s.scale == scale:
                    text = f"[{s.scale}サマリー {s.timestamp.strftime('%Y-%m-%d %H:%M')}]\n{s.content}"
                    context.append(text)
                    sources.append(
                        {
                            "type": "summary",
                            "timestamp": s.timestamp.isoformat(),
                            "preview": f"[{s.scale}] {s.content[:150]}",
                            "distance": 0,
                        }
                    )
            if len(context) >= 8:
                break

        # Key frames (sampled, with descriptions)
        frames = self._db.get_keyframes_for_date(d, max_frames=10)
        for f in frames:
            if not f.claude_description:
                continue
            parts = [f"[フレーム {f.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]"]
            parts.append(f"分析: {f.claude_description}")
            if f.activity:
                parts.append(f"アクティビティ: {f.activity}")
            if f.foreground_window:
                proc, _, title = f.foreground_window.partition("|")
                parts.append(f"アプリ: {proc} ({title})")
            context.append("\n".join(parts))
            sources.append(
                {
                    "type": "frame",
                    "timestamp": f.timestamp.isoformat(),
                    "preview": f.claude_description[:150],
                    "distance": 0,
                }
            )

        # Chat messages
        chat_msgs = self._db.get_chat_messages_for_date(d)
        if chat_msgs:
            chat_lines = []
            for msg in chat_msgs[:30]:  # cap at 30
                channel = f"{msg.guild_name}/{msg.channel_name}" if msg.guild_name else msg.channel_name
                chat_lines.append(f"{msg.timestamp.strftime('%H:%M')} [{channel}] {msg.author_name}: {msg.content}")
            context.append(f"[チャット {d.isoformat()}]\n" + "\n".join(chat_lines))
            sources.append(
                {
                    "type": "chat",
                    "timestamp": f"{d.isoformat()}T00:00:00",
                    "preview": f"{len(chat_msgs)}件のチャットメッセージ",
                    "distance": 0,
                }
            )

        return context, sources

    def _fetch_source_detail(self, item_type: str, source_id: int) -> str | None:
        """Fetch full detail for a source item to use as context."""
        try:
            if item_type == "frame":
                row = self._db._conn.execute("SELECT * FROM frames WHERE id = ?", (source_id,)).fetchone()
                if not row:
                    return None
                frame = self._db._row_to_frame(row)
                parts = [f"[フレーム {frame.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]"]
                if frame.claude_description:
                    parts.append(f"分析: {frame.claude_description}")
                if frame.activity:
                    parts.append(f"アクティビティ: {frame.activity}")
                if frame.transcription:
                    parts.append(f"音声: {frame.transcription}")
                if frame.foreground_window:
                    proc, _, title = frame.foreground_window.partition("|")
                    parts.append(f"アプリ: {proc} ({title})")
                return "\n".join(parts)

            elif item_type == "chat":
                row = self._db._conn.execute("SELECT * FROM chat_messages WHERE id = ?", (source_id,)).fetchone()
                if not row:
                    return None
                msg = self._db._row_to_chat_message(row)
                header = f"[チャット {msg.timestamp.strftime('%Y-%m-%d %H:%M')}]"
                channel = f"{msg.guild_name}/{msg.channel_name}" if msg.guild_name else msg.channel_name
                return f"{header}\n{channel} - {msg.author_name}: {msg.content}"

            elif item_type == "summary":
                row = self._db._conn.execute("SELECT * FROM summaries WHERE id = ?", (source_id,)).fetchone()
                if not row:
                    return None
                summary = self._db._row_to_summary(row)
                return f"[{summary.scale}サマリー {summary.timestamp.strftime('%Y-%m-%d %H:%M')}]\n{summary.content}"

        except Exception:
            log.exception("Failed to fetch source detail for %s/%d", item_type, source_id)
        return None

    def close(self):
        self._db.close()

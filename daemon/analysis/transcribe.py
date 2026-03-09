from __future__ import annotations

import logging
from pathlib import Path

from daemon.llm.base import LLMProvider

log = logging.getLogger(__name__)


class Transcriber:
    """Speech-to-text transcription via an LLM provider."""

    def __init__(self, provider: LLMProvider, context_path: Path | None = None):
        self._provider = provider
        self._context_path = context_path

    def _build_prompt(self) -> str:
        parts: list[str] = []

        if self._context_path and self._context_path.exists():
            try:
                ctx = self._context_path.read_text(encoding="utf-8").strip()
                if ctx:
                    parts.append(f"背景情報（人名や語彙の参考にしてください）:\n{ctx[:300]}\n")
            except Exception:
                pass

        parts.append(
            "以下の音声を正確に日本語で書き起こしてください。\n"
            "注意事項:\n"
            "- 音声が無音またはノイズのみの場合は何も出力しないでください\n"
            "- 聞こえた内容のみを記載し、推測や創作は行わないでください\n"
            "- 書き起こしテキストだけを出力してください"
        )
        return "\n".join(parts)

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text. Returns empty string on failure."""
        if not audio_path.exists():
            log.warning("Audio file not found: %s", audio_path)
            return ""

        prompt = self._build_prompt()
        text = self._provider.transcribe_audio(audio_path, prompt)

        if text:
            log.info("Transcribed: %s", text[:80])
        return text

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Common vocabulary to guide Whisper's decoding for Japanese homophones.
# Including correct kanji here makes the model prefer these over sound-alikes.
_DEFAULT_PROMPT = (
    "日常会話の書き起こし。"
    "返す、返して、返してほしい、お金を返す、借りる、貸す。"
    "帰る、帰ってくる、家に帰る。"
    "聞く、聴く、効く。買う、飼う。"
    "作る、造る、創る。計る、測る、量る。"
)


class Transcriber:
    """Speech-to-text using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "medium", language: str = "ja",
                 context_path: Path | None = None):
        self._model_size = model_size
        self._language = language
        self._model = None
        self._context_path = context_path
        self._initial_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        """Build initial_prompt from defaults + user context file."""
        parts = [_DEFAULT_PROMPT]
        if self._context_path and self._context_path.exists():
            try:
                ctx = self._context_path.read_text(encoding="utf-8").strip()
                # Extract names and key terms from context for Whisper
                if ctx:
                    # Use first 200 chars of context as vocabulary hints
                    parts.append(ctx[:200])
            except Exception:
                pass
        return " ".join(parts)

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
            log.info("Whisper model loaded: %s", self._model_size)
        except Exception:
            log.exception("Failed to load Whisper model")

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text. Returns empty string on failure."""
        if not audio_path.exists():
            log.warning("Audio file not found: %s", audio_path)
            return ""

        self._load_model()
        if self._model is None:
            return ""

        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self._language,
                vad_filter=True,
                initial_prompt=self._initial_prompt,
            )
            text = " ".join(seg.text.strip() for seg in segments)
            if text:
                log.debug("Transcribed: %s", text[:80])
            return text
        except Exception:
            log.exception("Transcription failed for %s", audio_path)
            return ""

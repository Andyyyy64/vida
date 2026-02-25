from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class Transcriber:
    """Speech-to-text using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "medium", language: str = "ja"):
        self._model_size = model_size
        self._language = language
        self._model = None

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
            )
            text = " ".join(seg.text.strip() for seg in segments)
            if text:
                log.debug("Transcribed: %s", text[:80])
            return text
        except Exception:
            log.exception("Transcription failed for %s", audio_path)
            return ""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path

from daemon.llm.base import LLMProvider, retry_on_transient_error

log = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider using Google Gemini API."""

    def __init__(self, model: str = "gemini-3.1-flash-lite-preview"):
        self._model = model
        self._client = None

    @staticmethod
    def _extract_text(resp) -> str:
        """Extract only non-thinking text from Gemini response.

        Gemini 2.5 models may include 'thought' parts (chain-of-thought)
        which should not be included in the final output.
        """
        try:
            parts = resp.candidates[0].content.parts
            text_parts = []
            for part in parts:
                if getattr(part, "thought", False):
                    continue
                if part.text:
                    text_parts.append(part.text)
            return "".join(text_parts).strip()
        except (IndexError, AttributeError, TypeError):
            # Fallback to resp.text if structure is unexpected (e.g. parts=None)
            return (resp.text or "").strip()

    def _get_client(self):
        if self._client is not None:
            return self._client

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            log.error("GEMINI_API_KEY environment variable not set")
            return None

        try:
            from google import genai

            self._client = genai.Client(api_key=api_key)
            log.info("Gemini client initialized (model=%s)", self._model)
            return self._client
        except Exception:
            log.exception("Failed to initialize Gemini client")
            return None

    def generate_text(self, prompt: str, timeout: int = 120) -> str | None:
        client = self._get_client()
        if not client:
            return None

        try:
            text = self._generate_text_with_retry(client, prompt)
            return text if text else None
        except Exception:
            log.exception("Gemini generate_text failed")
            return None

    @retry_on_transient_error
    def _generate_text_with_retry(self, client, prompt: str) -> str:
        resp = client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return self._extract_text(resp)

    def analyze_images(
        self, prompt: str, image_paths: list[Path], timeout: int = 120,
    ) -> str | None:
        client = self._get_client()
        if not client:
            return None

        try:
            parts: list[dict] = []
            for p in image_paths:
                data = p.read_bytes()
                suffix = p.suffix.lower()
                mime = "image/png" if suffix == ".png" else "image/jpeg"
                parts.append({
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(data).decode(),
                    },
                })
            parts.append({"text": prompt})

            text = self._analyze_images_with_retry(client, parts)
            return text if text else None
        except Exception:
            log.exception("Gemini analyze_images failed")
            return None

    @retry_on_transient_error
    def _analyze_images_with_retry(self, client, parts: list[dict]) -> str:
        resp = client.models.generate_content(
            model=self._model,
            contents=[{"role": "user", "parts": parts}],
        )
        return self._extract_text(resp)

    def transcribe_audio(self, audio_path: Path, prompt: str) -> str:
        client = self._get_client()
        if not client:
            return ""

        uploaded_name = None
        try:
            uploaded = client.files.upload(
                file=str(audio_path),
                config={"mime_type": "audio/wav"},
            )
            uploaded_name = uploaded.name

            while uploaded.state == "PROCESSING":
                time.sleep(1)
                uploaded = client.files.get(name=uploaded_name)

            if uploaded.state == "FAILED":
                log.warning("Gemini audio processing failed for %s", audio_path)
                return ""

            return self._transcribe_with_retry(client, uploaded, prompt)

        except Exception:
            log.exception("Gemini transcribe failed for %s", audio_path)
            return ""
        finally:
            if uploaded_name:
                try:
                    client.files.delete(name=uploaded_name)
                except Exception:
                    pass

    @retry_on_transient_error
    def _transcribe_with_retry(self, client, uploaded, prompt: str) -> str:
        resp = client.models.generate_content(
            model=self._model,
            contents=[{
                "role": "user",
                "parts": [
                    {
                        "file_data": {
                            "mime_type": uploaded.mime_type or "audio/wav",
                            "file_uri": uploaded.uri,
                        },
                    },
                    {"text": prompt},
                ],
            }],
        )
        return self._extract_text(resp)

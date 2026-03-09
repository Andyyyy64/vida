from __future__ import annotations

import abc
import functools
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

# HTTP status codes that should NOT be retried
_NON_RETRYABLE_CODES = {400, 401, 403, 404}

# Max retries and base delay for exponential backoff
_MAX_RETRIES = 3
_BASE_DELAY = 2  # seconds


def _is_transient_error(exc: Exception) -> bool:
    """Determine if an exception represents a transient/retryable error.

    Returns True for timeouts, rate limits (429), server errors (5xx).
    Returns False for auth errors (401/403) and bad requests (400).
    """
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    # Check for non-retryable HTTP status codes in the exception
    for code in _NON_RETRYABLE_CODES:
        if str(code) in str(exc):
            return False

    # Timeout errors are always transient
    if "timeout" in exc_type or "timeout" in exc_str:
        return True

    # Rate limit (429) is transient
    if "429" in str(exc) or "rate" in exc_str:
        return True

    # Server errors (5xx) are transient
    if any(str(code) in str(exc) for code in range(500, 600)):
        return True

    # Resource exhausted / quota exceeded are transient
    if "resourceexhausted" in exc_type or "resource_exhausted" in exc_str:
        return True

    # Default: treat unknown errors as transient (safer for resilience)
    return True


def retry_on_transient_error(func):
    """Decorator that retries a function on transient errors with exponential backoff.

    Retries up to 3 times with delays of 2s, 4s, 8s.
    Does NOT retry on auth errors (401/403) or invalid requests (400).
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    log.warning("LLM call %s failed after %d retries: %s", func.__qualname__, _MAX_RETRIES, exc)
                    raise

                if not _is_transient_error(exc):
                    log.warning("LLM call %s failed with non-retryable error: %s", func.__qualname__, exc)
                    raise

                delay = _BASE_DELAY * (2**attempt)
                log.warning(
                    "LLM call %s failed (attempt %d/%d), retrying in %ds: %s",
                    func.__qualname__,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)

        raise last_exc  # unreachable, but satisfies type checker

    return wrapper


class LLMProvider(abc.ABC):
    """Abstract base for LLM providers (Claude, Gemini, etc.)."""

    @abc.abstractmethod
    def generate_text(self, prompt: str, timeout: int = 120) -> str | None:
        """Generate text from a text-only prompt."""
        ...

    @abc.abstractmethod
    def analyze_images(
        self,
        prompt: str,
        image_paths: list[Path],
        timeout: int = 120,
    ) -> str | None:
        """Generate text from a prompt with image inputs."""
        ...

    def transcribe_audio(self, audio_path: Path, prompt: str) -> str:
        """Transcribe audio to text. Returns empty string if not supported."""
        return ""

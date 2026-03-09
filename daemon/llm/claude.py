from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from daemon.llm.base import LLMProvider, retry_on_transient_error

log = logging.getLogger(__name__)

_CLAUDE_CMD = "claude"


def _clean_env() -> dict[str, str]:
    """Remove Claude Code session markers so subprocess doesn't think it's nested."""
    env = os.environ.copy()
    for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        env.pop(key, None)
    return env


class ClaudeProvider(LLMProvider):
    """LLM provider using Claude Code CLI (claude -p)."""

    def __init__(self, model: str = "haiku"):
        self._model = model

    def generate_text(self, prompt: str, timeout: int = 120) -> str | None:
        return self._call(prompt, timeout)

    def analyze_images(
        self,
        prompt: str,
        image_paths: list[Path],
        timeout: int = 120,
    ) -> str | None:
        # Claude Code reads image files via its Read tool.
        # Embed file paths in the prompt so it knows what to read.
        if not image_paths:
            return self._call(prompt, timeout)
        refs = "\n".join(f"画像{i}のファイルパス: {p.resolve()}" for i, p in enumerate(image_paths, 1))
        full = f"{prompt}\n\n上記の分析対象画像:\n{refs}\nこれらの画像ファイルを読んでください。"
        return self._call(full, timeout)

    # Claude Code CLI cannot process audio files.
    # transcribe_audio() inherits the default (returns "").

    def _call(self, prompt: str, timeout: int) -> str | None:
        claude = shutil.which(_CLAUDE_CMD)
        if not claude:
            log.error("claude CLI not found in PATH")
            return None

        try:
            return self._call_with_retry(claude, prompt, timeout)
        except Exception:
            log.exception("Failed to call claude")
            return None

    @retry_on_transient_error
    def _call_with_retry(self, claude: str, prompt: str, timeout: int) -> str | None:
        out_path = err_path = None
        try:
            with (
                tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".txt",
                    delete=False,
                ) as out_f,
                tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".txt",
                    delete=False,
                ) as err_f,
            ):
                out_path, err_path = out_f.name, err_f.name

            with open(out_path, "w") as out_fh, open(err_path, "w") as err_fh:
                result = subprocess.run(
                    [claude, "-p", prompt, "--model", self._model],
                    stdin=subprocess.DEVNULL,
                    stdout=out_fh,
                    stderr=err_fh,
                    timeout=timeout,
                    env=_clean_env(),
                )

            stdout = Path(out_path).read_text().strip()
            stderr = Path(err_path).read_text().strip()

            if result.returncode != 0:
                log.warning("claude returned %d: %s", result.returncode, stderr[:200])
                # Raise so the retry decorator can evaluate the error
                raise RuntimeError(f"claude exit code {result.returncode}: {stderr[:200]}")
            return stdout if stdout else None

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude timeout after {timeout}s") from exc
        finally:
            if out_path:
                Path(out_path).unlink(missing_ok=True)
            if err_path:
                Path(err_path).unlink(missing_ok=True)

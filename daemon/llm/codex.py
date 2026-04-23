from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from daemon.llm.base import LLMProvider, retry_on_transient_error

log = logging.getLogger(__name__)

_CODEX_CMD = "codex"


def _clean_env() -> dict[str, str]:
    """Remove session-scoped Codex variables before spawning a nested CLI."""
    env = os.environ.copy()
    for key in ("CODEX_THREAD_ID",):
        env.pop(key, None)
    return env


class CodexProvider(LLMProvider):
    """LLM provider using the local Codex CLI (`codex exec`)."""

    def __init__(self, model: str = "gpt-5.4"):
        self._model = model

    def generate_text(self, prompt: str, timeout: int = 120) -> str | None:
        return self._call(prompt, image_paths=None, timeout=timeout)

    def analyze_images(
        self,
        prompt: str,
        image_paths: list[Path],
        timeout: int = 120,
    ) -> str | None:
        return self._call(prompt, image_paths=image_paths, timeout=timeout)

    def _call(self, prompt: str, image_paths: list[Path] | None, timeout: int) -> str | None:
        codex = shutil.which(_CODEX_CMD)
        if not codex:
            log.error("codex CLI not found in PATH")
            return None

        try:
            return self._call_with_retry(codex, prompt, image_paths or [], timeout)
        except Exception:
            log.exception("Failed to call codex")
            return None

    @retry_on_transient_error
    def _call_with_retry(self, codex: str, prompt: str, image_paths: list[Path], timeout: int) -> str | None:
        out_path = err_path = last_message_path = None
        try:
            with (
                tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as out_f,
                tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as err_f,
                tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as msg_f,
            ):
                out_path, err_path, last_message_path = out_f.name, err_f.name, msg_f.name

            cmd = [
                codex,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--model",
                self._model,
                "-o",
                last_message_path,
            ]
            for image_path in image_paths:
                cmd.extend(["-i", str(image_path.resolve())])
            if image_paths:
                cmd.append("--")
            cmd.append(prompt)

            with open(out_path, "w") as out_fh, open(err_path, "w") as err_fh:
                result = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=out_fh,
                    stderr=err_fh,
                    timeout=timeout,
                    env=_clean_env(),
                )

            stdout = Path(out_path).read_text().strip()
            stderr = Path(err_path).read_text().strip()
            message = Path(last_message_path).read_text().strip()

            if result.returncode != 0:
                detail = stderr or stdout or "no output"
                log.warning("codex returned %d: %s", result.returncode, detail[:200])
                raise RuntimeError(f"codex exit code {result.returncode}: {detail[:200]}")
            return message if message else None

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"codex timeout after {timeout}s") from exc
        finally:
            if out_path:
                Path(out_path).unlink(missing_ok=True)
            if err_path:
                Path(err_path).unlink(missing_ok=True)
            if last_message_path:
                Path(last_message_path).unlink(missing_ok=True)

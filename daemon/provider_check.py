from __future__ import annotations

import json
import os
import shutil
import sys

from daemon.llm import create_provider


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        _emit({"ok": False, "code": "invalid_payload"})
        return 1

    provider = str(data.get("provider") or "").strip()
    claude_model = str(data.get("claude_model") or "haiku")
    codex_model = str(data.get("codex_model") or "gpt-5.4")
    gemini_model = str(data.get("gemini_model") or "gemini-3.1-flash-lite-preview")
    gemini_api_key = str(data.get("gemini_api_key") or "").strip()

    if provider == "external":
        _emit({"ok": True, "code": "external"})
        return 0

    if provider not in {"gemini", "claude", "codex"}:
        _emit({"ok": False, "code": "invalid_provider"})
        return 1

    if provider == "gemini":
        api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            _emit({"ok": False, "code": "missing_api_key"})
            return 0
        os.environ["GEMINI_API_KEY"] = api_key

    if provider == "claude" and not shutil.which("claude"):
        _emit({"ok": False, "code": "missing_binary"})
        return 0

    if provider == "codex" and not shutil.which("codex"):
        _emit({"ok": False, "code": "missing_binary"})
        return 0

    token = f"VIDA_PROVIDER_CHECK_OK_{provider.upper()}"
    prompt = f"Return exactly the string: {token}"

    result = create_provider(
        provider,
        claude_model=claude_model,
        codex_model=codex_model,
        gemini_model=gemini_model,
    ).generate_text(prompt, timeout=45)

    if result and token in result:
        _emit({"ok": True, "code": "ready"})
        return 0

    detail = (result or "").strip()[:200]
    if provider in {"claude", "codex"}:
        _emit({"ok": False, "code": "binary_found_but_failed", "detail": detail})
        return 0

    _emit({"ok": False, "code": "request_failed", "detail": detail})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

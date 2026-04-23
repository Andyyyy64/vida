from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from daemon.llm import create_provider
from daemon.llm.codex import CodexProvider


def test_create_provider_codex():
    provider = create_provider("codex", codex_model="gpt-5.4-mini")
    assert isinstance(provider, CodexProvider)
    assert provider._model == "gpt-5.4-mini"


def test_codex_provider_generate_text_invokes_codex_exec(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("generated")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("daemon.llm.codex.shutil.which", lambda _: "/usr/bin/codex")
    monkeypatch.setattr("daemon.llm.codex.subprocess.run", fake_run)

    provider = CodexProvider(model="gpt-5.4")
    result = provider.generate_text("hello")

    assert result == "generated"
    assert calls[0][:11] == [
        "/usr/bin/codex",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--model",
        "gpt-5.4",
        "-o",
    ]
    assert calls[0][-1] == "hello"


def test_codex_provider_analyze_images_attaches_images(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"jpg")

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("analysis")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("daemon.llm.codex.shutil.which", lambda _: "/usr/bin/codex")
    monkeypatch.setattr("daemon.llm.codex.subprocess.run", fake_run)

    provider = CodexProvider()
    result = provider.analyze_images("describe", [image_path])

    assert result == "analysis"
    assert calls[0][:10] == [
        "/usr/bin/codex",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--model",
        "gpt-5.4",
    ]
    assert "-o" in calls[0]
    assert calls[0][-4:] == ["-i", str(image_path.resolve()), "--", "describe"]

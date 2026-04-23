from daemon.llm.base import LLMProvider
from daemon.llm.claude import ClaudeProvider
from daemon.llm.codex import CodexProvider
from daemon.llm.gemini import GeminiProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "gemini": GeminiProvider,
}


def create_provider(
    provider: str,
    *,
    claude_model: str = "haiku",
    codex_model: str = "gpt-5.4",
    gemini_model: str = "gemini-3.1-flash-lite-preview",
) -> LLMProvider:
    """Create an LLM provider by name."""
    if provider == "claude":
        return ClaudeProvider(model=claude_model)
    if provider == "codex":
        return CodexProvider(model=codex_model)
    if provider == "gemini":
        return GeminiProvider(model=gemini_model)
    available = ", ".join(_PROVIDERS)
    raise ValueError(f"Unknown provider '{provider}'. Available: {available}")


__all__ = [
    "LLMProvider",
    "ClaudeProvider",
    "CodexProvider",
    "GeminiProvider",
    "create_provider",
]

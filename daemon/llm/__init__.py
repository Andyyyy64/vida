from daemon.llm.base import LLMProvider
from daemon.llm.claude import ClaudeProvider
from daemon.llm.gemini import GeminiProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}


def create_provider(
    provider: str,
    *,
    claude_model: str = "haiku",
    gemini_model: str = "gemini-3.1-flash-lite-preview",
) -> LLMProvider:
    """Create an LLM provider by name."""
    if provider == "claude":
        return ClaudeProvider(model=claude_model)
    if provider == "gemini":
        return GeminiProvider(model=gemini_model)
    available = ", ".join(_PROVIDERS)
    raise ValueError(f"Unknown provider '{provider}'. Available: {available}")


__all__ = [
    "LLMProvider",
    "ClaudeProvider",
    "GeminiProvider",
    "create_provider",
]

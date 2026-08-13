"""LLM client — a thin adapter over `llmkit.llm`.

The implementation moved to the `llmkit` package (github.com/chiranjeevigundu/llmkit),
which is shared with synapse-storage-system. What stays here is the part that is
genuinely this application's: resolving secrets the way this deployment resolves them.

**Why config is built per call rather than once at startup.**

`llmkit.configure()` installs a process-wide default, which is the obvious thing to
call from `create_app()`. It would break the test suite in a way that is unpleasant to
diagnose. `tests/test_llm.py` sets `OPENROUTER_API_KEY` with monkeypatch *after*
import and expects the next call to see it — which works because `Settings.
openrouter_api_key` is a property that re-reads on every access. But pytest runs files
alphabetically, and several earlier files construct the app through TestClient. Those
would call `configure()` first, pinning a config, and every later env change would be
silently ignored. The failures would appear in `test_llm.py`, far from the cause.

Building the config per call keeps the original semantics exactly: secret file first,
environment second, re-read every time. The cost is constructing a small frozen
dataclass per model call, which is nothing beside an HTTP request to a model.

`litellm` and `requests` are re-exported deliberately — `tests/test_llm.py` patches
`llm.litellm.completion` and `llm.requests.get`, and those names have to resolve to
the same module objects llmkit uses or the patches reach nothing.
"""

from llmkit.config import LLMConfig
from llmkit.llm import LLMError, chat as _chat, health as _health

# Re-exported so existing monkeypatch targets keep working. Both are the same module
# objects llmkit calls through, so patching an attribute here changes llmkit's
# behaviour — which is the point.
from llmkit.llm import litellm, requests  # noqa: F401

from app.core.config import get_settings

__all__ = ["LLMError", "chat", "health", "litellm", "requests"]


def _config() -> LLMConfig:
    """This deployment's settings, as an llmkit config.

    `openrouter_api_key` is a property that checks the Docker secret file and then the
    environment on every access. That resolution order is this application's
    convention and stays on this side of the boundary; llmkit never reads a file.
    """
    settings = get_settings()
    return LLMConfig(
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
        ollama_base_url=settings.ollama_base_url,
        app_public_url=settings.app_public_url,
        referer_title="Aadyon Assist",
        routes=settings.default_routes,
        langfuse_public_key=settings.langfuse_public_key,
        langfuse_secret_key=settings.langfuse_secret_key,
        langfuse_host=settings.langfuse_host,
    )


def chat(
    provider: str,
    model: str,
    messages: list[dict],
    tools: list | None = None,
    temperature: float = 0.2,
    stream: bool = False,
    *,
    tier: str | None = None,
) -> dict | object:
    """Call a model. Signature preserved from before the extraction.

    `tier` is new and optional: it tags the call for cost reporting. Callers that
    resolve a route through `routing.resolve()` should pass it, since a call that
    arrives untagged is invisible in per-tier cost breakdowns.
    """
    return _chat(
        provider,
        model,
        messages,
        tools=tools,
        temperature=temperature,
        stream=stream,
        config=_config(),
        tier=tier,
    )


def health() -> dict:
    """What is reachable, for the dashboard and ops checks."""
    return _health(_config())

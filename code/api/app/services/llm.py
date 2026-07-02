"""LLM client core — one chat() entrypoint over two providers, powered by LiteLLM.

- OpenRouter (cloud): OpenAI-compatible, multi-provider, supports tool-calling.
  Use the special model "openrouter/auto" to let OpenRouter pick the best model.
- Ollama (local): for private/bulk tiers. Plain completion (no tool-calling here).

LiteLLM normalizes both to the OpenAI response shape and adds retries. Keys are
read lazily from config (secret file or env) and passed per-call — never set as
globals — so a missing key surfaces as LLMError, which the engine turns into a
'blocked' task rather than crashing. `stream=True` support in litellm.completion
is the enabler for token-streaming in the assistant's SSE endpoint (follow-up).
"""
import litellm
import requests

from app.core.config import get_settings

# Quiet library banners/telemetry; failures must raise, not print.
litellm.suppress_debug_info = True
litellm.telemetry = False


class LLMError(RuntimeError):
    pass


def health() -> dict:
    """Report what's reachable, for the dashboard / ops checks."""
    s = get_settings()
    ollama_ok = False
    try:
        r = requests.get(f"{s.ollama_base_url}/api/tags", timeout=3)
        ollama_ok = r.ok
    except Exception:  # noqa: BLE001
        ollama_ok = False
    return {
        "openrouter_key_set": bool(s.openrouter_api_key),
        "openrouter_base_url": s.openrouter_base_url,
        "ollama_reachable": ollama_ok,
        "ollama_base_url": s.ollama_base_url,
    }


def chat(provider: str, model: str, messages: list[dict],
         tools: list | None = None, temperature: float = 0.2) -> dict:
    """Return a normalized OpenAI-style response:
    {"message": {...}, "usage": {...}, "provider", "model"}.
    """
    s = get_settings()
    kwargs: dict = {
        "messages": messages,
        "temperature": temperature,
        "num_retries": 2,
    }

    if provider == "ollama":
        # Local chat endpoint; no tool-calling on this path (mirrors the engine's gate).
        kwargs["model"] = f"ollama_chat/{model}"
        kwargs["api_base"] = s.ollama_base_url
        kwargs["timeout"] = 300
    else:
        key = s.openrouter_api_key
        if not key:
            raise LLMError(
                "OPENROUTER_API_KEY is not set — add it to .env or secrets/openrouter_api_key.txt"
            )
        # model_routes may store either "auto" or the full "openrouter/auto".
        kwargs["model"] = f"openrouter/{model.removeprefix('openrouter/')}"
        kwargs["api_key"] = key
        kwargs["api_base"] = s.openrouter_base_url
        kwargs["timeout"] = 120
        kwargs["extra_headers"] = {"HTTP-Referer": s.app_public_url, "X-Title": "Aadyon Assist"}
        if tools:
            kwargs["tools"] = tools

    try:
        resp = litellm.completion(**kwargs)
    except Exception as e:  # litellm raises provider-specific exception classes
        raise LLMError(f"{provider} request failed: {e}") from e

    msg = resp.choices[0].message.model_dump()
    # Match the previous wire shape: no tool_calls key unless calls were made.
    if not msg.get("tool_calls"):
        msg.pop("tool_calls", None)
    usage = resp.usage.model_dump() if getattr(resp, "usage", None) else {}
    return {"message": msg, "usage": usage, "provider": provider, "model": model}

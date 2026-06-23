"""LLM client core — one chat() entrypoint over two providers.

- OpenRouter (cloud): OpenAI-compatible, multi-provider, supports tool-calling.
  Use the special model "openrouter/auto" to let OpenRouter pick the best model.
- Ollama (local): for private/bulk tiers. Plain completion (no tool-calling here).

Keys are read lazily from config (secret file or env). No key -> LLMError, which
the engine turns into a 'blocked' task rather than crashing.
"""
import requests

from app.core.config import get_settings


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
    if provider == "ollama":
        out = _ollama_chat(model, messages, temperature)
    else:
        out = _openrouter_chat(model, messages, tools, temperature)
    out["provider"] = provider
    out["model"] = model
    return out


def _openrouter_chat(model, messages, tools, temperature) -> dict:
    s = get_settings()
    key = s.openrouter_api_key
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set — add it to .env or secrets/openrouter_api_key.txt")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Aadyon Assist",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
    try:
        r = requests.post(f"{s.openrouter_base_url}/chat/completions",
                          headers=headers, json=payload, timeout=120)
    except requests.RequestException as e:
        raise LLMError(f"OpenRouter request failed: {e}") from e
    if not r.ok:
        raise LLMError(f"OpenRouter {r.status_code}: {r.text[:300]}")
    data = r.json()
    return {"message": data["choices"][0]["message"], "usage": data.get("usage", {})}


def _ollama_chat(model, messages, temperature) -> dict:
    s = get_settings()
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": temperature}}
    try:
        r = requests.post(f"{s.ollama_base_url}/api/chat", json=payload, timeout=300)
    except requests.RequestException as e:
        raise LLMError(f"Ollama request failed ({s.ollama_base_url}): {e}") from e
    if not r.ok:
        raise LLMError(f"Ollama {r.status_code}: {r.text[:300]}")
    data = r.json()
    msg = data.get("message", {"role": "assistant", "content": ""})
    usage = {"total_tokens": data.get("eval_count", 0) + data.get("prompt_eval_count", 0)}
    return {"message": msg, "usage": usage}

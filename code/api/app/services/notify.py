"""Push notifications via self-hosted ntfy.

The briefing worker calls push_briefing() once a day. It POSTs the briefing
markdown to the in-stack ntfy server (reached by service name), which delivers
it to the phone over Tailscale. Content never leaves the tailnet; only an
iOS background wake is proxied via ntfy.sh upstream (configured on the server).
"""
import requests

from app.core.config import get_settings


def push_briefing(markdown: str) -> bool:
    """POST the briefing to the configured ntfy topic. No-op if topic unset."""
    s = get_settings()
    if not s.ntfy_topic:
        return False
    url = f"{s.ntfy_internal_url.rstrip('/')}/{s.ntfy_topic}"
    try:
        r = requests.post(
            url,
            data=markdown.encode("utf-8"),
            headers={
                "Title": "Aadyon — morning briefing",
                "Markdown": "yes",
                "Tags": "sunrise",
                "Priority": "default",
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"[notify] pushed briefing to ntfy topic '{s.ntfy_topic}'", flush=True)
        return True
    except Exception as e:  # noqa: BLE001 — never let a push break the briefing
        print(f"[notify] ntfy push failed: {e}", flush=True)
        return False

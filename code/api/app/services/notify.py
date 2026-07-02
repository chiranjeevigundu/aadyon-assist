"""Push notifications via self-hosted ntfy.

The briefing worker calls push_briefing() once a day. It POSTs the briefing
markdown to the in-stack ntfy server (reached by service name), which delivers
it to the phone over Tailscale. Content never leaves the tailnet; only an
iOS background wake is proxied via ntfy.sh upstream (configured on the server).
"""
import requests

from app.core.config import get_settings
from app.db.session import query_unscoped


def _get_user_topic(user_id: str | None) -> str:
    s = get_settings()
    if user_id:
        rows = query_unscoped("SELECT ntfy_topic FROM users WHERE id = %s", (user_id,))
        if rows and rows[0]["ntfy_topic"]:
            return rows[0]["ntfy_topic"]
    return s.ntfy_topic


def push_briefing(user_id: str | None, markdown: str) -> bool:
    """POST the briefing to the user's ntfy topic (fallback to env var). No-op if topic unset."""
    s = get_settings()
    topic = _get_user_topic(user_id)
    if not topic:
        return False
    url = f"{s.ntfy_internal_url.rstrip('/')}/{topic}"
    try:
        r = requests.post(
            url,
            data=markdown.encode("utf-8"),
            headers={
                # HTTP headers must be Latin-1 — keep this ASCII (no em dash).
                "Title": "Aadyon - morning briefing",
                "Markdown": "yes",
                "Tags": "sunrise",
                "Priority": "default",
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"[notify] pushed briefing to ntfy topic '{topic}'", flush=True)
        return True
    except Exception as e:  # noqa: BLE001 — never let a push break the briefing
        print(f"[notify] ntfy push failed: {e}", flush=True)
        return False


def push_alert(user_id: str, markdown: str, title: str = "Aadyon Alert") -> bool:
    """POST a high-priority alert to the user's ntfy topic."""
    s = get_settings()
    topic = _get_user_topic(user_id)
    if not topic:
        return False
    url = f"{s.ntfy_internal_url.rstrip('/')}/{topic}"
    try:
        r = requests.post(
            url,
            data=markdown.encode("utf-8"),
            headers={
                "Title": title,
                "Markdown": "yes",
                "Tags": "warning",
                "Priority": "high",
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"[notify] pushed alert to ntfy topic '{topic}'", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[notify] ntfy alert push failed: {e}", flush=True)
        return False

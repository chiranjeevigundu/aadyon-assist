"""Push notifications via self-hosted ntfy.

The briefing worker calls push_briefing() once a day. It POSTs the briefing
markdown to the in-stack ntfy server (reached by service name), which delivers
it to the phone over Tailscale. Content never leaves the tailnet; only an
iOS background wake is proxied via ntfy.sh upstream (configured on the server).
"""
import requests

from app.core.config import get_settings


def push_message(markdown: str, title: str, topic: str | None = None,
                 tags: str = "sunrise", priority: str = "default") -> bool:
    """POST a message to an ntfy topic (default: the global NTFY_TOPIC).
    No-op if no topic is configured. Never raises."""
    s = get_settings()
    topic = topic or s.ntfy_topic
    if not topic:
        return False
    url = f"{s.ntfy_internal_url.rstrip('/')}/{topic}"
    try:
        r = requests.post(
            url,
            data=markdown.encode("utf-8"),
            headers={
                # HTTP headers must be Latin-1 — keep these ASCII (no em dash).
                "Title": title,
                "Markdown": "yes",
                "Tags": tags,
                "Priority": priority,
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"[notify] pushed '{title}' to ntfy topic '{topic}'", flush=True)
        return True
    except Exception as e:  # noqa: BLE001 — never let a push break the worker
        print(f"[notify] ntfy push failed: {e}", flush=True)
        return False


def push_briefing(markdown: str, topic: str | None = None) -> bool:
    """POST the briefing to ntfy. No-op if no topic configured."""
    return push_message(markdown, title="Aadyon - morning briefing", topic=topic)


def push_alerts(markdown: str, topic: str | None = None) -> bool:
    """POST an alert digest to ntfy (higher priority than the briefing)."""
    return push_message(markdown, title="Aadyon - needs attention", topic=topic,
                        tags="warning", priority="high")

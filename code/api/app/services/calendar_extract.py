"""LLM extraction of one actionable life-ops item from a calendar event.

Pure logic: given event title and description, return a normalized item dict or None.
Never touches the DB or the network except via the shared LLM client.
"""
import json
from datetime import date

from app.services import routing
from app.services.llm import chat
from app.services.email_extract import coerce_due

_EXTRACT_SYS = (
    "You extract ONE actionable personal life-ops item from a calendar event, if present. "
    "Return STRICT JSON only, no prose. Schema: "
    '{"kind":"deadline|none","title":string,'
    '"due_date":<JSON null or "YYYY-MM-DD">,"amount":<JSON null or number>,"summary":string}. '
    "A 'deadline' must be something YOU must personally do by a date (a payment, appointment, "
    "filing, renewal, or expiry) — NOT a log of a routine meeting, gym session, commute, or reminder. "
    "Return 'none' for anything that isn't a real personal to-do: weekly syncs, flights, hotel stays, "
    "holidays, birthdays, weather, marketing events, or general reminders. "
    "due_date and amount MUST be JSON null (not the string \"null\") when unknown. "
    "Never invent amounts or dates not present in the event."
)


def normalize(d: dict, default_due: str | None = None) -> dict | None:
    """Clean the model output and drop non-actionable / malformed items."""
    kind = (d.get("kind") or "none").strip().lower()
    # If the LLM didn't extract a due_date, we can fallback to the event's start date
    due = coerce_due(d.get("due_date")) or default_due
    d["due_date"] = due
    
    amt = d.get("amount")
    if isinstance(amt, str):
        try:
            amt = float(amt.replace("$", "").replace(",", "").strip())
        except Exception:  # noqa: BLE001
            amt = None
    d["amount"] = amt
    
    if kind == "deadline":
        if not d["due_date"] or date.fromisoformat(d["due_date"]) < date.today():
            return None  # a deadline needs a real, non-past date
    else:
        return None
    return d


def extract(title: str, description: str, event_date: str | None) -> dict | None:
    """Run the cheap model over one event; return a normalized item or None."""
    route = routing.resolve("cheap")
    msgs = [
        {"role": "system", "content": _EXTRACT_SYS},
        {"role": "user", "content": f"Event: {title}\nDate: {event_date}\n\n{description}"},
    ]
    resp = chat(route["provider"], route["model"], msgs, None, 0.0)
    txt = (resp["message"].get("content") or "").strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        txt = txt[txt.find("{"):txt.rfind("}") + 1]
    try:
        data = json.loads(txt)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict) or data.get("kind") in (None, "none", ""):
        return None
    
    default_due = coerce_due(event_date) if event_date else None
    return normalize(data, default_due)

"""LLM extraction of one actionable life-ops item from an email + output cleaning.

Pure logic: given sender/subject/body, return a normalized item dict or None.
Never touches the DB or the network except via the shared LLM client.
"""
import json
from datetime import date

from app.services import routing
from app.services.llm import chat

_EXTRACT_SYS = (
    "You extract ONE actionable personal life-ops item from an email, if present. "
    "Return STRICT JSON only, no prose. Schema: "
    '{"kind":"deadline|bill|subscription|none","title":string,'
    '"due_date":<JSON null or "YYYY-MM-DD">,"amount":<JSON null or number>,"summary":string}. '
    "A 'deadline' must be something YOU must personally do by a date (a payment, appointment, "
    "filing, renewal, or expiry) — NOT a log of something that already happened. "
    "'bill' = a specific payment you owe, with an amount. "
    "'subscription' = a recurring charge/renewal, with an amount. "
    "Return 'none' for anything that isn't a real personal to-do: marketing, sales, promotions, "
    "newsletters, social, receipts/confirmations for completed actions, shipping/tracking, "
    "OTP/verification, login/security alerts, and AUTOMATED system notifications "
    "(CI/CD, build/deploy results, GitHub/GitLab/version-control, workflow runs, app/service status). "
    "due_date and amount MUST be JSON null (not the string \"null\") when unknown. "
    "Never invent amounts or dates not present in the email."
)


def coerce_due(due):
    """Coerce a model due_date to a clean ISO 'YYYY-MM-DD' string or None.

    Handles the model's stringly-typed "null"/"none"/"" and validates the date.
    Shared by extraction-time normalization and approval-time application.
    """
    if isinstance(due, str) and due.strip().lower() in ("", "null", "none", "n/a", "tbd"):
        due = None
    if due is not None:
        try:
            due = date.fromisoformat(str(due)[:10]).isoformat()
        except Exception:  # noqa: BLE001
            due = None
    return due


def normalize(d: dict) -> dict | None:
    """Clean the model output and drop non-actionable / malformed items."""
    kind = (d.get("kind") or "none").strip().lower()
    d["due_date"] = coerce_due(d.get("due_date"))
    # amount: coerce "$1,234.50" -> float
    amt = d.get("amount")
    if isinstance(amt, str):
        try:
            amt = float(amt.replace("$", "").replace(",", "").strip())
        except Exception:  # noqa: BLE001
            amt = None
    d["amount"] = amt
    # filters
    if kind == "deadline":
        if not d["due_date"] or date.fromisoformat(d["due_date"]) < date.today():
            return None  # a deadline needs a real, non-past date
    elif kind in ("bill", "subscription"):
        if amt is None or amt <= 0:
            return None
    else:
        return None
    return d


def extract(sender: str, subject: str, body: str) -> dict | None:
    """Run the cheap model over one message; return a normalized item or None.

    May raise LLMError (the model client's error) — callers handle it.
    """
    route = routing.resolve("cheap")
    msgs = [
        {"role": "system", "content": _EXTRACT_SYS},
        {"role": "user", "content": f"From: {sender}\nSubject: {subject}\n\n{body}"},
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
    return normalize(data)

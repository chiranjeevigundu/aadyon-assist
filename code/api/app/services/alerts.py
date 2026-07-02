"""Proactive alerts — what needs the user's attention in the next few days.

Pure read-model over the RLS-scoped tables: overdue/upcoming deadlines and
bills whose day-of-month falls within the window. The briefing worker pushes
these to the user's ntfy topic daily; GET /api/alerts serves the same list.
"""
from datetime import date, timedelta

from app.core.config import get_settings
from app.db.session import query


def _next_due(due_day: int, today: date) -> date:
    """The next calendar date a monthly bill with this due_day falls on."""
    day = min(max(int(due_day), 1), 28)  # clamp: every month has a day 28
    if day >= today.day:
        return today.replace(day=day)
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, day)


def build_alerts(days: int | None = None, today: date | None = None) -> list[dict]:
    """Alert dicts for the current (RLS-scoped) user, most urgent first."""
    days = days if days is not None else get_settings().alert_days
    today = today or date.today()
    horizon = today + timedelta(days=days)
    alerts: list[dict] = []

    for d in query(
        "SELECT id, title, due_date, status FROM deadlines "
        "WHERE status NOT IN ('done', 'missed') AND due_date <= %s ORDER BY due_date",
        (horizon,),
    ):
        overdue = d["due_date"] < today
        delta = abs((d["due_date"] - today).days)
        when = (f"{delta}d overdue" if overdue
                else "due today" if delta == 0 else f"due in {delta}d")
        alerts.append({
            "kind": "deadline", "severity": "high" if overdue or delta == 0 else "medium",
            "title": d["title"], "when": when, "date": str(d["due_date"]), "id": str(d["id"]),
        })

    for b in query(
        "SELECT id, name, amount, due_day, autopay FROM bills "
        "WHERE active AND due_day IS NOT NULL ORDER BY due_day",
        (),
    ):
        nd = _next_due(b["due_day"], today)
        delta = (nd - today).days
        if delta <= days:
            when = "due today" if delta == 0 else f"due in {delta}d"
            alerts.append({
                "kind": "bill", "severity": "medium" if b.get("autopay") else "high",
                "title": f"{b['name']} (${b['amount']})", "when": when,
                "date": str(nd), "id": str(b["id"]),
            })

    order = {"high": 0, "medium": 1}
    alerts.sort(key=lambda a: (order.get(a["severity"], 2), a["date"]))
    return alerts


def alerts_markdown(alerts: list[dict]) -> str:
    """A compact push-notification body."""
    lines = [f"- [{a['severity']}] {a['title']} - {a['when']}" for a in alerts]
    return "\n".join(lines)

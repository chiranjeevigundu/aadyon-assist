"""Builds the daily life-ops briefing as Markdown from the live DB."""
from datetime import date

from app.db.session import query

HORIZON_DAYS = 14


def build_briefing(today: date | None = None) -> str:
    today = today or date.today()

    due_soon = query(
        "SELECT title, due_date, status, (due_date - CURRENT_DATE) AS days_left "
        "FROM deadlines WHERE status <> 'done' AND due_date <= CURRENT_DATE + %s "
        "ORDER BY due_date ASC",
        (HORIZON_DAYS,),
    )
    blocked = query(
        "SELECT title, due_date, blocked_on FROM deadlines "
        "WHERE status = 'blocked' ORDER BY due_date ASC"
    )
    bills_week = query(
        "SELECT name, amount, due_day FROM bills "
        "WHERE active AND due_day IS NOT NULL "
        "AND due_day BETWEEN EXTRACT(DAY FROM CURRENT_DATE)::int "
        "AND EXTRACT(DAY FROM CURRENT_DATE)::int + 7 "
        "ORDER BY due_day ASC"
    )
    totals = query(
        "SELECT COALESCE(SUM(balance),0) AS debt, "
        "COALESCE(SUM(balance*apr/100/12),0) AS int_mo FROM debts"
    )[0]
    renewals = query(
        "SELECT name, amount, renews_on FROM subscriptions "
        "WHERE active AND renews_on IS NOT NULL "
        "AND renews_on <= CURRENT_DATE + %s ORDER BY renews_on ASC",
        (HORIZON_DAYS,),
    )

    L: list[str] = [f"# Aadyon Assist — Briefing for {today:%A, %B %d, %Y}", ""]

    L.append(f"## Deadlines (next {HORIZON_DAYS} days)")
    if due_soon:
        for d in due_soon:
            days = d["days_left"]
            tag = "DUE TODAY" if days == 0 else (f"{days}d left" if days > 0 else f"{-days}d OVERDUE")
            L.append(f"- **{d['title']}** — {d['due_date']} ({tag}, {d['status']})")
    else:
        L.append("- Nothing due in this window.")
    L.append("")

    if blocked:
        L.append("## Blocked")
        for b in blocked:
            L.append(f"- **{b['title']}** ({b['due_date']}) — blocked on: {b['blocked_on']}")
        L.append("")

    L.append("## Bills due this week")
    if bills_week:
        for b in bills_week:
            L.append(f"- {b['name']} — ${b['amount']} (day {b['due_day']})")
    else:
        L.append("- None in the next 7 days.")
    L.append("")

    if renewals:
        L.append(f"## Subscriptions renewing (next {HORIZON_DAYS} days)")
        for s in renewals:
            L.append(f"- {s['name']} — ${s['amount']} on {s['renews_on']}")
        L.append("")

    L.append("## Money")
    L.append(f"- Total debt: **${float(totals['debt']):,.2f}**")
    L.append(f"- Interest accruing: **${float(totals['int_mo']):,.2f}/month**")
    L.append("")

    # Proposals waiting on you (the assistant files these; you approve).
    try:
        props = query(
            "SELECT title FROM proposals WHERE status = 'pending' "
            "ORDER BY created_at DESC LIMIT 5"
        )
        if props:
            L.append(f"## Proposals awaiting approval ({len(props)})")
            for p in props:
                L.append(f"- {p['title']}")
            L.append("")
    except Exception:  # noqa: BLE001
        pass

    return "\n".join(L)

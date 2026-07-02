"""Proactive intelligence rules evaluation."""
from datetime import date, timedelta

from app.db.session import active_user_ids, query, set_current_user
from app.services.notify import push_alert


def evaluate_rules() -> str:
    """Evaluate alert rules for all active users and push notifications."""
    notified_users = []
    
    for uid in active_user_ids():
        set_current_user(uid)
        alerts = []
        
        # Rule 1: Impending deadlines (within 3 days and not completed)
        target_date = date.today() + timedelta(days=3)
        deadlines = query(
            "SELECT title, due_date FROM deadlines WHERE status != 'completed' AND due_date <= %s ORDER BY due_date ASC",
            (target_date,)
        )
        if deadlines:
            alerts.append("**Upcoming Deadlines:**")
            for d in deadlines:
                alerts.append(f"- {d['title']} (due: {d['due_date']})")
                
        # Rule 2: Low bank balances (balance < 100)
        low_balance_accounts = query(
            "SELECT institution, balance FROM bank_accounts WHERE balance < 100.0 AND active = true"
        )
        if low_balance_accounts:
            if alerts:
                alerts.append("")
            alerts.append("**Low Balances:**")
            for a in low_balance_accounts:
                alerts.append(f"- {a['institution']}: ${a['balance']:.2f}")
                
        if alerts:
            markdown = "\n".join(alerts)
            if push_alert(uid, markdown, title="Aadyon - Proactive Alert"):
                notified_users.append(uid[:8])
                
    return f"Sent alerts to {len(notified_users)} user(s): {', '.join(notified_users) or 'none'}"

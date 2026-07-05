"""Per-user LLM token accounting + monthly budget enforcement.

`monthly_token_budget` NULL on a user means unlimited (the owner, and anyone you
don't cap). Counters live on the `users` row and reset at the start of each calendar
month on first use. Enforced in the assistant/agency loops: `check()` before spending,
`record()` after each model call.
"""
from app.db.session import query_unscoped


def _reset_if_new_month(user_id) -> None:
    query_unscoped(
        "UPDATE users SET tokens_used = 0, usage_period_start = date_trunc('month', CURRENT_DATE) "
        "WHERE id = %s AND (usage_period_start IS NULL "
        "OR date_trunc('month', usage_period_start) < date_trunc('month', CURRENT_DATE))",
        (str(user_id),), commit=True,
    )


def check(user_id) -> dict:
    """Return {allowed, unlimited, budget, used, remaining} for this user, rolling the
    monthly window first. Unlimited (NULL budget) is always allowed."""
    if not user_id:
        return {"allowed": True, "unlimited": True}
    _reset_if_new_month(user_id)
    rows = query_unscoped(
        "SELECT monthly_token_budget AS budget, tokens_used AS used FROM users WHERE id = %s",
        (str(user_id),),
    )
    if not rows or rows[0]["budget"] is None:
        return {"allowed": True, "unlimited": True}
    budget, used = int(rows[0]["budget"]), int(rows[0]["used"] or 0)
    remaining = budget - used
    return {"allowed": remaining > 0, "unlimited": False,
            "budget": budget, "used": used, "remaining": max(0, remaining)}


def record(user_id, tokens: int) -> None:
    """Add `tokens` to this user's monthly usage (no-op for unknown user / non-positive)."""
    if not user_id or not tokens or tokens <= 0:
        return
    query_unscoped("UPDATE users SET tokens_used = tokens_used + %s WHERE id = %s",
                   (int(tokens), str(user_id)), commit=True)

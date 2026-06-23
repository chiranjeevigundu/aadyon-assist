"""The individual life-dimension read-models.

Each function returns a transparent score plus the sub-components it was built
from, so every number on the dashboard is auditable. Pure computation over the
live tables; the orchestration lives in app.services.digital_me.
"""
from datetime import date

from app.db.session import query
from app.services.common import DAYS_PER_YEAR, WEEKS_PER_MONTH, f, clamp, rnd, band


def profile() -> dict:
    rows = query("SELECT * FROM profile LIMIT 1")
    return rows[0] if rows else {}


# --------------------------------------------------------------------------- life since birth
def life_track(p: dict, today: date) -> dict:
    bd = p.get("birthdate")
    if not bd:
        return {}
    days_alive = (today - bd).days
    age_years = days_alive / DAYS_PER_YEAR
    le = int(p.get("life_expectancy_years") or 80)

    thirty = date(bd.year + 30, bd.month, bd.day)  # the self-imposed deadline
    days_to_30 = (thirty - today).days

    return {
        "birthdate": str(bd),
        "days_alive": days_alive,
        "age_years": rnd(age_years, 2),
        "age_whole": int(age_years),
        "life_expectancy_years": le,
        "life_lived_pct": rnd(clamp(age_years / le * 100), 1),
        "weeks_lived": int(days_alive / 7),
        "weeks_total": le * 52,
        "thirtieth_birthday": str(thirty),
        "days_to_30": days_to_30,
        "years_to_30": rnd(days_to_30 / DAYS_PER_YEAR, 2),
        "age_progress_to_30_pct": rnd(clamp(age_years / 30 * 100), 1),
    }


# --------------------------------------------------------------------------- work & income
def work_income() -> dict:
    """Projected income from jobs + recurring weekly schedule.

    Hourly jobs: sum of active weekly schedule hours x rate. Salaried jobs:
    annual / 12. Totals count ACTIVE jobs only — offers and ended jobs are
    excluded so projected take-home reflects reality. Take-home applies each
    job's own remittance_pct.
    """
    jobs = query("SELECT * FROM jobs ORDER BY status ASC, employer ASC")
    sched = query(
        "SELECT job_id, COALESCE(SUM(hours), 0) AS wk_hours "
        "FROM work_schedule WHERE active GROUP BY job_id"
    )
    hours_by = {r["job_id"]: f(r["wk_hours"]) for r in sched}

    per_job = []
    wk_gross = mo_gross = mo_takehome = 0.0
    for j in jobs:
        remit = f(j.get("remittance_pct"))
        if j["kind"] == "full_time_salary" and j.get("annual_salary"):
            weekly = f(j["annual_salary"]) / 52
            monthly = f(j["annual_salary"]) / 12
            weekly_hours = None
        else:  # hourly / gig
            weekly_hours = hours_by.get(j["id"], 0.0)
            rate = f(j.get("hourly_rate"))
            weekly = weekly_hours * rate
            monthly = weekly * WEEKS_PER_MONTH
        takehome = monthly * (1 - remit / 100)
        per_job.append({
            "employer": j["employer"], "role": j.get("role"), "kind": j["kind"],
            "status": j["status"], "hourly_rate": j.get("hourly_rate"),
            "annual_salary": j.get("annual_salary"), "remittance_pct": j.get("remittance_pct"),
            "weekly_hours": rnd(weekly_hours, 2) if weekly_hours is not None else None,
            "weekly_gross": rnd(weekly, 2), "monthly_gross": rnd(monthly, 2),
            "monthly_takehome": rnd(takehome, 2),
        })
        if j["status"] == "active":
            wk_gross += weekly
            mo_gross += monthly
            mo_takehome += takehome

    return {
        "has_jobs": len(jobs) > 0,
        "weekly_gross": rnd(wk_gross, 2),
        "monthly_gross": rnd(mo_gross, 2),
        "monthly_takehome": rnd(mo_takehome, 2),
        "annual_takehome": rnd(mo_takehome * 12, 2),
        "jobs": per_job,
    }


# --------------------------------------------------------------------------- financial
def financial_dimension(p: dict, income: dict | None = None) -> dict:
    debts = query("SELECT * FROM debt_summary")
    totals = query(
        """
        SELECT COALESCE(SUM(balance),0)                                AS total_debt,
               COALESCE(SUM(COALESCE(installment_amount,min_payment)),0) AS total_min,
               COALESCE(SUM(balance*apr/100),0)                         AS ann_int,
               COALESCE(SUM(balance*apr/100/12),0)                      AS mo_int
        FROM debts
        """
    )[0]
    total_debt = f(totals["total_debt"])
    total_min = f(totals["total_min"])
    ann_int = f(totals["ann_int"])

    # Balance-weighted card utilization.
    cards = [d for d in debts if d.get("utilization_pct") is not None]
    wsum = sum(f(c["balance"]) for c in cards)
    weighted_util = (
        sum(f(c["utilization_pct"]) * f(c["balance"]) for c in cards) / wsum
        if wsum else 0.0
    )

    eff_apr = (ann_int / total_debt * 100) if total_debt else 0.0  # blended APR

    # Disposable income, monthly. Prefer real projected take-home from active jobs
    # (offers excluded); fall back to the profile figure if no jobs are defined.
    if income and income.get("has_jobs"):
        monthly_disposable = f(income.get("monthly_takehome"))
        disposable_source = "jobs"
    else:
        monthly_disposable = f(p.get("current_income")) * (1 - f(p.get("remittance_pct")) / 100) / 12
        disposable_source = "profile"

    # --- three transparent sub-scores (0-100, higher = healthier) ---
    util_score = clamp(100 - weighted_util)
    coverage_score = clamp(monthly_disposable / total_min * 100) if total_min else 100.0
    interest_score = clamp(100 * (1 - eff_apr / 30))  # 0% APR -> 100, 30% -> 0

    score = rnd(0.40 * util_score + 0.35 * coverage_score + 0.25 * interest_score, 0)

    return {
        "score": score,
        "band": band(score),
        "total_debt": rnd(total_debt, 2),
        "monthly_minimums": rnd(total_min, 2),
        "monthly_interest": rnd(f(totals["mo_int"]), 2),
        "annual_interest": rnd(ann_int, 2),
        "weighted_card_utilization_pct": rnd(weighted_util, 1),
        "effective_apr_pct": rnd(eff_apr, 1),
        "monthly_disposable": rnd(monthly_disposable, 2),
        "disposable_source": disposable_source,
        "components": {
            "utilization": rnd(util_score, 0),
            "coverage": rnd(coverage_score, 0),
            "interest": rnd(interest_score, 0),
        },
        "debts": debts,
    }


# --------------------------------------------------------------------------- visa
def visa_dimension(p: dict) -> dict:
    items = query(
        "SELECT title, due_date, status, priority, blocked_on, "
        "(due_date - CURRENT_DATE) AS days_left "
        "FROM deadlines WHERE category = 'immigration' AND status <> 'done' "
        "ORDER BY due_date ASC"
    )
    penalty = 0.0
    blockers = []
    for it in items:
        days = it["days_left"]
        days = 999 if days is None else int(days)
        if it["status"] == "blocked":
            penalty += 40 if days <= 14 else 25 if days <= 30 else 15
            blockers.append(it)
        elif days <= 7:
            penalty += 15
        elif days <= 30:
            penalty += 8
    score = rnd(clamp(100 - penalty), 0)

    work_auth = p.get("work_auth_until")
    return {
        "score": score,
        "band": band(score),
        "visa_type": p.get("visa_type"),
        "visa_status": p.get("visa_status"),
        "work_auth_until": str(work_auth) if work_auth else None,
        "work_auth_days_left": (work_auth - date.today()).days if work_auth else None,
        "open_count": len(items),
        "blocked_count": len(blockers),
        "next": items[0] if items else None,
        "items": items,
    }


# --------------------------------------------------------------------------- career
def career_dimension(p: dict) -> dict:
    apps = query(
        "SELECT *, (CURRENT_DATE - applied_date) AS age_days FROM applications "
        "ORDER BY COALESCE(applied_date, created_at::date) DESC"
    )
    total = len(apps)
    last30 = sum(
        1 for a in apps
        if a.get("age_days") is not None and 0 <= int(a["age_days"]) <= 30
    )
    in_funnel = {s: 0 for s in
                 ["saved", "applied", "screening", "interview", "offer", "rejected", "accepted"]}
    for a in apps:
        in_funnel[a["status"]] = in_funnel.get(a["status"], 0) + 1
    interviews = in_funnel["interview"] + in_funnel["offer"] + in_funnel["accepted"]
    offers = in_funnel["offer"] + in_funnel["accepted"]

    target = f(p.get("target_salary"))
    current = f(p.get("current_income"))
    gap = target - current
    gap_closed_pct = clamp(current / target * 100) if target else 0.0

    activity_score = clamp(last30 / 8 * 100)              # ~8 quality apps / month = full
    funnel_score = clamp(interviews * 25 + offers * 25)   # any traction climbs fast
    income_score = rnd(gap_closed_pct, 0)
    score = rnd(0.50 * activity_score + 0.30 * funnel_score + 0.20 * income_score, 0)

    return {
        "score": score,
        "band": band(score),
        "total_applications": total,
        "applications_last_30d": last30,
        "interviews": interviews,
        "offers": offers,
        "funnel": in_funnel,
        "target_salary": rnd(target, 2) if target else None,
        "current_income": rnd(current, 2) if current else None,
        "salary_gap": rnd(gap, 2) if target else None,
        "gap_closed_pct": rnd(gap_closed_pct, 1),
        "components": {
            "activity": rnd(activity_score, 0),
            "funnel": rnd(funnel_score, 0),
            "income": income_score,
        },
        "applications": apps,
        "started": total > 0,
    }


# --------------------------------------------------------------------------- goals
def goal_dimension(p: dict, life: dict) -> dict:
    goals = query(
        "SELECT title, category, milestone_date, progress_pct, notes "
        "FROM milestones WHERE achieved = false ORDER BY milestone_date ASC"
    )
    achieved = query(
        "SELECT title, category, milestone_date, notes "
        "FROM milestones WHERE achieved = true ORDER BY milestone_date ASC"
    )
    progresses = [int(g["progress_pct"]) for g in goals if g.get("progress_pct") is not None]
    avg_progress = sum(progresses) / len(progresses) if progresses else 0.0

    # Time used vs the before-30 window — negative pace gap means behind schedule.
    time_used = life.get("age_progress_to_30_pct", 0.0)

    return {
        "score": rnd(avg_progress, 0),
        "band": band(avg_progress),
        "goal_title": p.get("goal_title"),
        "goal_target_date": str(p["goal_target_date"]) if p.get("goal_target_date") else None,
        "days_to_30": life.get("days_to_30"),
        "avg_goal_progress_pct": rnd(avg_progress, 1),
        "time_used_pct": time_used,
        "pace_gap_pct": rnd(avg_progress - time_used, 1),
        "open_goals": goals,
        "achieved_milestones": achieved,
    }

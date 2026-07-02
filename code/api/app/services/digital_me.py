"""The "Digital Me" read-model — orchestration only.

Assembles the whole person into one payload: identity, a life-since-birth track,
and four life-dimension scores (financial, visa, career, goal), each computed in
app.services.dimensions. Every score is transparent and auditable.

Design note: the scores are deliberately honest. A near-limit debt load and a
job search that hasn't started will read low. That is the point — the dashboard
reflects reality; it does not flatter it.
"""
from datetime import date

from app.services.common import rnd, band
from app.services import dimensions as dim


def digital_me() -> dict:
    """The whole person in one payload."""
    today = date.today()
    p = dim.profile()
    life = dim.life_track(p, today)
    income = dim.work_income()
    fin = dim.financial_dimension(p, income)
    visa = dim.visa_dimension(p)
    career = dim.career_dimension(p)
    goal = dim.goal_dimension(p, life)

    # Overall composite — directional only, weighted toward the live fires.
    overall = rnd(
        0.35 * fin["score"] + 0.30 * visa["score"]
        + 0.25 * career["score"] + 0.10 * goal["score"], 0
    )

    return {
        "as_of": str(today),
        "profile": p,
        "life": life,
        "income": income,
        "overall": {"score": overall, "band": band(overall)},
        "dimensions": {
            "financial": fin,
            "visa": visa,
            "career": career,
            "goal": goal,
        },
    }

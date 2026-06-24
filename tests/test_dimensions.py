"""Life-dimension read-models: pure life math + scored dimensions (DB mocked)."""
from datetime import date

from app.services import dimensions as dim
from app.services.common import DAYS_PER_YEAR
from conftest import patch_query


def test_life_track_is_pure_and_correct():
    p = {"birthdate": date(1999, 12, 15), "life_expectancy_years": 80}
    today = date(2026, 6, 23)
    lt = dim.life_track(p, today)
    assert lt["days_alive"] == (today - date(1999, 12, 15)).days
    assert lt["life_expectancy_years"] == 80
    assert lt["weeks_total"] == 80 * 52
    assert lt["thirtieth_birthday"] == "2029-12-15"
    assert lt["days_to_30"] == (date(2029, 12, 15) - today).days
    assert 0 <= lt["life_lived_pct"] <= 100


def test_life_track_no_birthdate():
    assert dim.life_track({}, date(2026, 6, 23)) == {}


def test_financial_dimension(monkeypatch):
    debts = [{"balance": 1000, "apr": 20, "utilization_pct": 50}]
    totals = {"total_debt": 1000, "total_min": 50, "ann_int": 200, "mo_int": 16.67}
    patch_query(monkeypatch, "app.services.dimensions", [debts, [totals]])
    out = dim.financial_dimension({"current_income": 0, "remittance_pct": 0},
                                  income={"has_jobs": False})
    assert 0 <= out["score"] <= 100
    assert out["band"] in {"strong", "fair", "at risk", "critical"}
    assert out["total_debt"] == 1000
    assert set(out["components"]) == {"utilization", "coverage", "interest"}
    assert out["weighted_card_utilization_pct"] == 50.0


def test_visa_dimension_penalizes_blocked(monkeypatch):
    items = [{"title": "I-765", "due_date": "2026-07-06", "status": "blocked",
              "priority": 1, "blocked_on": "STEM I-20", "days_left": 10}]
    patch_query(monkeypatch, "app.services.dimensions", [items])
    out = dim.visa_dimension({"visa_type": "F-1", "work_auth_until": None})
    assert out["blocked_count"] == 1
    assert out["open_count"] == 1
    assert out["score"] == 60  # 100 - 40 (blocked, <=14 days)


def test_career_dimension(monkeypatch):
    apps = [{"status": "applied", "age_days": 5, "applied_date": "2026-06-18"},
            {"status": "interview", "age_days": 40, "applied_date": "2026-05-14"}]
    patch_query(monkeypatch, "app.services.dimensions", [apps])
    out = dim.career_dimension({"target_salary": 120000, "current_income": 38400})
    assert out["started"] is True
    assert out["total_applications"] == 2
    assert out["applications_last_30d"] == 1
    assert out["interviews"] == 1
    assert set(out["funnel"]) >= {"applied", "interview", "offer"}


def test_work_income_hourly(monkeypatch):
    jobs = [{"id": "j1", "kind": "hourly", "status": "active", "employer": "Cafe",
             "role": "barista", "hourly_rate": 15, "remittance_pct": 0, "annual_salary": None}]
    sched = [{"job_id": "j1", "wk_hours": 20}]
    patch_query(monkeypatch, "app.services.dimensions", [jobs, sched])
    out = dim.work_income()
    assert out["has_jobs"] is True
    assert out["weekly_gross"] == 300.0          # 20h * $15
    assert out["monthly_takehome"] > 0
    assert len(out["jobs"]) == 1


def test_goal_dimension(monkeypatch):
    goals = [{"title": "Aadyon", "category": "career", "milestone_date": "2029-12-15",
              "progress_pct": 50, "notes": None}]
    patch_query(monkeypatch, "app.services.dimensions", [goals, []])
    out = dim.goal_dimension({"goal_title": "Aadyon"},
                             life={"age_progress_to_30_pct": 80.0, "days_to_30": 1000})
    assert out["score"] == 50
    assert out["pace_gap_pct"] == -30.0          # 50 progress - 80 time used

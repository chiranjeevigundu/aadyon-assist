"""Digital Me orchestrator: composes dimensions + the overall composite score."""
from app.services import digital_me
from app.services import dimensions as dim


def test_digital_me_payload_and_composite(monkeypatch):
    monkeypatch.setattr(dim, "profile", lambda: {"full_name": "Test User"})
    monkeypatch.setattr(dim, "life_track", lambda p, today: {"days_alive": 1})
    monkeypatch.setattr(dim, "work_income", lambda: {"has_jobs": False})
    monkeypatch.setattr(dim, "financial_dimension", lambda p, income: {"score": 40})
    monkeypatch.setattr(dim, "visa_dimension", lambda p: {"score": 60})
    monkeypatch.setattr(dim, "career_dimension", lambda p: {"score": 20})
    monkeypatch.setattr(dim, "goal_dimension", lambda p, life: {"score": 50})

    out = digital_me.digital_me()
    # 0.35*40 + 0.30*60 + 0.25*20 + 0.10*50 = 14 + 18 + 5 + 5 = 42
    assert out["overall"]["score"] == 42
    assert out["overall"]["band"] == "fair"
    assert set(out) >= {"as_of", "profile", "life", "income", "overall", "dimensions"}
    assert set(out["dimensions"]) == {"financial", "visa", "career", "goal"}
    assert out["profile"]["full_name"] == "Test User"

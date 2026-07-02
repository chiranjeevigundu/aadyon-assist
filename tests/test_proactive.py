from datetime import date, timedelta
from app.services import proactive

def test_evaluate_rules_no_users(monkeypatch):
    monkeypatch.setattr(proactive, "active_user_ids", lambda: [])
    assert proactive.evaluate_rules() == "Sent alerts to 0 user(s): none"

def test_evaluate_rules_no_alerts(monkeypatch):
    monkeypatch.setattr(proactive, "active_user_ids", lambda: ["u1"])
    def mock_query(sql, params=()):
        return []
    monkeypatch.setattr(proactive, "query", mock_query)
    
    # We also need to mock set_current_user to not hit db/context issues
    monkeypatch.setattr(proactive, "set_current_user", lambda u: None)
    
    assert proactive.evaluate_rules() == "Sent alerts to 0 user(s): none"

def test_evaluate_rules_with_alerts(monkeypatch):
    monkeypatch.setattr(proactive, "active_user_ids", lambda: ["user123456789"])
    
    def mock_query(sql, params=()):
        if "deadlines" in sql:
            return [{"title": "Visa Renewal", "due_date": date.today() + timedelta(days=2)}]
        if "bank_accounts" in sql:
            return [{"institution": "Chase", "balance": 45.0}]
        return []
        
    monkeypatch.setattr(proactive, "query", mock_query)
    monkeypatch.setattr(proactive, "set_current_user", lambda u: None)
    
    pushed = []
    def mock_push_alert(uid, md, title):
        pushed.append((uid, md, title))
        return True
        
    monkeypatch.setattr(proactive, "push_alert", mock_push_alert)
    
    res = proactive.evaluate_rules()
    assert res == "Sent alerts to 1 user(s): user1234"
    assert len(pushed) == 1
    uid, md, title = pushed[0]
    assert uid == "user123456789"
    assert "Visa Renewal" in md
    assert "Chase: $45.00" in md

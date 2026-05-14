from backend.app.enterprise.audit import _safe_json, record_event

class FakeDB:
    def __init__(self): self.calls=[]; self.committed=False
    def execute(self, sql, params): self.calls.append((str(sql), params))
    def commit(self): self.committed=True

def test_audit_sanitizes_sensitive_fields():
    payload = _safe_json({"password": "secret", "amount": 10, "refresh_token": "abc"})
    assert "secret" not in payload
    assert "abc" not in payload
    assert "***" in payload

def test_record_event_contains_enterprise_fields():
    db = FakeDB()
    record_event(db, organization_id="org-a", user_id="u1", action="expense.created", entity_type="expense", entity_id="1", before={"x":1}, after={"x":2}, request_id="req-1", commit=True)
    sql, params = db.calls[0]
    assert "audit_logs" in sql
    assert params["organization_id"] == "org-a"
    assert params["request_id"] == "req-1"
    assert db.committed is True

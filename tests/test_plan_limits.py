from backend.app.services.plan_limits_service import PlanLimitExceeded, ensure_feature_allowed, get_plan_limits, plan_limit_payload

class FakeScalar:
    def __init__(self, value): self.value = value
    def scalar(self): return self.value
class FakeDB:
    def __init__(self, count): self.count = count; self.queries=[]
    def execute(self, sql, params):
        self.queries.append((str(sql), params))
        return FakeScalar(self.count)

def test_free_plan_has_basic_limits():
    limits = get_plan_limits("free")
    assert limits["users"] >= 1
    assert limits["advanced_ai"] is False

def test_enterprise_limits_are_high():
    assert get_plan_limits("enterprise")["users"] > get_plan_limits("free")["users"]

def test_limit_blocks_when_reached():
    db = FakeDB(count=get_plan_limits("free")["accounts"])
    try:
        ensure_feature_allowed(db, organization_id="org-a", plan="free", feature="accounts")
    except PlanLimitExceeded:
        pass
    else:
        raise AssertionError("limit should block")
    assert "organization_id" in db.queries[0][0]
    assert db.queries[0][1]["organization_id"] == "org-a"

def test_plan_limit_payload_is_upgrade_friendly():
    payload = plan_limit_payload("free", "users", "blocked")
    assert payload["upgrade_required"] is True
    assert payload["detail"] == "Plan limit reached"

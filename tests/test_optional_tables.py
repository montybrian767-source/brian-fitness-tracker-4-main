from services import supabase_service


class _FakeResponse:
    def __init__(self, count=0):
        self.count = count


class _FakeTable:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "coaching_feedback":
            raise RuntimeError("relation coaching_feedback does not exist")
        return _FakeResponse(count=3)


class _FakeClient:
    def table(self, table_name):
        return _FakeTable(table_name)


def test_optional_table_missing_does_not_raise(monkeypatch):
    monkeypatch.setattr(supabase_service, "connect_supabase", lambda: (_FakeClient(), None))

    status, err = supabase_service.get_database_feature_status()

    assert err is None
    assert "Coaching Feedback" in status
    assert status["Coaching Feedback"]["state"] == "Missing"
    assert status["Workouts"]["state"] == "Ready"

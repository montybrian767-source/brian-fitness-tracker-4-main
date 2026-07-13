from services import supabase_service


def test_normalize_health_check_legacy_two_tuple():
    payload = supabase_service.normalize_health_check_result((True, "Supabase connected"))

    assert payload["ok"] is True
    assert payload["message"] == "Supabase connected"
    assert payload["latency_ms"] is None
    assert payload["workouts_ready"] is False
    assert payload["cardio_ready"] is False
    assert payload["apple_ready"] is False


def test_normalize_health_check_six_tuple():
    payload = supabase_service.normalize_health_check_result(
        (True, "Connected", 42.5, True, True, False)
    )

    assert payload["ok"] is True
    assert payload["message"] == "Connected"
    assert payload["latency_ms"] == 42.5
    assert payload["workouts_ready"] is True
    assert payload["cardio_ready"] is True
    assert payload["apple_ready"] is False


def test_normalize_health_check_dict_result():
    payload = supabase_service.normalize_health_check_result(
        {
            "ok": True,
            "message": "Supabase connected",
            "latency_ms": 12,
            "workouts_ready": True,
            "cardio_ready": True,
            "apple_ready": True,
            "workout_count": 99,
        }
    )

    assert payload["ok"] is True
    assert payload["message"] == "Supabase connected"
    assert payload["latency_ms"] == 12
    assert payload["workout_count"] == 99


def test_normalize_health_check_exception_result():
    payload = supabase_service.normalize_health_check_result(RuntimeError("boom"))

    assert payload["ok"] is False
    assert payload["message"] == "Health check failed."
    assert "boom" in payload["error"]


def test_normalize_health_check_malformed_result():
    payload = supabase_service.normalize_health_check_result("bad-result")

    assert payload["ok"] is False
    assert payload["message"] == "Health check returned an invalid result."
    assert payload["workouts_ready"] is False
    assert payload["cardio_ready"] is False
    assert payload["apple_ready"] is False


def test_safe_health_check_handles_failure(monkeypatch):
    def _raise_failure():
        raise ValueError("network down")

    monkeypatch.setattr(supabase_service, "health_check", _raise_failure)

    payload = supabase_service.safe_health_check()

    assert payload["ok"] is False
    assert payload["message"] == "Health check failed."
    assert "network down" in payload["error"]

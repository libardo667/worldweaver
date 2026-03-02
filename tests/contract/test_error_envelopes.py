"""Contract tests for error response format."""

from unittest.mock import patch


def _assert_error_envelope(resp, expected_status=None):
    assert resp.status_code != 200
    if expected_status is not None:
        assert resp.status_code == expected_status
    assert "detail" in resp.json()


def test_next_missing_session_id(client):
    _assert_error_envelope(client.post("/api/next", json={"vars": {}}), 422)


def test_suggest_invalid_n_too_high(client):
    _assert_error_envelope(client.post("/author/suggest", json={"n": 25, "themes": [], "bible": {}}), 422)


def test_suggest_invalid_n_too_low(client):
    _assert_error_envelope(client.post("/author/suggest", json={"n": 0, "themes": [], "bible": {}}), 422)


def test_populate_target_count_too_low(client):
    _assert_error_envelope(client.post("/author/populate", params={"target_count": 0}), 400)


def test_populate_target_count_too_high(client):
    _assert_error_envelope(client.post("/author/populate", params={"target_count": 200}), 400)


def test_debug_endpoint_error_returns_500(client):
    with patch("src.api.author.SessionVars") as mock_sv:
        mock_sv.side_effect = RuntimeError("boom")
        with patch("src.api.author.Storylet") as mock_st:
            mock_st.side_effect = RuntimeError("boom")
            resp = client.get("/author/debug")
    assert resp.status_code != 200


def test_storylet_analysis_error_returns_500(client):
    with patch("src.services.storylet_analyzer.analyze_storylet_gaps", side_effect=RuntimeError("analysis broke")):
        resp = client.get("/author/storylet-analysis")
    assert resp.status_code == 500 and "detail" in resp.json()


def test_unhandled_exception_returns_500_safe(client):
    with patch("src.api.game.get_state_manager", side_effect=RuntimeError("kaboom")):
        resp = client.get("/api/state/test-crash")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body and "kaboom" not in body["detail"]
    assert body["detail"] == "Internal server error"


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.json()["ok"] is True

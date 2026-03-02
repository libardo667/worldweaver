"""Contract tests for error response format.

Verifies that all error responses use proper HTTP status codes (never 200)
and return a ``{"detail": ...}`` body consistent with FastAPI conventions.
"""

import os
import tempfile

# Isolated temp DB — set before any app imports.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DW_DB_PATH"] = _tmp_db.name

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.database import create_tables  # noqa: E402

create_tables()

from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _assert_error_envelope(resp, expected_status: int | None = None):
    """Assert the response is an error with a ``detail`` field."""
    assert resp.status_code != 200, (
        f"Expected error status but got 200: {resp.json()}"
    )
    if expected_status is not None:
        assert resp.status_code == expected_status
    body = resp.json()
    assert "detail" in body, f"Error body missing 'detail': {body}"


# ------------------------------------------------------------------
# 1. Pydantic validation errors (FastAPI auto-generates 422)
# ------------------------------------------------------------------

def test_next_missing_session_id():
    """POST /api/next without required session_id → 422."""
    resp = client.post("/api/next", json={"vars": {}})
    _assert_error_envelope(resp, 422)


def test_suggest_invalid_n_too_high():
    """POST /author/suggest with n > 20 → 422 (Pydantic le=20)."""
    resp = client.post(
        "/author/suggest",
        json={"n": 25, "themes": [], "bible": {}},
    )
    _assert_error_envelope(resp, 422)


def test_suggest_invalid_n_too_low():
    """POST /author/suggest with n < 1 → 422 (Pydantic ge=1)."""
    resp = client.post(
        "/author/suggest",
        json={"n": 0, "themes": [], "bible": {}},
    )
    _assert_error_envelope(resp, 422)


def test_populate_target_count_too_low():
    """POST /author/populate with target_count < 1 → 400."""
    resp = client.post("/author/populate", params={"target_count": 0})
    _assert_error_envelope(resp, 400)


def test_populate_target_count_too_high():
    """POST /author/populate with target_count > 100 → 400."""
    resp = client.post("/author/populate", params={"target_count": 200})
    _assert_error_envelope(resp, 400)


# ------------------------------------------------------------------
# 2. Fixed endpoints that previously returned 200 on error
# ------------------------------------------------------------------

def test_debug_endpoint_error_returns_500():
    """GET /author/debug should return 500 (not 200) on internal error."""
    with patch("src.api.author.SessionVars") as mock_sv:
        mock_sv.side_effect = RuntimeError("boom")
        # The query(SessionVars) call will raise
        with patch("src.api.author.Storylet") as mock_st:
            mock_st.side_effect = RuntimeError("boom")
            resp = client.get("/author/debug")
    # Should NOT be 200 anymore
    assert resp.status_code != 200


def test_storylet_analysis_error_returns_500():
    """GET /author/storylet-analysis should return 500 on internal error."""
    with patch(
        "src.services.storylet_analyzer.analyze_storylet_gaps",
        side_effect=RuntimeError("analysis broke"),
    ):
        resp = client.get("/author/storylet-analysis")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body


# ------------------------------------------------------------------
# 3. Global unhandled exception handler
# ------------------------------------------------------------------

def test_unhandled_exception_returns_500_safe():
    """An unhandled exception should return 500 with safe message (no traceback)."""
    with patch(
        "src.api.game.get_state_manager",
        side_effect=RuntimeError("unexpected kaboom"),
    ):
        resp = client.get("/api/state/test-crash")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    # Must NOT leak the traceback or raw exception message.
    assert "kaboom" not in body["detail"]
    assert body["detail"] == "Internal server error"


# ------------------------------------------------------------------
# 4. Control — success responses are unaffected
# ------------------------------------------------------------------

def test_health_returns_200():
    """GET /health should still return 200 on success."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

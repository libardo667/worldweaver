"""Tests for main FastAPI application health endpoint."""

from datetime import datetime, timezone


def test_health_check_endpoint(client):
    """GET /health returns {'ok': True} and valid ISO 8601 UTC timestamp."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "time" in data
    timestamp_str = data["time"]
    assert timestamp_str.endswith("Z"), "Timestamp should end with 'Z' for UTC"
    timestamp_without_z = timestamp_str[:-1]
    parsed_time = datetime.fromisoformat(timestamp_without_z)
    now = datetime.now(timezone.utc)
    time_diff = abs((now - parsed_time).total_seconds())
    assert time_diff < 60, "Health check timestamp should be recent"


def test_health_check_response_content_type(client):
    """Health check returns JSON content type."""
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"


def test_health_check_consistent_format(client):
    """Health check returns consistent response format across multiple calls."""
    for _ in range(3):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert isinstance(data["time"], str)
        assert data["time"].endswith("Z")


def test_openapi_info_title_matches_worldweaver_backend(client):
    """OpenAPI title reflects the product name used across backend surfaces."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "WorldWeaver Backend"

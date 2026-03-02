"""Tests for world memory API endpoints."""


class TestWorldHistoryEndpoint:

    def test_empty_history(self, client):
        resp = client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["count"] == 0

    def test_history_after_next(self, seeded_client):
        # Fire a storylet via POST /api/next
        resp = seeded_client.post(
            "/api/next", json={"session_id": "world-test", "vars": {}}
        )
        assert resp.status_code == 200

        # Check world history
        resp = seeded_client.get("/api/world/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["events"][0]["event_type"] == "storylet_fired"

    def test_history_with_session_filter(self, seeded_client):
        seeded_client.post(
            "/api/next", json={"session_id": "sess-a", "vars": {}}
        )
        resp = seeded_client.get("/api/world/history?session_id=sess-a")
        assert resp.status_code == 200
        for event in resp.json()["events"]:
            assert event["session_id"] == "sess-a"


class TestWorldFactsEndpoint:

    def test_facts_returns_shape(self, client):
        resp = client.get("/api/world/facts?query=bridge")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "facts" in data
        assert "count" in data
        assert data["query"] == "bridge"

    def test_facts_missing_query(self, client):
        resp = client.get("/api/world/facts")
        assert resp.status_code == 422


class TestWorldGraphEndpoints:

    def test_graph_facts_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-api", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-api",
                "action": "I break the bridge supports",
            },
        )

        resp = seeded_client.get("/api/world/graph/facts?query=bridge&session_id=graph-api")
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "facts" in data
        assert "count" in data

    def test_graph_neighborhood_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-neighborhood", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-neighborhood",
                "action": "I damage the bridge",
            },
        )

        resp = seeded_client.get("/api/world/graph/neighborhood?node=bridge")
        assert resp.status_code == 200
        data = resp.json()
        assert "node" in data
        assert "edges" in data
        assert "facts" in data
        assert "count" in data

    def test_graph_location_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "graph-location", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "graph-location",
                "action": "I destroy the bridge",
            },
        )

        resp = seeded_client.get("/api/world/graph/location/bridge?session_id=graph-location")
        assert resp.status_code == 200
        data = resp.json()
        assert data["location"] == "bridge"
        assert "facts" in data
        assert "count" in data


class TestWorldProjectionEndpoint:

    def test_projection_returns_shape(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "projection-api", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "projection-api",
                "action": "I destroy the old bridge",
            },
        )

        resp = seeded_client.get("/api/world/projection")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "count" in data
        assert isinstance(data["entries"], list)
        if data["entries"]:
            first = data["entries"][0]
            assert "source_event_id" in first
            assert "source_event_type" in first
            assert "source_event_summary" in first
            assert "source_event_created_at" in first

    def test_projection_prefix_filter(self, seeded_client):
        seeded_client.post("/api/next", json={"session_id": "projection-prefix", "vars": {}})
        seeded_client.post(
            "/api/action",
            json={
                "session_id": "projection-prefix",
                "action": "I damage the bridge",
            },
        )

        resp = seeded_client.get("/api/world/projection?prefix=variables.")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prefix"] == "variables."

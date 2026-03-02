"""Tests for author API input validation."""

import pytest
from src.models.schemas import SuggestReq, GenerateStoryletRequest, WorldDescription


class TestAuthorInputValidation:

    def test_suggest_req_valid_n_parameter(self):
        for req in [SuggestReq(n=1), SuggestReq(n=10), SuggestReq(n=20)]:
            assert 1 <= req.n <= 20

    def test_suggest_req_invalid_n_parameter(self):
        for val in [0, -5, 25, 100]:
            with pytest.raises(ValueError):
                SuggestReq(n=val)

    def test_generate_storylet_request_valid_count(self):
        for req in [GenerateStoryletRequest(count=1), GenerateStoryletRequest(count=8), GenerateStoryletRequest(count=15)]:
            assert 1 <= req.count <= 15

    def test_generate_storylet_request_invalid_count(self):
        for val in [0, -3, 20, 50]:
            with pytest.raises(ValueError):
                GenerateStoryletRequest(count=val)

    def test_world_description_storylet_count_validation(self):
        assert WorldDescription(description="A magical realm", theme="fantasy", storylet_count=25).storylet_count == 25
        for val in [3, 75]:
            with pytest.raises(ValueError):
                WorldDescription(description="A magical realm", theme="fantasy", storylet_count=val)

    def test_populate_endpoint_target_count_validation(self, client):
        resp = client.post("/author/populate", params={"target_count": 0})
        assert resp.status_code == 400
        assert "target_count must be at least 1" in resp.json()["detail"]
        resp = client.post("/author/populate", params={"target_count": 150})
        assert resp.status_code == 400
        assert "target_count cannot exceed 100" in resp.json()["detail"]

    def test_suggest_endpoint_with_invalid_n(self, client):
        response = client.post("/author/suggest", json={"n": 25, "themes": [], "bible": {}})
        assert response.status_code == 422

    def test_default_values_are_valid(self):
        assert SuggestReq().n == 3
        assert GenerateStoryletRequest().count == 3
        wd = WorldDescription(description="A test world", theme="fantasy")
        assert wd.storylet_count == 15
        assert wd.confirm_delete is False

    def test_edge_case_boundary_values(self):
        assert SuggestReq(n=1).n == 1
        assert SuggestReq(n=20).n == 20
        assert GenerateStoryletRequest(count=1).count == 1
        assert GenerateStoryletRequest(count=15).count == 15
        assert WorldDescription(description="Minimum length realm", theme="test", storylet_count=5).storylet_count == 5
        assert WorldDescription(description="Maximum length realm", theme="test", storylet_count=50).storylet_count == 50

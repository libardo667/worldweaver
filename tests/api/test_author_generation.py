"""Author generation endpoint behavior tests."""

from unittest.mock import patch


def _author_storylet(title: str) -> dict:
    return {
        "title": title,
        "text_template": f"{title} text",
        "requires": {"location": "start"},
        "choices": [{"label": "Continue", "set": {}}],
        "weight": 1.0,
    }


def test_generate_intelligent_includes_operation_receipt(client):
    generated = [_author_storylet("intelligent-receipt")]
    with patch(
        "src.services.llm_service.generate_learning_enhanced_storylets",
        return_value=generated,
    ), patch(
        "src.services.embedding_service.embed_all_storylets",
        return_value=0,
    ):
        response = client.post("/author/generate-intelligent", json={"count": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["storylets"]
    assert "operation_receipt" in payload
    receipt = payload["operation_receipt"]
    assert receipt["operation"] == "author-generate-intelligent"
    assert receipt["status"] in {"completed", "completed_with_warnings"}
    phase_names = {phase["name"] for phase in receipt.get("phases", [])}
    assert "core_transaction" in phase_names
    assert "insert_storylets" in phase_names


def test_populate_includes_operation_receipt(client):
    with patch(
        "src.api.author.populate._generate_population_candidates",
        return_value=[_author_storylet("populate-receipt")],
    ), patch(
        "src.services.embedding_service.embed_all_storylets",
        return_value=0,
    ):
        response = client.post("/author/populate", params={"target_count": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["added"] >= 1
    assert "operation_receipt" in payload
    assert payload["operation_receipt"]["operation"] == "author-populate"

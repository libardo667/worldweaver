"""Integration coverage for transaction-safe author mutation flows."""

from unittest.mock import patch

from src.models import Storylet
from tests.integration_helpers import assert_ok_response, assert_status


def _world_storylet(title: str) -> dict:
    return {
        "title": title,
        "text": f"{title} narrative",
        "requires": {"location": "start"},
        "choices": [{"label": "Continue", "set": {}}],
        "weight": 1.0,
    }


def _starting_storylet() -> dict:
    return {
        "title": "world-start",
        "text": "You arrive at the beginning.",
        "choices": [{"label": "Continue", "set": {}}],
    }


def _intelligent_storylet() -> dict:
    return {
        "title": "intelligent-pipeline",
        "text_template": "A deliberate clue surfaces.",
        "requires": {"location": "start"},
        "choices": [{"label": "Continue", "set": {}}],
        "weight": 1.0,
    }


def test_world_generation_rolls_back_on_coordinate_assignment_failure(client, db_session):
    db_session.add(
        Storylet(
            title="preexisting-world-storylet",
            text_template="Existing world state",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
    )
    db_session.commit()
    baseline_count = db_session.query(Storylet).count()

    with (
        patch(
            "src.services.world_bootstrap_service.generate_world_storylets",
            return_value=[_world_storylet("generated-a"), _world_storylet("generated-b")],
        ),
        patch(
            "src.services.world_bootstrap_service.generate_starting_storylet",
            return_value=_starting_storylet(),
        ),
        patch(
            "src.services.storylet_ingest.assign_spatial_to_storylets",
            side_effect=RuntimeError("forced coordinate failure"),
        ),
        patch(
            "src.services.embedding_service.embed_all_storylets",
            return_value=0,
        ),
    ):
        response = client.post(
            "/author/generate-world",
            json={
                "description": "A brittle world under repair.",
                "theme": "transaction-test",
                "confirm_delete": True,
            },
        )

    assert_status(response, 500)
    payload = response.json()
    assert isinstance(payload.get("detail"), dict)
    receipt = payload["detail"].get("operation_receipt", {})
    assert receipt.get("status") == "failed"
    assert db_session.query(Storylet).count() == baseline_count
    assert db_session.query(Storylet).filter(Storylet.title == "preexisting-world-storylet").count() == 1


def test_auto_improvement_failure_does_not_rollback_core_author_writes(client, db_session):
    with (
        patch(
            "src.services.llm_service.generate_learning_enhanced_storylets",
            return_value=[_intelligent_storylet()],
        ),
        patch(
            "src.services.embedding_service.embed_all_storylets",
            return_value=0,
        ),
        patch(
            "src.services.storylet_ingest.run_auto_improvements",
            side_effect=RuntimeError("forced auto-improvement failure"),
        ),
    ):
        response = client.post("/author/generate-intelligent", json={"count": 1})

    assert_ok_response(response)
    payload = response.json()
    assert payload["storylets"]
    assert db_session.query(Storylet).filter(Storylet.title == "intelligent-pipeline").count() == 1
    receipt = payload.get("operation_receipt", {})
    assert receipt.get("status") == "completed_with_warnings"
    phases = {phase["name"]: phase for phase in receipt.get("phases", [])}
    assert phases["auto_improvement"]["status"] == "failed"

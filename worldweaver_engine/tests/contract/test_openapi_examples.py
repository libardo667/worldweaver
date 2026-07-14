"""Contract tests for OpenAPI examples on core game schemas."""

from typing import Dict, Type

from src.models.schemas import (
    ActionRequest,
    ActionResponse,
)

# NextReq/NextResp are no longer exposed as route schemas (the /api/next endpoint
# was removed in Major 69); only the /api/action contract is asserted here.
CORE_GAME_SCHEMAS: Dict[str, Type] = {
    "ActionRequest": ActionRequest,
    "ActionResponse": ActionResponse,
}


def _model_example(model_cls: Type) -> dict:
    raw_extra = model_cls.model_config.get("json_schema_extra", {})
    assert isinstance(raw_extra, dict)
    raw_example = raw_extra.get("example")
    assert isinstance(raw_example, dict)
    return raw_example


def test_openapi_includes_core_game_schema_examples(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema_map = response.json()["components"]["schemas"]

    for model_name, model_cls in CORE_GAME_SCHEMAS.items():
        expected_example = _model_example(model_cls)
        schema_payload = schema_map.get(model_name)
        assert schema_payload is not None
        assert schema_payload.get("example") == expected_example


def test_core_game_examples_validate_against_models():
    for model_cls in CORE_GAME_SCHEMAS.values():
        model_cls.model_validate(_model_example(model_cls))


def test_request_examples_work_as_smoke_payloads(seeded_client):
    action_payload = dict(_model_example(ActionRequest))
    action_response = seeded_client.post("/api/action", json=action_payload)
    assert action_response.status_code == 200

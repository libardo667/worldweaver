"""The public contract no longer advertises model-interpreted action schemas."""


def test_openapi_does_not_expose_freeform_action_models(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema_map = response.json().get("components", {}).get("schemas", {})
    assert "ActionRequest" not in schema_map
    assert "ActionResponse" not in schema_map

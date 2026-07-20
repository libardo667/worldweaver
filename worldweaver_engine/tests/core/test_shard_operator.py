import argparse
import json

from scripts import shard_operator


def test_node_admission_accepts_a_public_key_that_begins_with_a_dash(
    tmp_path, monkeypatch
) -> None:
    public_key = "-" + ("A" * 42)
    descriptor = tmp_path / "node.json"
    descriptor.write_text(
        json.dumps(
            {
                "schema": "worldweaver.node",
                "schema_version": 1,
                "node_id": "dash-key-node",
                "shard_type": "city",
                "city_id": "test_city",
                "public_key": public_key,
            }
        ),
        encoding="utf-8",
    )
    compose_arguments: list[str] = []
    monkeypatch.setattr(shard_operator, "_read_env", lambda: {"SHARD_TYPE": "world"})
    monkeypatch.setattr(
        shard_operator,
        "_services",
        lambda *, running_only=False: {"backend"},
    )
    monkeypatch.setattr(
        shard_operator,
        "_compose",
        lambda *arguments: compose_arguments.extend(arguments),
    )

    result = shard_operator.command_node(
        argparse.Namespace(
            node_action="admit",
            descriptor=str(descriptor),
            reason="Known steward",
        )
    )

    assert result == 0
    assert f"--public-key={public_key}" in compose_arguments
    assert "--public-key" not in compose_arguments

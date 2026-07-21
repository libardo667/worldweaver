# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.world.client import scene_data_from_payload


def test_scene_payload_parser_is_shared_with_transport_free_gym_adapters():
    scene = scene_data_from_payload(
        {
            "location": "Willow Court",
            "role": "Mara",
            "present": [
                {
                    "actor_id": "actor-ivo",
                    "session_id": "ivo-20260720-120000",
                    "name": "Ivo",
                    "role": "Ivo",
                    "last_action": "",
                    "last_seen": "2026-07-20T12:00:00",
                }
            ],
            "ambient_presence": [],
            "traces_here": [],
            "recent_events_here": [],
            "location_graph": {
                "nodes": [{"key": "willow", "name": "Willow Court"}],
                "edges": [],
            },
        },
        session_id="mara-20260720-120000",
    )

    assert scene.session_id == "mara-20260720-120000"
    assert scene.location == "Willow Court"
    assert [(person.actor_id, person.name) for person in scene.present] == [
        ("actor-ivo", "Ivo")
    ]
    assert scene.location_graph["nodes"][0]["name"] == "Willow Court"

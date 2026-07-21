"""Integration tests for core game API endpoints."""

from datetime import datetime, timedelta, timezone
import json
from urllib.parse import quote

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from src.models import (
    LocationChat,
    ResidentAuthority,
    ResidentRequestNonce,
    ResidentSessionAuthority,
    ResidentSessionRetirementReceipt,
    SessionVars,
    ShardTravelHandoff,
    WorldEvent,
)
from src.services.federation_identity import current_shard_id
from src.services.resident_authority import bind_resident_identity
from src.services.resident_protocol import (
    encoded_public_key,
    issue_runtime_certificate,
    signed_resident_request_headers,
)


class TestGameEndpoints:
    def test_private_state_and_public_maintenance_routes_do_not_exist(
        self, seeded_client
    ):
        requests = [
            ("get", "/api/state/never-seen", None),
            ("get", "/api/state/never-seen/vars", None),
            ("post", "/api/state/never-seen/vars", {"vars": {"private": True}}),
            ("get", "/api/state/never-seen/identity-growth", None),
            (
                "post",
                "/api/state/never-seen/identity-growth",
                {"growth_text": "rewrite"},
            ),
            ("post", "/api/cleanup-sessions", None),
            ("post", "/api/session/prune-duplicate-agents", {}),
            ("post", "/api/reset-session", None),
        ]

        for method, path, payload in requests:
            response = seeded_client.request(method.upper(), path, json=payload)
            assert response.status_code == 404, path

        openapi_paths = seeded_client.get("/openapi.json").json()["paths"]
        assert all(path not in openapi_paths for _, path, _ in requests)

    def test_dev_hard_reset_is_absent_when_disabled(self, seeded_client, monkeypatch):
        monkeypatch.setattr("src.api.game.state.settings.enable_dev_reset", False)
        response = seeded_client.post("/api/dev/hard-reset")
        assert response.status_code == 404

    def test_session_bootstrap_persists_resident_actor_id(
        self, seeded_client, seeded_world_id, db_session
    ):
        session_id = "resident-bootstrap-session"
        actor_id = "resident-actor-123"

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": actor_id,
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": seeded_world_id,
            },
        )
        assert response.status_code == 200

        sv = db_session.get(SessionVars, session_id)
        assert sv is not None
        assert sv.actor_id == actor_id
        assert sv.vars["variables"]["name"] == "Test Resident"
        bootstrap_event = (
            db_session.query(WorldEvent)
            .filter(
                WorldEvent.session_id == session_id,
                WorldEvent.event_type == "session_bootstrap",
            )
            .one()
        )
        assert bootstrap_event.summary.startswith("Test Resident arrived at ")
        assert bootstrap_event.embedding is not None
        assert (
            bootstrap_event.world_state_delta["__action_meta__"]["surface"]
            == "session_bootstrap"
        )

    def test_pre_admitted_resident_can_bootstrap_one_generation_with_exact_proof(
        self, seeded_client, seeded_world_id, db_session
    ):
        actor_id = "signed-resident-actor"
        session_id = "signed-resident-session"
        identity_private = Ed25519PrivateKey.generate()
        runtime_private = Ed25519PrivateKey.generate()
        bind_resident_identity(
            db_session,
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-resident-actor",
            identity_public_key=encoded_public_key(identity_private.public_key()),
        )
        db_session.commit()
        certificate = issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=runtime_private.public_key(),
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-resident-actor",
            runtime_generation=1,
            audience=current_shard_id(),
            scopes=["session.act", "session.bootstrap"],
        )
        payload = {
            "session_id": session_id,
            "actor_id": actor_id,
            "world_theme": "quiet harbor",
            "player_role": "Signed Resident",
            "bootstrap_source": "worldweaver-agent",
            "world_id": seeded_world_id,
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target="/api/session/bootstrap/resident",
            body=body,
            nonce="signed-bootstrap-once",
        )
        headers["Content-Type"] = "application/json"

        response = seeded_client.post(
            "/api/session/bootstrap/resident",
            content=body,
            headers=headers,
        )

        assert response.status_code == 200, response.text
        session = db_session.get(SessionVars, session_id)
        binding = db_session.get(ResidentSessionAuthority, session_id)
        assert session is not None
        assert session.actor_id == actor_id
        assert binding is not None
        assert binding.actor_id == actor_id
        assert binding.runtime_generation == 1

        replay = seeded_client.post(
            "/api/session/bootstrap/resident",
            content=body,
            headers=headers,
        )
        assert replay.status_code == 409
        assert replay.json()["detail"]["code"] == "session_id_in_use"

    def test_signed_resident_bootstrap_refuses_unsigned_traffic(
        self, seeded_client, seeded_world_id
    ):
        response = seeded_client.post(
            "/api/session/bootstrap/resident",
            json={
                "session_id": "unsigned-resident-session",
                "actor_id": "unsigned-resident-actor",
                "player_role": "Unsigned Resident",
                "world_id": seeded_world_id,
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "resident_proof_required"

    def test_signed_resident_session_requires_its_proof_to_leave(
        self, seeded_client, seeded_world_id, db_session
    ):
        actor_id = "signed-leave-actor"
        session_id = "signed-leave-session"
        identity_private = Ed25519PrivateKey.generate()
        runtime_private = Ed25519PrivateKey.generate()
        bind_resident_identity(
            db_session,
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-leave-actor",
            identity_public_key=encoded_public_key(identity_private.public_key()),
        )
        db_session.commit()
        certificate = issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=runtime_private.public_key(),
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-leave-actor",
            runtime_generation=1,
            audience=current_shard_id(),
            scopes=["session.bootstrap", "session.lifecycle"],
        )
        bootstrap_payload = {
            "session_id": session_id,
            "actor_id": actor_id,
            "player_role": "Signed Leaver",
            "world_id": seeded_world_id,
        }
        bootstrap_body = json.dumps(bootstrap_payload, separators=(",", ":")).encode(
            "utf-8"
        )
        bootstrap_headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target="/api/session/bootstrap/resident",
            body=bootstrap_body,
            nonce="signed-leave-bootstrap",
        )
        bootstrap_headers["Content-Type"] = "application/json"
        assert (
            seeded_client.post(
                "/api/session/bootstrap/resident",
                content=bootstrap_body,
                headers=bootstrap_headers,
            ).status_code
            == 200
        )

        anonymous = seeded_client.post(
            "/api/session/leave", json={"session_id": session_id}
        )
        assert anonymous.status_code == 401
        assert anonymous.json()["detail"]["code"] == "actor_proof_required"
        assert db_session.get(SessionVars, session_id) is not None

        leave_payload = {
            "session_id": session_id,
            "transition_id": "signed-leave-transition",
        }
        leave_body = json.dumps(leave_payload, separators=(",", ":")).encode("utf-8")
        leave_headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target="/api/session/leave",
            body=leave_body,
            nonce="signed-leave-once",
        )
        leave_headers["Content-Type"] = "application/json"
        left = seeded_client.post(
            "/api/session/leave",
            content=leave_body,
            headers=leave_headers,
        )

        assert left.status_code == 200, left.text
        assert left.json()["transition_id"] == "signed-leave-transition"
        assert left.json()["actor_id"] == actor_id
        assert left.json()["runtime_generation"] == 1
        assert db_session.get(SessionVars, session_id) is None
        durable = db_session.get(
            ResidentSessionRetirementReceipt, "signed-leave-transition"
        )
        assert durable is not None
        assert durable.session_id == session_id
        assert durable.actor_id == actor_id
        assert durable.runtime_generation == 1

        def retry(payload, *, signer, runtime_certificate, nonce):
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers = signed_resident_request_headers(
                runtime_private_key=signer,
                certificate=runtime_certificate,
                method="POST",
                target="/api/session/leave",
                body=body,
                nonce=nonce,
            )
            headers["Content-Type"] = "application/json"
            return seeded_client.post(
                "/api/session/leave", content=body, headers=headers
            )

        replay = retry(
            leave_payload,
            signer=runtime_private,
            runtime_certificate=certificate,
            nonce="signed-leave-retry",
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == left.json()
        assert db_session.query(ResidentSessionRetirementReceipt).count() == 1

        wrong_transition = retry(
            {"session_id": session_id, "transition_id": "another-transition"},
            signer=runtime_private,
            runtime_certificate=certificate,
            nonce="signed-leave-wrong-transition",
        )
        assert wrong_transition.status_code == 409
        assert wrong_transition.json()["detail"]["code"] == (
            "departure_receipt_mismatch"
        )

        wrong_session = retry(
            {
                "session_id": "another-session",
                "transition_id": "signed-leave-transition",
            },
            signer=runtime_private,
            runtime_certificate=certificate,
            nonce="signed-leave-wrong-session",
        )
        assert wrong_session.status_code == 409
        assert wrong_session.json()["detail"]["code"] == "departure_receipt_mismatch"

        newer_runtime_private = Ed25519PrivateKey.generate()
        newer_certificate = issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=newer_runtime_private.public_key(),
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-leave-actor",
            runtime_generation=2,
            audience=current_shard_id(),
            scopes=["session.lifecycle"],
        )
        wrong_generation = retry(
            leave_payload,
            signer=newer_runtime_private,
            runtime_certificate=newer_certificate,
            nonce="signed-leave-wrong-generation",
        )
        assert wrong_generation.status_code == 401
        assert wrong_generation.json()["detail"]["code"] == "invalid_proof"

        other_identity_private = Ed25519PrivateKey.generate()
        other_runtime_private = Ed25519PrivateKey.generate()
        bind_resident_identity(
            db_session,
            actor_id="another-resident-actor",
            hearth_shard_id="hearth:another-resident-actor",
            identity_public_key=encoded_public_key(other_identity_private.public_key()),
        ).active_runtime_generation = 1
        db_session.commit()
        other_certificate = issue_runtime_certificate(
            identity_private_key=other_identity_private,
            runtime_public_key=other_runtime_private.public_key(),
            actor_id="another-resident-actor",
            hearth_shard_id="hearth:another-resident-actor",
            runtime_generation=1,
            audience=current_shard_id(),
            scopes=["session.lifecycle"],
        )
        wrong_actor = retry(
            leave_payload,
            signer=other_runtime_private,
            runtime_certificate=other_certificate,
            nonce="signed-leave-wrong-actor",
        )
        assert wrong_actor.status_code == 401
        assert wrong_actor.json()["detail"]["code"] == "invalid_proof"

    def test_signed_resident_session_requires_its_proof_to_speak(
        self, seeded_client, seeded_world_id, db_session
    ):
        actor_id = "signed-speaker-actor"
        session_id = "signed-speaker-session"
        identity_private = Ed25519PrivateKey.generate()
        runtime_private = Ed25519PrivateKey.generate()
        bind_resident_identity(
            db_session,
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-speaker-actor",
            identity_public_key=encoded_public_key(identity_private.public_key()),
        )
        db_session.commit()
        certificate = issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=runtime_private.public_key(),
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-speaker-actor",
            runtime_generation=1,
            audience=current_shard_id(),
            scopes=["session.act", "session.bootstrap"],
        )
        bootstrap_payload = {
            "session_id": session_id,
            "actor_id": actor_id,
            "player_role": "Signed Speaker",
            "world_id": seeded_world_id,
        }
        bootstrap_body = json.dumps(bootstrap_payload, separators=(",", ":")).encode(
            "utf-8"
        )
        bootstrap_headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target="/api/session/bootstrap/resident",
            body=bootstrap_body,
            nonce="signed-speaker-bootstrap",
        )
        bootstrap_headers["Content-Type"] = "application/json"
        assert (
            seeded_client.post(
                "/api/session/bootstrap/resident",
                content=bootstrap_body,
                headers=bootstrap_headers,
            ).status_code
            == 200
        )
        session = db_session.get(SessionVars, session_id)
        location = "Test Commons"
        vars_payload = dict(session.vars or {})
        variables = dict(vars_payload.get("variables") or {})
        variables["location"] = location
        vars_payload["variables"] = variables
        session.vars = vars_payload
        db_session.commit()
        path = f"/api/world/location/{quote(location, safe='')}/chat"
        chat_payload = {"session_id": session_id, "message": "I am here."}

        anonymous = seeded_client.post(path, json=chat_payload)
        assert anonymous.status_code == 401
        assert anonymous.json()["detail"]["code"] == "actor_proof_required"

        chat_body = json.dumps(chat_payload, separators=(",", ":")).encode("utf-8")
        chat_headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target=path,
            body=chat_body,
            nonce="signed-speaker-chat",
        )
        chat_headers["Content-Type"] = "application/json"
        spoken = seeded_client.post(path, content=chat_body, headers=chat_headers)

        assert spoken.status_code == 200, spoken.text
        stored = db_session.query(LocationChat).filter_by(session_id=session_id).one()
        assert stored.message == "I am here."

    def test_signed_resident_bootstrap_cannot_replace_an_existing_session(
        self, seeded_client, seeded_world_id, db_session
    ):
        actor_id = "signed-collision-actor"
        identity_private = Ed25519PrivateKey.generate()
        runtime_private = Ed25519PrivateKey.generate()
        bind_resident_identity(
            db_session,
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-collision-actor",
            identity_public_key=encoded_public_key(identity_private.public_key()),
        )
        db_session.add(
            SessionVars(
                session_id="occupied-session",
                actor_id="someone-else",
                vars={"name": "Still Here"},
            )
        )
        db_session.commit()
        certificate = issue_runtime_certificate(
            identity_private_key=identity_private,
            runtime_public_key=runtime_private.public_key(),
            actor_id=actor_id,
            hearth_shard_id="hearth:signed-collision-actor",
            runtime_generation=1,
            audience=current_shard_id(),
            scopes=["session.act", "session.bootstrap"],
        )
        payload = {
            "session_id": "occupied-session",
            "actor_id": actor_id,
            "player_role": "Collision Resident",
            "world_id": seeded_world_id,
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = signed_resident_request_headers(
            runtime_private_key=runtime_private,
            certificate=certificate,
            method="POST",
            target="/api/session/bootstrap/resident",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        response = seeded_client.post(
            "/api/session/bootstrap/resident",
            content=body,
            headers=headers,
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "session_id_in_use"
        assert (
            db_session.get(SessionVars, "occupied-session").actor_id == "someone-else"
        )
        assert (
            db_session.get(ResidentAuthority, actor_id).active_runtime_generation
            is None
        )
        assert db_session.query(ResidentRequestNonce).count() == 0

    def test_session_bootstrap_retires_stale_duplicate_presence_but_keeps_history(
        self, seeded_client, seeded_world_id, db_session
    ):
        stale_session_id = "test_resident-20260317-010101"
        fresh_session_id = "test_resident-20260318-020202"

        db_session.add(
            SessionVars(
                session_id=stale_session_id,
                actor_id="resident-sun-li-old",
                vars={"location": "Chinatown"},
                updated_at=datetime.now(timezone.utc) - timedelta(hours=6),
            )
        )
        db_session.add(
            WorldEvent(
                session_id=stale_session_id,
                event_type="session_bootstrap",
                summary="Test Resident arrived earlier.",
                world_state_delta={"location": "Chinatown"},
            )
        )
        db_session.commit()

        response = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": fresh_session_id,
                "actor_id": "resident-sun-li-new",
                "world_theme": "quiet harbor",
                "player_role": "Test Resident",
                "bootstrap_source": "worldweaver-agent",
                "world_id": seeded_world_id,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["bootstrap_diagnostics"]["duplicate_agent_sessions_pruned"] == 1

        assert db_session.get(SessionVars, stale_session_id) is None
        assert db_session.get(SessionVars, fresh_session_id) is not None
        assert (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == stale_session_id)
            .count()
            == 1
        )

    def test_session_leave_retires_presence_without_erasing_history(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
    ):
        session_id = "resident-leaving-city"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "resident-leaving-actor",
                "player_role": "Leaving Resident",
                "world_id": seeded_world_id,
            },
        )
        assert bootstrap.status_code == 200
        event_ids = [
            row.id
            for row in db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == session_id)
            .all()
        ]
        assert event_ids

        response = seeded_client.post(
            "/api/session/leave",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        assert response.json()["deleted"] == {"sessions": 1}
        assert db_session.get(SessionVars, session_id) is None
        assert [
            row.id
            for row in db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == session_id)
            .all()
        ] == event_ids

    def test_unsigned_caller_cannot_depart_an_agent_session(
        self, seeded_client, seeded_world_id, db_session
    ):
        session_id = "unsigned-travel-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "unsigned-travel-actor",
                "player_role": "Unsigned Traveler",
                "world_id": seeded_world_id,
                "entry_location": "Embarcadero",
            },
        )
        assert bootstrap.status_code == 200

        response = seeded_client.post(
            "/api/session/travel/depart",
            json={
                "travel_id": "unsigned-trip",
                "session_id": session_id,
                "route_id": "sf-pdx",
                "destination_shard": "rose-city-coop-1",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "actor_proof_required"
        assert db_session.get(SessionVars, session_id) is not None

    def test_unsigned_caller_cannot_create_an_arriving_agent_session(
        self, seeded_client, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "src.services.shard_travel.current_shard_id", lambda: "bay-commons-1"
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.get_federated_travel",
            lambda **_kwargs: {
                "travel": {
                    "travel_id": "unsigned-arrival",
                    "actor_id": "unsigned-arrival-actor",
                    "actor_type": "agent",
                    "source_shard": "rose-city-coop-1",
                    "destination_shard": "bay-commons-1",
                    "arrival_hub_id": "emeryville-sf-transfer",
                    "status": "traveling",
                }
            },
        )

        response = seeded_client.post(
            "/api/session/travel/arrive",
            json={
                "travel_id": "unsigned-arrival",
                "session_id": "unsigned-arrival-session",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "actor_proof_required"
        assert db_session.get(SessionVars, "unsigned-arrival-session") is None
        assert db_session.get(ShardTravelHandoff, "unsigned-arrival") is None

    def test_session_travel_departure_retires_presence_and_is_idempotent(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        session_id = "resident-cross-node-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-cross-node-departure",
                "player_role": "Traveling Resident",
                "world_id": seeded_world_id,
                "entry_location": "Embarcadero",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.services.shard_travel.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [
                            {
                                "shard_id": "rose-city-coop-1",
                                "shard_url": "https://rose.example",
                                "client_url": "https://play.rose.example",
                                "status": "healthy",
                            }
                        ],
                    }
                ],
            },
        )
        starts = []
        departures = []
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.start_federated_travel",
            lambda **kwargs: starts.append(kwargs)
            or {"travel": {"status": "departing"}, "idempotent": False},
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_departure",
            lambda **kwargs: departures.append(kwargs)
            or {"travel": {"status": "traveling"}, "idempotent": False},
        )
        request = {
            "travel_id": "trip-local-001",
            "session_id": session_id,
            "route_id": "sf-pdx",
            "destination_shard": "rose-city-coop-1",
            "reason": "visit",
        }

        response = seeded_client.post("/api/session/travel/depart", json=request)
        repeated = seeded_client.post("/api/session/travel/depart", json=request)

        assert response.status_code == 200
        assert response.json()["handoff"]["status"] == "traveling"
        assert response.json()["handoff"]["destination_url"] == "https://rose.example"
        assert (
            response.json()["handoff"]["destination_client_url"]
            == "https://play.rose.example"
        )
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True
        assert len(starts) == 1
        assert starts[0]["departure_hub_id"] == "emeryville-sf-transfer"
        assert starts[0]["arrival_hub_id"] == "portland-union-station"
        assert len(departures) == 1
        assert db_session.get(SessionVars, session_id) is None
        handoff = db_session.get(ShardTravelHandoff, "trip-local-001")
        assert handoff is not None and handoff.status == "traveling"
        assert handoff.departure_hub_id == "emeryville-sf-transfer"
        assert handoff.arrival_hub_id == "portland-union-station"
        departure_events = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.event_type == "cross_shard_departure")
            .all()
        )
        assert len(departure_events) == 1

    def test_session_travel_departure_can_recover_after_federation_confirmation_fails(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        session_id = "resident-recovering-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-recovering-departure",
                "player_role": "Recovering Traveler",
                "world_id": seeded_world_id,
                "entry_location": "Embarcadero",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.services.shard_travel.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [
                            {
                                "shard_id": "rose-city-coop-1",
                                "shard_url": "https://rose.example",
                                "client_url": "https://play.rose.example",
                                "status": "healthy",
                            }
                        ],
                    }
                ],
            },
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.start_federated_travel",
            lambda **_kwargs: {"travel": {"status": "departing"}},
        )

        def unavailable_departure(**_kwargs):
            raise HTTPException(status_code=503, detail="federation unavailable")

        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_departure",
            unavailable_departure,
        )
        response = seeded_client.post(
            "/api/session/travel/depart",
            json={
                "travel_id": "trip-local-002",
                "session_id": session_id,
                "route_id": "sf-pdx",
                "destination_shard": "rose-city-coop-1",
            },
        )

        assert response.status_code == 202
        assert response.json()["recoverable"] is True
        assert response.json()["handoff"]["status"] == "session_retired"
        assert db_session.get(SessionVars, session_id) is None

        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_departure",
            lambda **_kwargs: {"travel": {"status": "traveling"}, "idempotent": True},
        )
        retry = seeded_client.post("/api/session/travel/trip-local-002/retry-departure")

        assert retry.status_code == 200
        assert retry.json()["handoff"]["status"] == "traveling"
        assert db_session.get(ShardTravelHandoff, "trip-local-002").last_error is None

    def test_session_travel_departure_requires_presence_at_the_route_hub(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        session_id = "resident-away-from-departure"
        bootstrap = seeded_client.post(
            "/api/session/bootstrap",
            json={
                "session_id": session_id,
                "actor_id": "actor-away-from-departure",
                "player_role": "Misplaced Traveler",
                "world_id": seeded_world_id,
                "entry_location": "Chinatown",
            },
        )
        assert bootstrap.status_code == 200
        monkeypatch.setattr(
            "src.services.shard_travel.federation_discovery.get_travel_destinations",
            lambda: {
                "registry": {"reachable": True},
                "destinations": [
                    {
                        "route_id": "sf-pdx",
                        "departure_hub_id": "emeryville-sf-transfer",
                        "departure_hub": "Emeryville / San Francisco transfer",
                        "arrival_hub_id": "portland-union-station",
                        "arrival_hub": "Portland Union Station",
                        "nodes": [
                            {
                                "shard_id": "rose-city-coop-1",
                                "shard_url": "https://rose.example",
                                "client_url": "https://play.rose.example",
                                "status": "healthy",
                            }
                        ],
                    }
                ],
            },
        )

        response = seeded_client.post(
            "/api/session/travel/depart",
            json={
                "travel_id": "trip-wrong-place",
                "session_id": session_id,
                "route_id": "sf-pdx",
                "destination_shard": "rose-city-coop-1",
            },
        )

        assert response.status_code == 409
        assert "departs from Embarcadero" in response.json()["detail"]
        assert db_session.get(SessionVars, session_id) is not None
        assert db_session.get(ShardTravelHandoff, "trip-wrong-place") is None

    def test_session_travel_arrival_uses_destination_pack_and_preserves_actor_id(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        trip = {
            "travel_id": "trip-arrival-001",
            "actor_id": "actor-arriving-resident",
            "actor_type": "agent",
            "name": "Arriving Resident",
            "source_shard": "rose-city-coop-1",
            "destination_shard": "bay-commons-1",
            "departure_hub_id": "portland-union-station",
            "departure_hub": "Portland Union Station",
            "arrival_hub_id": "emeryville-sf-transfer",
            "arrival_hub": "Emeryville / San Francisco transfer",
            "status": "traveling",
        }
        monkeypatch.setattr(
            "src.services.shard_travel.current_shard_id", lambda: "bay-commons-1"
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.get_federated_travel",
            lambda **_kwargs: {"travel": trip},
        )
        confirmations = []
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_arrival",
            lambda **kwargs: confirmations.append(kwargs)
            or {"travel": {"status": "arrived"}, "idempotent": False},
        )
        request = {
            "travel_id": trip["travel_id"],
            "session_id": "arriving-resident-session",
        }

        response = seeded_client.post("/api/session/travel/arrive", json=request)
        repeated = seeded_client.post("/api/session/travel/arrive", json=request)

        assert response.status_code == 200
        assert response.json()["handoff"]["status"] == "arrived"
        assert response.json()["handoff"]["arrival_hub_id"] == "emeryville-sf-transfer"
        assert response.json()["place"] == "Embarcadero"
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True
        assert confirmations == [
            {"travel_id": "trip-arrival-001", "destination_shard": "bay-commons-1"}
        ]

        session = db_session.get(SessionVars, "arriving-resident-session")
        assert session is not None
        assert session.actor_id == "actor-arriving-resident"
        assert session.vars["variables"]["location"] == "Embarcadero"
        events = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == "arriving-resident-session")
            .all()
        )
        assert [event.event_type for event in events].count("session_bootstrap") == 1
        assert [event.event_type for event in events].count("cross_shard_arrival") == 1

    def test_session_travel_arrival_retries_confirmation_without_rebooting(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        trip = {
            "travel_id": "trip-arrival-002",
            "actor_id": "actor-recovering-arrival",
            "actor_type": "agent",
            "name": "Recovering Arrival",
            "source_shard": "rose-city-coop-1",
            "destination_shard": "bay-commons-1",
            "arrival_hub_id": "emeryville-sf-transfer",
            "arrival_hub": "Emeryville / San Francisco transfer",
            "status": "traveling",
        }
        monkeypatch.setattr(
            "src.services.shard_travel.current_shard_id", lambda: "bay-commons-1"
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.get_federated_travel",
            lambda **_kwargs: {"travel": trip},
        )

        def unavailable_arrival(**_kwargs):
            raise HTTPException(status_code=503, detail="federation unavailable")

        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_arrival",
            unavailable_arrival,
        )
        response = seeded_client.post(
            "/api/session/travel/arrive",
            json={
                "travel_id": trip["travel_id"],
                "session_id": "recovering-arrival-session",
            },
        )

        assert response.status_code == 202
        assert response.json()["recoverable"] is True
        assert response.json()["handoff"]["status"] == "session_booted"
        assert db_session.get(SessionVars, "recovering-arrival-session") is not None

        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.confirm_federated_arrival",
            lambda **_kwargs: {"travel": {"status": "arrived"}, "idempotent": True},
        )
        retry = seeded_client.post("/api/session/travel/trip-arrival-002/retry-arrival")

        assert retry.status_code == 200
        assert retry.json()["handoff"]["status"] == "arrived"
        events = (
            db_session.query(WorldEvent)
            .filter(WorldEvent.session_id == "recovering-arrival-session")
            .all()
        )
        assert [event.event_type for event in events].count("session_bootstrap") == 1
        assert [event.event_type for event in events].count("cross_shard_arrival") == 1

    def test_session_travel_arrival_rejects_unknown_local_hub(
        self,
        seeded_client,
        seeded_world_id,
        db_session,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.api.game.state._authorize_travel_request",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "src.services.shard_travel.current_shard_id", lambda: "bay-commons-1"
        )
        monkeypatch.setattr(
            "src.services.shard_travel.federation_travel.get_federated_travel",
            lambda **_kwargs: {
                "travel": {
                    "travel_id": "trip-arrival-003",
                    "actor_id": "actor-misrouted-arrival",
                    "actor_type": "agent",
                    "name": "Misrouted Arrival",
                    "source_shard": "rose-city-coop-1",
                    "destination_shard": "bay-commons-1",
                    "arrival_hub_id": "not-in-this-city",
                    "status": "traveling",
                }
            },
        )

        response = seeded_client.post(
            "/api/session/travel/arrive",
            json={
                "travel_id": "trip-arrival-003",
                "session_id": "misrouted-arrival-session",
            },
        )

        assert response.status_code == 409
        assert "does not exist in city pack" in response.json()["detail"]
        assert db_session.get(SessionVars, "misrouted-arrival-session") is None
        assert db_session.get(ShardTravelHandoff, "trip-arrival-003") is None

    # ── Major 109: turn_source / pipeline_mode diagnostics ──────────────────

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Loopback-only City Studio application, separate from the public shard API."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from .services.city_draft_store import CityDraft, CityDraftStore


class CreateDraftRequest(BaseModel):
    city: str
    draft_id: str | None = None


class SectionEditRequest(BaseModel):
    action: Literal["lock", "unlock", "reroll"]
    expected_revision: int


def _draft_payload(draft: CityDraft) -> dict:
    generated = draft.preview.files.get("generated_map.json") or {}
    sections = generated.get("sections") or []
    return {
        "metadata": draft.metadata,
        "manifest": draft.preview.files["manifest.json"],
        "sections": [
            {
                "id": section["id"],
                "x": section["x"],
                "y": section["y"],
                "width": section["width"],
                "height": section["height"],
                "revision": section["revision"],
                "locked": section["locked"],
                "detail_count": len(section["detail"]["features"]),
            }
            for section in sections
        ],
        "validation": draft.preview.validation.to_dict(),
        "map_available": draft.preview.generated_map_svg is not None,
    }


def create_city_studio_app(
    *,
    store: CityDraftStore,
    configurations_dir: Path,
    access_token: str,
    html_path: Path,
) -> FastAPI:
    """Create a private editor app that is never mounted by the shard server."""
    app = FastAPI(title="WorldWeaver City Studio", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver", "[::1]"],
    )

    def require_token(
        token: Annotated[str | None, Header(alias="X-City-Studio-Token")] = None,
    ) -> None:
        if not token or not secrets.compare_digest(token, access_token):
            raise HTTPException(status_code=401, detail="City Studio token required.")

    authorized = [Depends(require_token)]

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        template = html_path.read_text(encoding="utf-8")
        return HTMLResponse(
            template.replace("__CITY_STUDIO_TOKEN__", json.dumps(access_token)[1:-1]),
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
                "X-Frame-Options": "DENY",
            },
        )

    @app.get("/api/configurations", dependencies=authorized)
    def configurations() -> dict:
        values = []
        for path in sorted(configurations_dir.glob("*.json")):
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            values.append(
                {
                    "id": path.stem,
                    "name": str(config.get("city_name") or path.stem),
                    "fictional": bool(config.get("fictional", False)),
                }
            )
        return {"configurations": values}

    @app.get("/api/drafts", dependencies=authorized)
    def drafts() -> dict:
        return {"drafts": list(store.list())}

    @app.post("/api/drafts", dependencies=authorized, status_code=201)
    def create_draft(payload: CreateDraftRequest) -> dict:
        config_path = (configurations_dir / f"{payload.city}.json").resolve()
        if config_path.parent != configurations_dir.resolve() or not config_path.is_file():
            raise HTTPException(status_code=404, detail="City configuration not found.")
        try:
            source = json.loads(config_path.read_text(encoding="utf-8"))
            draft = store.create(source, draft_id=payload.draft_id)
        except FileExistsError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _draft_payload(draft)

    @app.get("/api/drafts/{draft_id}", dependencies=authorized)
    def get_draft(draft_id: str) -> dict:
        return _draft_payload(_get_draft_or_error(store, draft_id))

    @app.get("/api/drafts/{draft_id}/map.svg", dependencies=authorized)
    def get_map(draft_id: str) -> Response:
        draft = _get_draft_or_error(store, draft_id)
        if draft.preview.generated_map_svg is None:
            raise HTTPException(status_code=404, detail="This draft has no generated map.")
        return Response(draft.preview.generated_map_svg, media_type="image/svg+xml")

    @app.get(
        "/api/drafts/{draft_id}/sections/{section_id}.svg",
        dependencies=authorized,
    )
    def get_section_map(draft_id: str, section_id: str) -> Response:
        draft = _get_draft_or_error(store, draft_id)
        known = {section["id"] for section in _draft_payload(draft)["sections"]}
        if section_id not in known:
            raise HTTPException(status_code=404, detail="Map section not found.")
        path = store.root / draft_id / "preview" / "sections" / f"{section_id}.svg"
        return Response(path.read_text(encoding="utf-8"), media_type="image/svg+xml")

    @app.post("/api/drafts/{draft_id}/sections/{section_id}", dependencies=authorized)
    def edit_map_section(draft_id: str, section_id: str, payload: SectionEditRequest) -> dict:
        try:
            draft = store.edit_section(
                draft_id,
                section_id=section_id,
                action=payload.action,
                expected_revision=payload.expected_revision,
            )
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            status = 409 if "city draft changed" in str(error) else 400
            raise HTTPException(status_code=status, detail=str(error)) from error
        return _draft_payload(draft)

    return app


def _get_draft_or_error(store: CityDraftStore, draft_id: str) -> CityDraft:
    try:
        return store.get(draft_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


__all__ = ["create_city_studio_app"]

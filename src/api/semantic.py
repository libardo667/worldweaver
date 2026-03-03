"""Semantic debug API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.schemas import SemanticConstellationResponse, SessionId
from ..services.constellation_service import get_semantic_constellation
from ..services.session_service import get_state_manager

router = APIRouter()


@router.get("/constellation/{session_id}", response_model=SemanticConstellationResponse)
def get_semantic_constellation_endpoint(
    session_id: SessionId,
    top_n: int = Query(default=20, ge=1, le=100),
    include_edges: bool = Query(default=True),
    semantic_neighbors_k: int = Query(default=3, ge=0, le=10),
    db: Session = Depends(get_db),
):
    """Inspect top semantic storylet candidates for a session."""
    if not settings.enable_constellation:
        raise HTTPException(status_code=404, detail="Constellation debug view is disabled.")

    state_manager = get_state_manager(session_id, db)
    return get_semantic_constellation(
        db=db,
        state_manager=state_manager,
        session_id=session_id,
        top_n=top_n,
        include_edges=include_edges,
        semantic_neighbors_k=semantic_neighbors_k,
    )

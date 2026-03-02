"""Author generation and analysis endpoints."""

from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import SessionVars
from ...models.schemas import GenerateStoryletRequest
from ...services.storylet_ingest import postprocess_new_storylets

router = APIRouter()


@router.post("/generate-intelligent")
def generate_intelligent_storylets(
    request: GenerateStoryletRequest,
    db: Session = Depends(get_db),
):
    """Generate storylets using AI learning and gap analysis."""
    try:
        session_vars = db.query(SessionVars).first()
        current_vars: Dict[str, Any] = {}
        if session_vars:
            current_vars = cast(Dict[str, Any], session_vars.vars or {})

        from ...services.llm_service import generate_learning_enhanced_storylets

        storylets = generate_learning_enhanced_storylets(
            db=db,
            current_vars=current_vars,
            n=request.count or 3,
        )

        if not storylets:
            raise HTTPException(status_code=422, detail="No storylets generated")

        storylet_dicts: list[dict[str, Any]] = []
        for data in storylets:
            if not all(
                key in data
                for key in ["title", "text_template", "requires", "choices", "weight"]
            ):
                continue
            storylet_dicts.append(
                {
                    "title": data["title"],
                    "text_template": data["text_template"],
                    "requires": data["requires"],
                    "choices": data["choices"],
                    "weight": float(data["weight"]),
                }
            )

        save_result = postprocess_new_storylets(
            db=db,
            storylets=storylet_dicts,
            improvement_trigger="intelligent-generation",
            assign_spatial=True,
        )

        base_response = {
            "message": f"Generated {save_result.get('added', 0)} intelligent storylets",
            "storylets": save_result.get("storylets", []),
            "ai_context": "Used storylet analysis to create targeted, coherent content",
        }

        if save_result.get("auto_improvements"):
            base_response["auto_improvements"] = save_result.get("auto_improvements")
            base_response["improvement_details"] = save_result.get("improvement_details")

        return base_response
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate intelligent storylets: {str(exc)}",
        )


@router.get("/storylet-analysis")
def get_storylet_analysis(db: Session = Depends(get_db)):
    """Get comprehensive storylet analysis and recommendations."""
    try:
        from ...services.storylet_analyzer import (
            analyze_storylet_gaps,
            generate_gap_recommendations,
            get_ai_learning_context,
        )

        gap_analysis = analyze_storylet_gaps(db)

        missing_setters = set(gap_analysis.get("missing_connections", []))
        unused_setters = set(gap_analysis.get("unused_setters", []))
        location_flow = gap_analysis.get("location_analysis", {})
        danger_distribution = gap_analysis.get("danger_distribution", {})

        recommendations = generate_gap_recommendations(
            missing_setters,
            unused_setters,
            location_flow,
            danger_distribution,
        )
        learning_context = get_ai_learning_context(db)

        return {
            "gap_analysis": gap_analysis,
            "recommendations": recommendations,
            "ai_learning_context": learning_context,
            "summary": {
                "total_gaps": len(gap_analysis.get("missing_connections", [])),
                "top_priority": (
                    recommendations[0]["suggestion"]
                    if recommendations
                    else "No urgent issues"
                ),
                "connectivity_health": learning_context.get("world_state_analysis", {}).get(
                    "connectivity_health",
                    0,
                ),
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze storylets: {str(exc)}",
        )


@router.post("/generate-targeted")
def generate_targeted_storylets(db: Session = Depends(get_db)):
    """Generate storylets specifically targeting identified gaps."""
    try:
        from ...services.storylet_analyzer import generate_targeted_storylets as generate_targeted

        storylets = generate_targeted(db, max_storylets=5)

        if not storylets:
            return {
                "message": "No critical gaps identified - storylet ecosystem is healthy!"
            }

        storylet_dicts: list[dict[str, Any]] = []
        for data in storylets:
            if not all(
                key in data
                for key in ["title", "text_template", "requires", "choices", "weight"]
            ):
                continue
            storylet_dicts.append(
                {
                    "title": data["title"],
                    "text_template": data["text_template"],
                    "requires": data["requires"],
                    "choices": data["choices"],
                    "weight": float(data["weight"]),
                }
            )

        save_result = postprocess_new_storylets(
            db=db,
            storylets=storylet_dicts,
            improvement_trigger="targeted-generation",
            assign_spatial=True,
        )

        base_response = {
            "message": f"Generated {save_result.get('added', 0)} targeted storylets",
            "storylets": save_result.get("storylets", []),
            "targeting_info": (
                "These storylets specifically address connectivity gaps and flow issues"
            ),
        }

        if save_result.get("auto_improvements"):
            base_response["auto_improvements"] = save_result.get("auto_improvements")
            base_response["improvement_details"] = save_result.get("improvement_details")

        return base_response
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate targeted storylets: {str(exc)}",
        )

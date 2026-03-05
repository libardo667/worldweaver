"""Author suggestion endpoints."""

import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import StoryletIn, SuggestReq, SuggestResp
from ...services.llm_service import llm_suggest_storylets
from ...services.storylet_ingest import postprocess_new_storylets

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/suggest", response_model=SuggestResp)
def author_suggest(
    payload: SuggestReq,
    commit: bool = False,
    db: Session = Depends(get_db),
):
    """Generate storylet suggestions using LLM."""
    try:
        raw = llm_suggest_storylets(payload.n, payload.themes or [], payload.bible or {})
        items = [StoryletIn(**item) for item in (raw or [])]

        if not items:
            items = [
                StoryletIn(
                    title="Model returned no storylets",
                    text_template=("The model did not return any storylets. " "Try adjusting the prompt or your API key."),
                    requires={},
                    choices=[{"label": "Ok", "set": {}}],
                    weight=1.0,
                )
            ]

        if commit and items:
            storylet_dicts = [
                {
                    "title": storylet.title,
                    "text_template": storylet.text_template,
                    "requires": storylet.requires,
                    "choices": storylet.choices,
                    "weight": storylet.weight,
                }
                for storylet in items
            ]
            try:
                save_result = postprocess_new_storylets(
                    db=db,
                    storylets=storylet_dicts,
                    improvement_trigger="author-suggest",
                    assign_spatial=True,
                )
                logger.info("author_suggest: saved %s storylets", save_result.get("added", 0))
            except Exception:
                logger.exception("Failed to save suggested storylets")

        return SuggestResp(storylets=items)
    except Exception as exc:
        logger.exception("Error in LLM suggest")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "type": type(exc).__name__,
                "trace": traceback.format_exc().splitlines()[-3:],
            },
        )

"""Storylet ingest/postprocessing service for author workflows."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Storylet

logger = logging.getLogger(__name__)


class AuthorPipelineError(RuntimeError):
    """Raised when an author mutation pipeline fails."""

    def __init__(self, message: str, receipt: Dict[str, Any]):
        super().__init__(message)
        self.receipt = receipt


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _start_receipt(operation: str) -> Dict[str, Any]:
    return {
        "operation": operation,
        "status": "started",
        "started_at": _utc_now_iso(),
        "completed_at": None,
        "counts": {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        },
        "phases": [],
        "rollback_actions": [],
    }


def _start_phase(receipt: Dict[str, Any], name: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    phase = {
        "name": name,
        "status": "started",
        "started_at": _utc_now_iso(),
        "completed_at": None,
        "details": details or {},
    }
    receipt["phases"].append(phase)
    return phase


def _complete_phase(phase: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> None:
    phase["status"] = "completed"
    phase["completed_at"] = _utc_now_iso()
    if details:
        merged = dict(phase.get("details") or {})
        merged.update(details)
        phase["details"] = merged


def _fail_phase(phase: Dict[str, Any], error: str, details: Optional[Dict[str, Any]] = None) -> None:
    phase["status"] = "failed"
    phase["completed_at"] = _utc_now_iso()
    merged = dict(phase.get("details") or {})
    if details:
        merged.update(details)
    merged["error"] = str(error)
    phase["details"] = merged


def _finalize_receipt(receipt: Dict[str, Any], status: str) -> Dict[str, Any]:
    receipt["status"] = status
    receipt["completed_at"] = _utc_now_iso()
    return receipt


def deduplicate_and_insert(
    db: Session,
    storylets: list[dict[str, Any]],
    *,
    commit: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """Validate, deduplicate, and insert storylets into the database."""
    required_keys = ["title", "text_template", "requires", "choices", "weight"]
    created_storylets: list[dict[str, Any]] = []
    skipped_count = 0

    for data in storylets:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            logger.warning(
                "Skipping storylet '%s': missing required keys: %s",
                (data.get("title") or "<untitled>"),
                ", ".join(missing_keys),
            )
            skipped_count += 1
            continue

        normalized = (data.get("title") or "").strip()
        exists = db.query(Storylet).filter(func.lower(Storylet.title) == func.lower(normalized)).first()
        if exists:
            logger.warning("Skipped storylet '%s': duplicate title", normalized)
            skipped_count += 1
            continue

        storylet = Storylet(
            title=normalized,
            text_template=data["text_template"],
            requires=data["requires"],
            choices=data["choices"],
            weight=float(data["weight"]),
        )
        # Use a savepoint per row to avoid aborting all inserts on one conflict.
        nested = db.begin_nested()
        db.add(storylet)
        try:
            db.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            logger.warning(
                "Skipped storylet '%s': integrity error (likely duplicate)",
                normalized,
            )
            skipped_count += 1
            continue

        created_storylets.append(
            {
                "id": storylet.id,
                "title": storylet.title,
                "text_template": storylet.text_template,
                "requires": data["requires"],
                "choices": data["choices"],
                "weight": storylet.weight,
            }
        )

    if commit:
        db.commit()
    return created_storylets, skipped_count


def assign_spatial_to_storylets(
    db: Session,
    storylet_titles: list[str],
    spatial_ids: Optional[list[int]] = None,
    *,
    commit: bool = True,
) -> int:
    """Assign spatial coordinates to newly created storylets."""
    from ..services.spatial_navigator import SpatialNavigator

    new_storylet_ids = [storylet.id for storylet in db.query(Storylet).filter(Storylet.title.in_(storylet_titles)) if storylet.id is not None]

    updates = SpatialNavigator.auto_assign_coordinates(
        db,
        spatial_ids or new_storylet_ids,
        commit=commit,
    )
    if updates > 0:
        logger.info("Auto-assigned coordinates to %d storylets", updates)
    return updates


def run_auto_improvements(
    db: Session,
    storylet_count: int,
    trigger: str,
) -> Optional[dict[str, Any]]:
    """Run auto-improvement if the trigger warrants it."""
    from ..services.auto_improvement import (
        auto_improve_storylets,
        should_run_auto_improvement,
    )

    if not str(trigger or "").strip():
        return None

    if not should_run_auto_improvement(storylet_count, trigger):
        return None

    return auto_improve_storylets(
        db=db,
        trigger=f"{trigger} ({storylet_count} storylets)",
        run_smoothing=bool(settings.enable_story_smoothing),
        run_deepening=True,
    )


def postprocess_new_storylets(
    db: Session,
    storylets: list[dict[str, Any]],
    improvement_trigger: str = "",
    assign_spatial: bool = True,
    spatial_ids: Optional[list[int]] = None,
    *,
    replace_existing: bool = False,
    operation_name: str = "author-storylet-mutation",
) -> dict[str, Any]:
    """Insert storylets with transaction safety and operation receipts."""
    from ..services.auto_improvement import get_improvement_summary
    from ..services.embedding_service import embed_all_storylets

    receipt = _start_receipt(operation_name)
    created_storylets: list[dict[str, Any]] = []
    skipped_count = 0
    updates = 0
    improvement_results = None
    warning_messages: list[str] = []

    transaction_phase = _start_phase(
        receipt,
        "core_transaction",
        {"replace_existing": bool(replace_existing), "assign_spatial": bool(assign_spatial)},
    )

    outer_tx = db.begin_nested() if db.in_transaction() else db.begin()
    try:
        if replace_existing:
            delete_phase = _start_phase(receipt, "replace_existing")
            deleted_count = int(db.query(Storylet).delete())
            _complete_phase(delete_phase, {"deleted_storylets": deleted_count})
            receipt["counts"]["updated"] += deleted_count

        insert_phase = _start_phase(receipt, "insert_storylets", {"candidate_count": len(storylets)})
        created_storylets, skipped_count = deduplicate_and_insert(
            db,
            storylets,
            commit=False,
        )
        _complete_phase(
            insert_phase,
            {"inserted_storylets": len(created_storylets), "skipped_storylets": skipped_count},
        )
        receipt["counts"]["inserted"] = len(created_storylets)
        receipt["counts"]["skipped"] = skipped_count

        if assign_spatial and created_storylets:
            spatial_phase = _start_phase(receipt, "assign_coordinates")
            titles = [storylet["title"] for storylet in created_storylets]
            updates = assign_spatial_to_storylets(
                db,
                titles,
                spatial_ids,
                commit=False,
            )
            _complete_phase(spatial_phase, {"spatial_updates": updates})
            receipt["counts"]["updated"] += int(updates)

        outer_tx.commit()
        _complete_phase(transaction_phase, {"result": "committed"})
    except Exception as exc:
        outer_tx.rollback()
        _fail_phase(transaction_phase, str(exc), {"result": "rolled_back"})
        receipt["rollback_actions"].append(
            {
                "phase": "core_transaction",
                "action": "rolled_back",
                "reason": str(exc),
            }
        )
        _finalize_receipt(receipt, "failed")
        raise AuthorPipelineError(
            f"Author pipeline core transaction failed: {exc}",
            receipt,
        ) from exc

    if created_storylets:
        embed_phase = _start_phase(receipt, "embed_storylets")
        try:
            embedded = int(embed_all_storylets(db) or 0)
            _complete_phase(embed_phase, {"embedded_storylets": embedded})
            receipt["counts"]["updated"] += max(0, embedded)
        except Exception as exc:
            warning_messages.append(f"embedding failed (non-fatal): {exc}")
            logger.warning("Embedding failed (non-fatal): %s", exc)
            _fail_phase(embed_phase, str(exc), {"non_fatal": True})

    auto_phase = _start_phase(receipt, "auto_improvement")
    try:
        improvement_results = run_auto_improvements(
            db,
            len(created_storylets),
            improvement_trigger,
        )
        if improvement_results and not bool(improvement_results.get("success", True)):
            warning_messages.append(str(improvement_results.get("error", "auto-improvement failed")))
            _fail_phase(
                auto_phase,
                str(improvement_results.get("error", "auto-improvement failed")),
                {"non_fatal": True},
            )
        else:
            _complete_phase(
                auto_phase,
                {
                    "ran": bool(improvement_results is not None),
                    "success": bool(improvement_results.get("success", True)) if isinstance(improvement_results, dict) else True,
                },
            )
    except Exception as exc:
        warning_messages.append(f"auto-improvement failed (non-fatal): {exc}")
        logger.warning("Auto-improvement failed (non-fatal): %s", exc)
        _fail_phase(auto_phase, str(exc), {"non_fatal": True})
        improvement_results = {"success": False, "error": str(exc)}

    status = "completed_with_warnings" if warning_messages else "completed"
    _finalize_receipt(receipt, status)

    response = {
        "added": len(created_storylets),
        "skipped": skipped_count,
        "storylets": created_storylets,
        "spatial_updates": updates,
        "auto_improvements": get_improvement_summary(improvement_results) if improvement_results else None,
        "improvement_details": improvement_results,
        "operation_receipt": receipt,
    }
    if warning_messages:
        response["warnings"] = warning_messages
    return response

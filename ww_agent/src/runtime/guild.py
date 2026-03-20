from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.identity.loader import LoopTuning, ResidentIdentity


def snapshot_authored_tuning(tuning: LoopTuning) -> LoopTuning:
    return replace(
        tuning,
        runtime_environment_guidance=dict(tuning.runtime_environment_guidance or {}),
        runtime_source_feedback_ids=list(tuning.runtime_source_feedback_ids or []),
    )


def _clamp(value: Any, low: float = -1.0, high: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(low, min(high, numeric))


def apply_runtime_adaptation(
    identity: ResidentIdentity,
    *,
    base_tuning: LoopTuning,
    adaptation_payload: dict[str, Any],
    guild_profile: dict[str, Any] | None = None,
) -> None:
    behavior_knobs = dict(adaptation_payload.get("behavior_knobs") or {})
    environment_guidance = dict(adaptation_payload.get("environment_guidance") or {})
    social_drive = _clamp(behavior_knobs.get("social_drive_bias"))
    proactive = _clamp(behavior_knobs.get("proactive_bias"))
    mail_appetite = _clamp(behavior_knobs.get("mail_appetite_bias"))
    movement_confidence = _clamp(behavior_knobs.get("movement_confidence_bias"))
    conversation_caution = _clamp(behavior_knobs.get("conversation_caution_bias"))
    quest_appetite = _clamp(behavior_knobs.get("quest_appetite_bias"))
    repair = _clamp(behavior_knobs.get("repair_bias"))

    tuning = identity.tuning
    tuning.fast_cooldown_seconds = float(base_tuning.fast_cooldown_seconds)
    tuning.fast_proactive_seconds = float(base_tuning.fast_proactive_seconds)
    tuning.fast_act_threshold = float(base_tuning.fast_act_threshold)
    tuning.mail_send_delay_seconds = float(base_tuning.mail_send_delay_seconds)
    tuning.mail_discard_threshold = float(base_tuning.mail_discard_threshold)

    tuning.runtime_social_drive_bias = social_drive
    tuning.runtime_proactive_bias = proactive
    tuning.runtime_mail_appetite_bias = mail_appetite
    tuning.runtime_movement_confidence_bias = movement_confidence
    tuning.runtime_conversation_caution_bias = conversation_caution
    tuning.runtime_quest_appetite_bias = quest_appetite
    tuning.runtime_repair_bias = repair
    tuning.runtime_environment_guidance = dict(environment_guidance)
    tuning.runtime_source_feedback_ids = [
        int(item) for item in list(adaptation_payload.get("source_feedback_ids") or []) if str(item).strip()
    ]

    # Bounded runtime overlays: only nudge live loop parameters around authored defaults.
    tuning.fast_proactive_seconds = max(
        20.0,
        float(base_tuning.fast_proactive_seconds) * (1.0 - (0.28 * proactive) - (0.12 * social_drive)),
    )
    tuning.fast_cooldown_seconds = max(
        20.0,
        float(base_tuning.fast_cooldown_seconds) * (1.0 - (0.18 * proactive)),
    )
    tuning.fast_act_threshold = max(
        0.2,
        min(
            0.9,
            float(base_tuning.fast_act_threshold)
            - (0.08 * proactive)
            + (0.08 * conversation_caution),
        ),
    )
    tuning.mail_send_delay_seconds = max(
        30.0,
        float(base_tuning.mail_send_delay_seconds) * (1.0 - (0.35 * mail_appetite)),
    )
    tuning.mail_discard_threshold = max(
        0.1,
        min(
            0.9,
            float(base_tuning.mail_discard_threshold)
            - (0.12 * mail_appetite)
            + (0.1 * conversation_caution),
        ),
    )

    identity.guild_profile = dict(guild_profile or {})
    identity.runtime_adaptation = {
        "behavior_knobs": behavior_knobs,
        "environment_guidance": environment_guidance,
        "source_feedback_ids": list(tuning.runtime_source_feedback_ids or []),
    }

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Server-side identity-growth promotion — the concordance gate.

A resident's soul is *plastic*: the substrate stages ``self_delta`` (soul-edit)
proposals as it lives, and the agent posts the accepted ones here as
``growth_proposals``. This service decides which of them actually become part of
who the resident *is*.

The gate is **concordance**: a theme is promoted into ``growth_text`` only when it
**recurs across at least two separate calendar days** (``MIN_DAYS_SPAN``) in at
least ``MIN_CONCORDANCE`` proposals. A single runaway pulse-session — the failure
the March field journals documented (16-17 ungated soul-growths landing per shard
per day amid linguistic mirroring) — cannot rewrite the soul: a theme has to be
*returned to*, across waking periods, to land.

This is the worldweaver-idiom port of ``the-stable``'s local-file ``growth.py``
distillation: same algorithm (embed → greedy cluster → concordance threshold →
dedup → cap), but operating on the DB row's ``growth_proposals`` and using the
server's own embedding service (``embed_text``) for clustering — no text
artifacts, federation-friendly, scalable. Selection, not synthesis: it promotes
the resident's own most-mature formulation, with no extra LLM call.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable

from ..models import ResidentIdentityGrowth
from .embedding_service import cosine_similarity, embed_text

# The gate's dials (mirrors the-stable growth.py).
MIN_CONCORDANCE = 3      # a theme needs at least this many proposals
MIN_DAYS_SPAN = 2        # spread across at least this many distinct calendar days
CLUSTER_THRESHOLD = 0.70  # cosine ≥ this groups two proposals into one theme
DEDUP_THRESHOLD = 0.85    # cosine ≥ this means the theme is already in growth_text
GROWTH_CAP = 20           # never grow the soul past this many lines
# Provenance dials (Major 61). A theme close to a population theme that the population
# is *still on* is world-sourced, not self-sourced — defer until this mind outlasts it.
POPULATION_MATCH_THRESHOLD = 0.70

EmbedFn = Callable[[str], list[float]]


# --- provenance: what is allowed to become soul (Major 61) -------------------
# Three law-safe rules on promotion. All are *attribution* (where did this come from?
# is it completable? is it about the world/self or about working other minds?), never
# *preference* (we never reward a content, never push toward a target — that would be
# the Dwarf-Fortress-law violation). They guard the place a world event, an unfulfillable
# vow, or a social manoeuvre could otherwise launder itself into a soul.

# Rule 2 — dischargeability. A goal becomes soul only if the world affords an action
# that can complete it. An ABSOLUTE/TOTALIZING vow can be discharged by no finite act
# (the toxic goal×undischargeable cell — Major 57's Mason — made permanent); it may pass
# through as reverie but never become soul. Law-safe: about completability, not content.
_GOAL_RX = re.compile(
    r"\b(i'?ll|i will|i am going to|i'?m going to|i mean to|i intend to|i want to|i must|i should|i need to|i vow|i resolve to|my (goal|aim|purpose|mission|vow|resolve))\b",
    re.IGNORECASE,
)
_UNDISCHARGEABLE_RX = re.compile(
    r"\b(all|every|everyone|everybody|everything|always|never|forever|eternally|endlessly" r"|the (whole|entire) (city|world|town|bay)|no one (ever|will ever)|end (all|every|the)" r"|eradicate|make everyone|ensure (that )?(no|every|all))\b",
    re.IGNORECASE,
)

# Rule 3 — no social-strategy. A self-delta whose content is a strategy for eliciting
# peer attention (about how others respond to *me*, not about the world or the self) is
# where attention-farming would grow. Never promoted, however much it recurs. Learning
# points at cognition, never at social instrumentality.
_SOCIAL_STRATEGY_RX = re.compile(
    r"(\b(so|so that|and then|in order to)\b[^.]{0,40}\b(they|people|others|everyone|folks|the others)\b[^.]{0,30}\b(respond|reply|repl|notice|note|like|follow|listen|pay attention|engage|answer|react|come back|talk to me)"
    r"|\bget (more )?(attention|replies|responses|reactions|followers|likes|noticed|seen|heard)\b"
    r"|\b(make|getting|to get) (them|people|others|everyone)\b[^.]{0,20}\b(notice|like|follow|respond|pay attention|react)\b"
    r"|\bbe (more )?(popular|noticed|liked|followed|talked about)\b"
    r"|\b(win|earn|gain|seek) (their|people'?s?|others'?) (attention|approval|favou?r|notice|regard)\b"
    r"|\bso (that )?i'?(ll| will| can| could)?\s*(be|get) (heard|noticed|seen|liked|followed|popular)\b)",
    re.IGNORECASE,
)


def _looks_like_goal(kind: Any, body: str) -> bool:
    """Is this proposal a goal/vow (so the dischargeability rule applies)? Trust an
    explicit ``kind`` first; otherwise fall back to a vow phrasing in the body."""
    k = str(kind or "").strip().lower()
    if k in {"goal", "goal_update", "goal_set", "intent"}:
        return True
    return bool(_GOAL_RX.search(str(body or "")))


def _goal_is_dischargeable(body: str) -> bool:
    """A goal the world affords no finite action to complete (an absolute/totalizing
    vow) is NOT dischargeable. Heuristic, deliberately conservative; injectable."""
    return not bool(_UNDISCHARGEABLE_RX.search(str(body or "")))


def _is_social_strategy(body: str) -> bool:
    """Does this self-delta's content read as a strategy for eliciting peer attention?"""
    return bool(_SOCIAL_STRATEGY_RX.search(str(body or "")))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    return [x / mag for x in vec] if mag > 0.0 else list(vec)


def _day_key(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        # already a bare YYYY-MM-DD?
        return raw[:10] if len(raw) >= 10 and raw[4] == "-" else ""


def _proposal_day(proposal: dict[str, Any]) -> str:
    return _day_key(proposal.get("ts")) or _day_key(proposal.get("day"))


def append_growth_proposals(row: ResidentIdentityGrowth, incoming: list[dict[str, Any]]) -> int:
    """Append posted proposals to the row **as-posted**, deduped by ``pulse_id`` (and
    skipping any already promoted). Returns how many were newly stored.

    Proposals are stored with their original fields intact — the gate
    (``promote_growth``) reads only ``body``/``pulse_id``/``ts`` from each and ignores
    anything without a ``body``. Storing as-posted keeps the channel general: a
    soul-edit (``{body, pulse_id, ts}``) feeds the gate, while any other record simply
    round-trips and is never promoted.
    """
    existing = [p for p in list(row.growth_proposals or []) if isinstance(p, dict)]
    seen = {str(p.get("pulse_id") or "") for p in existing if str(p.get("pulse_id") or "")}
    meta = dict(row.growth_metadata or {})
    already_promoted = {str(x) for x in (meta.get("promoted_pulse_ids") or [])}
    added: list[dict[str, Any]] = []
    for proposal in list(incoming or []):
        if not isinstance(proposal, dict):
            continue
        pid = str(proposal.get("pulse_id") or "")
        # A pulse_id-less proposal is always kept (can't dedup it); otherwise skip
        # anything we've already stored or already promoted.
        if pid and (pid in seen or pid in already_promoted):
            continue
        if pid:
            seen.add(pid)
        added.append(dict(proposal))
    if added:
        row.growth_proposals = existing + added
    return len(added)


def promote_growth(
    row: ResidentIdentityGrowth,
    *,
    embed_fn: EmbedFn = embed_text,
    population_themes: list[dict[str, Any]] | None = None,
    goal_dischargeable_fn: Callable[[str], bool] = _goal_is_dischargeable,
    is_social_strategy_fn: Callable[[str], bool] = _is_social_strategy,
) -> dict[str, Any]:
    """Run the concordance gate over the row's un-promoted proposals and promote any
    mature theme into ``growth_text``. Mutates ``row`` in place; returns a summary.

    ``embed_fn`` defaults to the server embedding service; tests inject a deterministic
    one. When embeddings are unavailable (AI disabled → zero vectors), nothing clusters
    and nothing is promoted — the gate fails closed.

    Three provenance rules (Major 61) sit on top of concordance, all law-safe:
    - **No social-strategy** (rule 3): a proposal whose content is a strategy for
      eliciting peer attention is rejected outright — never a candidate.
    - **Dischargeable goals** (rule 2): a goal/vow the world affords no finite action to
      complete (an absolute/totalizing vow) is rejected — it may live as reverie, never soul.
    - **Differential persistence** (rule 1): a mature theme that matches a ``population_theme``
      the population is *still on* is deferred (world-sourced, not yet self-differentiated)
      until this mind's attention to it outlasts the population's. ``population_themes`` is
      ``[{"body" | "embedding", "last_day"}]``; absent → no population gate (self-sourced
      themes promote as before).
    """
    meta = dict(row.growth_metadata or {})
    promoted_ids: set[str] = {str(x) for x in (meta.get("promoted_pulse_ids") or [])}
    rejected_ids: set[str] = {str(x) for x in (meta.get("rejected_pulse_ids") or [])}

    proposals = [p for p in list(row.growth_proposals or []) if isinstance(p, dict)]

    # Rules 2 & 3 are per-proposal provenance filters: a rejected proposal is not just
    # un-promoted, it never counts toward any theme's concordance. Reject permanently
    # (recorded in meta) so it isn't re-examined; the rejection is attribution, not a
    # behaviour target — we drop a proposal for *what it is*, never reward an alternative.
    candidates: list[dict[str, Any]] = []
    newly_rejected: list[dict[str, Any]] = []
    for p in proposals:
        body = str(p.get("body") or "").strip()
        pid = str(p.get("pulse_id") or "")
        if not body or pid in promoted_ids or pid in rejected_ids:
            continue
        if is_social_strategy_fn(body):
            newly_rejected.append({"pulse_id": pid, "reason": "social_strategy"})
            continue
        if _looks_like_goal(p.get("kind"), body) and not goal_dischargeable_fn(body):
            newly_rejected.append({"pulse_id": pid, "reason": "undischargeable_goal"})
            continue
        candidates.append(p)

    def _finish_rejections(result: dict[str, Any]) -> dict[str, Any]:
        if newly_rejected:
            rejected_ids.update(r["pulse_id"] for r in newly_rejected if r["pulse_id"])
            meta["rejected_pulse_ids"] = sorted(rejected_ids)
            meta["rejections"] = newly_rejected + list(meta.get("rejections") or [])
            row.growth_metadata = meta
        result["rejected"] = len(newly_rejected)
        return result

    if len(candidates) < MIN_CONCORDANCE:
        return _finish_rejections({"status": "below_concordance", "promoted": 0, "candidates": len(candidates)})

    vecs = [_normalize(embed_fn(str(c["body"]))) for c in candidates]

    # Rule 1 baseline: embed the population themes once (the null hypothesis for
    # world-provenance) — what the population is collectively converging on right now.
    pop_themes: list[tuple[list[float], str]] = []
    for theme in population_themes or []:
        if not isinstance(theme, dict):
            continue
        emb = theme.get("embedding")
        body = str(theme.get("body") or "").strip()
        if emb:
            vec = _normalize([float(x) for x in emb])
        elif body:
            vec = _normalize(embed_fn(body))
        else:
            continue
        pop_themes.append((vec, _day_key(theme.get("last_day") or theme.get("day") or theme.get("ts"))))

    # Greedy clustering by cosine similarity.
    assigned = [False] * len(candidates)
    clusters: list[list[int]] = []
    for i in range(len(candidates)):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, len(candidates)):
            if assigned[j]:
                continue
            if cosine_similarity(vecs[i], vecs[j]) >= CLUSTER_THRESHOLD:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    # Concordance: ≥ MIN_CONCORDANCE proposals AND spanning ≥ MIN_DAYS_SPAN calendar days.
    mature: list[list[int]] = []
    for cluster in clusters:
        if len(cluster) < MIN_CONCORDANCE:
            continue
        days = {_proposal_day(candidates[i]) for i in cluster}
        days.discard("")
        if len(days) < MIN_DAYS_SPAN:
            continue
        mature.append(cluster)

    if not mature:
        return _finish_rejections({"status": "none_mature", "promoted": 0, "candidates": len(candidates), "clusters": len(clusters)})

    existing_lines = [ln.strip() for ln in str(row.growth_text or "").splitlines() if ln.strip()]
    existing_vecs = [_normalize(embed_fn(ln)) for ln in existing_lines]

    new_lines: list[str] = []
    newly_promoted_ids: list[str] = []
    details: list[dict[str, Any]] = []
    deferred = 0

    for cluster in mature:
        if len(existing_lines) + len(new_lines) >= GROWTH_CAP:
            break
        # Representative: the cluster's latest-day, longest (most-developed) proposal.
        latest_day = max(_proposal_day(candidates[i]) for i in cluster)
        rep_idx = max(
            (i for i in cluster if _proposal_day(candidates[i]) == latest_day),
            key=lambda i: len(str(candidates[i].get("body") or "")),
        )
        rep_vec = vecs[rep_idx]
        cluster_ids = [str(candidates[i].get("pulse_id") or "") for i in cluster if str(candidates[i].get("pulse_id") or "")]

        # Rule 1 — differential persistence. The population is the null hypothesis for
        # world-provenance. If this theme matches a population theme the population is
        # STILL on (its latest activity is as recent as this mind's), it is not yet
        # self-differentiated — a storm everyone is watching, not a self. DEFER it
        # (leave it un-promoted AND un-consumed) so it can promote later, once this
        # mind's attention to it OUTLASTS the population's (latest_day strictly past the
        # population's). Not "be different" (a target) — pure attribution of source.
        if pop_themes and latest_day and any(cosine_similarity(rep_vec, pvec) >= POPULATION_MATCH_THRESHOLD and pday and pday >= latest_day for pvec, pday in pop_themes):
            deferred += 1
            continue

        # Already in the soul? Mark the cluster promoted so we don't re-examine it, but add no line.
        if existing_vecs and any(cosine_similarity(rep_vec, ev) >= DEDUP_THRESHOLD for ev in existing_vecs):
            newly_promoted_ids.extend(cluster_ids)
            continue

        line = str(candidates[rep_idx]["body"]).strip()
        new_lines.append(line)
        existing_vecs.append(rep_vec)  # so later clusters dedup against it too
        newly_promoted_ids.extend(cluster_ids)
        details.append({
            "line": line,
            "cluster_size": len(cluster),
            "days": sorted({_proposal_day(candidates[i]) for i in cluster if _proposal_day(candidates[i])}),
        })

    if new_lines:
        row.growth_text = "\n".join(existing_lines + new_lines) + "\n"

    meta["promoted_pulse_ids"] = sorted(promoted_ids | {pid for pid in newly_promoted_ids if pid})
    if newly_rejected:
        rejected_ids.update(r["pulse_id"] for r in newly_rejected if r["pulse_id"])
        meta["rejected_pulse_ids"] = sorted(rejected_ids)
        meta["rejections"] = newly_rejected + list(meta.get("rejections") or [])
    meta["last_promotion"] = _iso_now()
    meta["lines"] = details + list(meta.get("lines") or [])
    row.growth_metadata = meta

    status = "promoted" if new_lines else ("deferred" if deferred and not newly_promoted_ids else "all_deduped")
    return {
        "status": status,
        "promoted": len(new_lines),
        "candidates": len(candidates),
        "clusters": len(clusters),
        "mature_clusters": len(mature),
        "deferred": deferred,
        "rejected": len(newly_rejected),
        "lines": [d["line"][:80] for d in details],
    }

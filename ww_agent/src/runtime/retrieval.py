"""Retrieval prediction: the first step of Rung 3 — predict from experience, not
from the LLM (Major 51).

Rung 3's prize is a substrate that predicts its own world. The frontier version
trains neural weights on prediction error and must reckon with the dark room. This
is the honest first stone *before* any of that: a non-parametric, training-free
predictor that recalls the most similar past moments and reuses what actually
followed them — k-nearest-neighbours over the resident's own ledger, weighted by
similarity. It improves with experience (more history → better neighbours), needs
no gradient descent, and has no collapse dynamics: it can only echo what has
already happened, so it cannot wander into a dark room of its own making. It is the
cheapest test of the question Rung 3 rests on — *can the system predict its own
world from its own past at all?* — and it runs OFFLINE as a backtest, changing no
live behaviour.

It predicts in the ANCHOR lane (concrete, soul-distinct things — the keeper, the
red thread), not the five flat drives, so "predict well" cannot collapse into
"predict calm." The price on boring is kept by the choice of *what* to predict.

The metric that matters is **new-anchor recall**: of the anchors that newly appear
from one moment to the next, how many did each method foresee? A persistence
baseline (predict the present persists) catches *none* of them by construction —
it can only ever say "more of the same." So any new-anchor recall above zero is
prediction the substrate generated from its own experience, not from the teacher
and not from mere stickiness. That is the first faint signal of self-prediction.
"""

from __future__ import annotations

from typing import Any

from src.runtime.drive import Embedder, _cosine
from src.runtime.ledger import load_runtime_events


def anchor_snapshots(events: list[dict[str, Any]], *, salience_floor: float = 0.0) -> list[set[str]]:
    """Time-ordered salient-anchor sets from ``anchor_observed`` events."""
    snaps: list[tuple[str, set[str]]] = []
    for e in events:
        if str(e.get("event_type") or "").strip() != "anchor_observed":
            continue
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        ts = str(payload.get("observed_ts") or e.get("ts") or "").strip()
        anchors = payload.get("anchors")
        if not isinstance(anchors, list):
            continue
        s: set[str] = set()
        for a in anchors:
            if isinstance(a, dict):
                name = str(a.get("anchor") or "").strip()
                try:
                    sal = float(a.get("salience"))
                except (TypeError, ValueError):
                    sal = 1.0
                if name and sal >= salience_floor:
                    s.add(name)
        if s:
            snaps.append((ts, s))
    snaps.sort(key=lambda x: x[0])
    return [s for _, s in snaps]


def _as_text(anchorset: set[str]) -> str:
    return " ".join(sorted(anchorset)) or "—"


async def _embed_into(embedder: Embedder, texts: list[str], cache: dict[str, list[float]]) -> None:
    fresh = [t for t in dict.fromkeys(texts) if t not in cache]
    if fresh:
        for t, v in zip(fresh, await embedder.embed(fresh)):
            if v:
                cache[t] = v


async def anchor_retrieval_backtest(embedder: Embedder, snapshots: list[set[str]], *, k: int = 5, top_n: int = 6, min_history: int = 4) -> dict[str, Any]:
    """Walk the snapshots; at each step predict the NEXT anchor set two ways —
    retrieval (kNN over past states, vote over what followed each neighbour) and
    persistence (the present set) — and score both against what actually came next.

    Returns precision/recall for each method overall, plus the headline
    ``new_anchor_recall``: the share of newly-appearing anchors each method foresaw
    (persistence is ~0 by construction; retrieval above 0 is real self-prediction).
    """
    sets = [set(s) for s in snapshots if s]
    n = len(sets)
    cache: dict[str, list[float]] = {}
    await _embed_into(embedder, [_as_text(s) for s in sets], cache)

    rows: list[dict[str, Any]] = []
    for i in range(min_history, n - 1):
        cur, nxt = sets[i], sets[i + 1]
        q = cache.get(_as_text(cur))
        if not q:
            continue
        sims: list[tuple[int, float]] = []
        for j in range(i):
            v = cache.get(_as_text(sets[j]))
            if v:
                c = _cosine(q, v)
                if c > 0.0:
                    sims.append((j, c))
        sims.sort(key=lambda x: -x[1])
        votes: dict[str, float] = {}
        for j, s in sims[:k]:
            for a in sets[j + 1]:
                votes[a] = votes.get(a, 0.0) + s
        pred_ret = set(sorted(votes, key=lambda a: -votes[a])[:top_n])
        rows.append({"cur": cur, "nxt": nxt, "ret": pred_ret, "per": set(cur)})

    def pr(pred: set[str], truth: set[str]) -> tuple[float, float]:
        if not pred:
            return 0.0, 0.0
        inter = len(pred & truth)
        return inter / len(pred), (inter / len(truth) if truth else 0.0)

    def agg(key: str) -> dict[str, float]:
        ps, rs = [], []
        for r in rows:
            p, rc = pr(r[key], r["nxt"])
            ps.append(p)
            rs.append(rc)
        return {"precision": round(sum(ps) / len(ps), 3) if ps else 0.0, "recall": round(sum(rs) / len(rs), 3) if rs else 0.0}

    def new_recall(key: str) -> float | None:
        caught = []
        for r in rows:
            appeared = r["nxt"] - r["cur"]
            if not appeared:
                continue
            caught.append(len((r[key] - r["cur"]) & appeared) / len(appeared))
        return round(sum(caught) / len(caught), 3) if caught else None

    return {
        "steps": len(rows),
        "retrieval": agg("ret"),
        "persistence": agg("per"),
        "new_anchor_recall": {"retrieval": new_recall("ret"), "persistence": new_recall("per")},
    }


async def anchor_generalization_backtest(embedder: Embedder, snapshots: list[set[str]], *, k: int = 5, top_n: int = 6, sim_threshold: float = 0.6, min_history: int = 4) -> dict[str, Any]:
    """The generalization question: of the anchors that newly appear, how many were
    *semantically* foreseeable — close to something we'd have predicted — even when
    the exact string was new? Exact recall asks "did we name it"; semantic recall
    asks "did we foresee its neighbourhood." If semantic >> exact, then most string-
    novelty is really variation on known themes, and generalization (the thing a
    learned model can do that echo can't) is the lever Rung 3 would pull. If both
    stay low, the novelty is genuine and the prize is thin even with generalization.
    """
    sets = [set(s) for s in snapshots if s]
    n = len(sets)
    set_cache: dict[str, list[float]] = {}
    await _embed_into(embedder, [_as_text(s) for s in sets], set_cache)
    anc_cache: dict[str, list[float]] = {}
    await _embed_into(embedder, sorted({a for s in sets for a in s}), anc_cache)

    def sem_hit(anchor: str, predset: set[str]) -> bool:
        av = anc_cache.get(anchor)
        if not av:
            return False
        return any(_cosine(av, anc_cache.get(p) or []) >= sim_threshold for p in predset)

    ex_ret, sem_ret, sem_per = [], [], []
    for i in range(min_history, n - 1):
        cur, nxt = sets[i], sets[i + 1]
        appeared = nxt - cur
        if not appeared:
            continue
        q = set_cache.get(_as_text(cur))
        if not q:
            continue
        sims = sorted(((j, _cosine(q, set_cache.get(_as_text(sets[j])) or [])) for j in range(i)), key=lambda x: -x[1])
        votes: dict[str, float] = {}
        for j, s in sims[:k]:
            if s <= 0:
                continue
            for a in sets[j + 1]:
                votes[a] = votes.get(a, 0.0) + s
        pred = set(sorted(votes, key=lambda a: -votes[a])[:top_n])
        ex_ret.append(len(pred & appeared) / len(appeared))
        sem_ret.append(sum(1 for a in appeared if sem_hit(a, pred)) / len(appeared))
        sem_per.append(sum(1 for a in appeared if sem_hit(a, cur)) / len(appeared))

    def m(x: list[float]) -> float | None:
        return round(sum(x) / len(x), 3) if x else None

    return {
        "change_steps": len(ex_ret),
        "sim_threshold": sim_threshold,
        "new_anchor_recall_exact": {"retrieval": m(ex_ret)},
        "new_anchor_recall_semantic": {"retrieval": m(sem_ret), "persistence": m(sem_per)},
    }


def transition_learnability(snapshots: list[set[str]]) -> dict[str, Any]:
    """Split every newly-appearing anchor into RECURRING (it had appeared somewhere
    earlier — the only kind any echo-based predictor could foresee) vs FIRST-TIME
    (genuinely novel — structurally unpredictable from the past). The recurring
    fraction is the *ceiling* on what retrieval prediction can ever achieve; the
    first-time fraction is the irreducible novelty in a resident's world.

    This is the number that reframes Rung 3: if most change is first-time, then a
    learned predictor's only possible edge over echo is *generalization* — foreseeing
    a never-seen anchor by analogy to similar ones — and most of what is predictable
    (the sticky steady state) needed no learning at all.
    """
    sets = [set(s) for s in snapshots if s]
    seen: set[str] = set()
    recurring = novel = 0
    for i in range(len(sets) - 1):
        for a in sets[i + 1] - sets[i]:
            if a in seen:
                recurring += 1
            else:
                novel += 1
        seen |= sets[i]
    total = recurring + novel
    return {"appeared": total, "recurring": recurring, "first_time": novel, "learnable_ceiling": round(recurring / total, 3) if total else None}


async def transition_learnability_semantic(embedder: Embedder, snapshots: list[set[str]], *, threshold: float = 0.7) -> dict[str, Any]:
    """``transition_learnability`` in CONCEPT space, not string space (reviewer fix).

    The string version counts a newly-appearing anchor as recurring only if the exact
    string was seen before — so "the question" / "question itself" / "the question's
    edge" are three first-time anchors for one concept, inflating apparent novelty.
    Here an appeared anchor is RECURRING if it is within ``threshold`` cosine of any
    anchor seen up to and including the current moment — i.e. the *concept* has
    appeared, however it's phrased. The gap between this and the string version is
    exactly the extractor's false-novelty inflation; what survives here is novelty in
    concept space, the only kind that bounds what any predictor could foresee.
    """
    sets = [set(s) for s in snapshots if s]
    cache: dict[str, list[float]] = {}
    await _embed_into(embedder, sorted({a for s in sets for a in s}), cache)
    seen_vecs: list[list[float]] = []
    recurring = novel = 0
    for i in range(len(sets) - 1):
        for a in sets[i]:  # the current concept is "seen" before we judge the next step
            v = cache.get(a)
            if v:
                seen_vecs.append(v)
        for a in sets[i + 1] - sets[i]:
            v = cache.get(a)
            if v and any(_cosine(v, sv) >= threshold for sv in seen_vecs):
                recurring += 1
            else:
                novel += 1
    total = recurring + novel
    return {"appeared": total, "recurring": recurring, "first_time": novel, "learnable_ceiling": round(recurring / total, 3) if total else None, "threshold": threshold}


async def backtest_from_ledger(embedder: Embedder, memory_dir: Any, *, k: int = 5, top_n: int = 6) -> dict[str, Any]:
    """Convenience: run the anchor retrieval backtest over a resident's ledger."""
    return await anchor_retrieval_backtest(embedder, anchor_snapshots(load_runtime_events(memory_dir)), k=k, top_n=top_n)

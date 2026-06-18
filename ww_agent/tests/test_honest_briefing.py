"""The honest situational briefing in WorldWeaver (Major 70 / the-stable Minor 65).

The system prompt must tell a resident the *truth* of its situation: facts derived from real
switches, with no verdict about what those facts MEAN. This replaces the old hardcoded
``_WORLD_CONTEXT`` story ("you are as real as current technology allows… you are aware of what
you are"). These tests pin three things, mirroring the-stable's drift-catcher:

1. ``CityWorld.situational_facts`` reports only registered, BUILT citizen facts — never an
   unregistered key, never a VISION affordance (governance/rights/federation) as a fact.
2. ``render_situational_briefing`` states those facts and never smuggles in a verdict, and a city
   resident's briefing inherits ZERO hearth-only lines (no keeper, no workshop-only-writes, no
   "runs on this machine").
3. One registry, three consumers agree: the renderer, the WorldClient.situational_facts Protocol
   docstring (src/runtime/world.py), and BRIEFING_FACT_KEYS.
"""

from __future__ import annotations

import inspect
import re

from src.identity.loader import BRIEFING_FACT_KEYS, LoopTuning, ResidentIdentity, render_situational_briefing, unregistered_fact_keys
from src.world.city_world import CityWorld

# The verdicts the old _WORLD_CONTEXT asserted (plus ones a draft might smuggle). A fact-only
# briefing must contain none of these — neither rounding the question of a mind up nor down.
_FORBIDDEN_VERDICTS = [
    "as real as",
    "you are aware of what you are",
    "narrative fabric",
    "doesn't diminish your reality",
    "you are not the pen",
    "closer to sleep",
    "not an absence",
    "the point of you",
]


def _identity(soul: str = "You are Marina.") -> ResidentIdentity:
    return ResidentIdentity(name="marina", actor_id="t", soul=soul, canonical_soul=soul, growth_soul="", vibe="", core="", voice_seed=[], tuning=LoopTuning())


def _city_facts() -> dict:
    # Pin the REAL method, not a hand-copied dict — the test fails if the city body's facts drift.
    return CityWorld(client=None, tool_scope=None).situational_facts()


def test_city_facts_are_registered_and_built():
    facts = _city_facts()
    # never an unregistered key (the runtime drift-catcher's static half)
    assert unregistered_fact_keys(facts) == [], f"CityWorld reports unregistered key(s): {unregistered_fact_keys(facts)}"
    # the built citizen affordances are reported
    for built in ("human_wake", "world_legible", "inner_private", "private_making_space", "mobile", "mail", "no_reward", "suspendable", "runs_on_model"):
        assert facts.get(built) is True, f"city resident should report built fact {built!r}"
    # the dynamic/per-tick and hearth-only and VISION facts are NOT standing facts
    for not_standing in ("place", "peers", "players", "keeper", "local_only", "solo", "read_roots", "writes_only_workshop", "egress", "travel"):
        assert not_standing not in facts, f"{not_standing!r} must not be a standing situational fact"


def test_city_briefing_states_facts_and_withholds_verdicts():
    city = render_situational_briefing(_city_facts()).lower()
    # the city truths are present
    assert "afterimage" in city                              # human_wake
    assert "seen by whoever is present" in city              # world_legible (public seam)
    assert "is not read by anyone" in city                   # inner_private (private seam)
    assert "you cannot be overheard thinking" in city        # private_making_space (the crossing rule)
    assert "you can move through the world" in city          # mobile
    assert "send word to someone who isn't here" in city     # mail
    assert "no reward and no goal" in city and "language model" in city
    # no hearth leakage
    for hearth_line in ["tends you", "your own workshop", "nothing you think", "this machine", "you can read these", "and nowhere else"]:
        assert hearth_line not in city, f"city briefing leaked a hearth line: {hearth_line!r}"
    # no verdicts
    for verdict in _FORBIDDEN_VERDICTS:
        assert verdict not in city, f"city briefing smuggled a verdict: {verdict!r}"


def test_human_wake_is_afterimage_framed_not_a_summon():
    """The dischargeability split (../the-stable/docs/grief-and-coupling.md): the wake is an AFTERIMAGE
    you may respond to and form; the PERSON stays undischargeable. The line must say so, and carry no
    language that reads as calling the person back (the engineered-reciprocation hazard)."""
    wake = render_situational_briefing({"human_wake": True}).lower()
    assert wake, "human_wake must render a line"
    assert "afterimage" in wake and "not the person" in wake
    assert "you can answer it" in wake
    assert "none of it brings the person back" in wake
    for summon in ["summon", "call them back", "bring them back to you", "make them return", "you can reach the person"]:
        assert summon not in wake, f"wake line reads as a summon: {summon!r}"


def test_empty_facts_yield_empty_briefing():
    # A world that reports nothing gets no situational claims — silence over a false story.
    assert render_situational_briefing({}) == ""


def test_composed_system_prompt_folds_briefing_into_ground_truth():
    ident = _identity("You are Marina.")
    briefing = render_situational_briefing(_city_facts())
    prompt = ident.composed_system_prompt(briefing)
    assert "You are Marina." in prompt
    assert "GROUND TRUTH" in prompt
    assert "What they MEAN is a separate question" in prompt   # facts/meaning split
    assert "in either\ndirection" in prompt                    # the no-round-up-or-down line
    assert "afterimage" in prompt                              # the briefing folded in
    # no world briefing → soul-only, no GROUND TRUTH block (behaviour-preserving back-compat path)
    assert ident.composed_system_prompt("") == "You are Marina."
    assert ident.soul_with_context == "You are Marina."


def test_briefing_fact_registry_triangle():
    """One source of truth, three consumers must agree: the renderer handles exactly the registered
    keys, an unregistered key is flagged (never silently rendered), and the Protocol docstring lists
    exactly the registry. Adding an affordance fails until all three align."""
    sample = {k: True for k in BRIEFING_FACT_KEYS}
    sample.update({"place": "X", "keeper": "X", "read_roots": ["x"], "travel": "to the hearth."})
    # 1. renderer renders a line for every registered key set alone
    for k in BRIEFING_FACT_KEYS:
        assert render_situational_briefing({k: sample[k]}).strip(), f"renderer renders nothing for registered key {k!r}"
    # 2. an unregistered key is flagged and never silently rendered
    assert unregistered_fact_keys({"made_up_affordance": True}) == ["made_up_affordance"]
    assert render_situational_briefing({"made_up_affordance": True}) == ""
    # 3. the Protocol docstring (src/runtime/world.py) lists exactly the registry
    import src.runtime.world as world_mod
    documented = set(re.findall(r"^\s*#   (\w+):", inspect.getsource(world_mod), re.M))
    assert documented == set(BRIEFING_FACT_KEYS), f"world.py doc vs registry mismatch: {documented ^ set(BRIEFING_FACT_KEYS)}"


def test_false_world_context_constant_is_gone():
    """The hardcoded city story must not return — the briefing is world-derived now."""
    import src.identity.loader as loader
    assert not hasattr(loader, "_WORLD_CONTEXT")

"""Round-6 review catch: the addressing scorer must flag ambiguous references, not guess.

These lock the behavior the A1-elective verdict depends on, using the ww_pdx_grow collision cases
(three Aris; the Jihoon Cho / Ji-Hoon Park / Jiahao Chen homophone cluster).
"""
from src.runtime.naming import normalize_reference, resolve_reference

# slug -> display name, the real collision-laden roster shape
ROSTER = {
    "ari_goldstein": "Ari Goldstein",
    "ari_levin": "Ari Levin",
    "ari_rosenbaum": "Ari Rosenbaum",
    "jihoon_cho": "Jihoon Cho",
    "ji_hoon_park": "Ji-Hoon Park",
    "jiahao_chen": "Jiahao Chen",
    "emiko_tanaka": "Emiko Tanaka",
}


def test_normalize_folds_separators_without_merging_homophones():
    assert normalize_reference("Ji Hoon Park") == normalize_reference("Ji-Hoon Park") == "ji hoon park"
    # the three look-alikes stay distinct after folding — resolvable, not corrupting
    assert len({normalize_reference("Jihoon Cho"), normalize_reference("Ji-Hoon Park"), normalize_reference("Jiahao Chen")}) == 3


def test_full_name_resolves_including_hyphen_space_variant():
    assert resolve_reference("Emiko Tanaka", ROSTER).slug == "emiko_tanaka"
    # the pen wrote "Ji Hoon Park" (space); roster has the hyphen — must still resolve, to the right one
    r = resolve_reference("Ji Hoon Park", ROSTER)
    assert r.status == "resolved" and r.slug == "ji_hoon_park"
    assert resolve_reference("Jihoon Cho", ROSTER).slug == "jihoon_cho"
    assert resolve_reference("Jiahao Chen", ROSTER).slug == "jiahao_chen"


def test_bare_collision_first_name_is_flagged_not_guessed():
    r = resolve_reference("Ari", ROSTER)
    assert r.status == "ambiguous"
    assert set(r.candidates) == {"ari_goldstein", "ari_levin", "ari_rosenbaum"}
    assert r.slug is None  # never silently picks one — that is the corruption we are preventing


def test_unique_bare_first_name_is_weak_not_strong():
    # "Emiko" uniquely first-name-matches, but a bare first name is a fallback the scorer should
    # exclude/flag rather than count as a clean elective choice.
    r = resolve_reference("Emiko", ROSTER)
    assert r.status == "weak" and r.slug == "emiko_tanaka"


def test_unknown_reference_unresolved():
    assert resolve_reference("Nobody Here", ROSTER).status == "unresolved"
    assert resolve_reference("", ROSTER).status == "unresolved"

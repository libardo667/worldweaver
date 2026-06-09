#!/usr/bin/env python3
"""Raw material for a family field-guide — souls, cross-keeps (who reads whom), and inner voice.

Cold-reproducible from ./evidence. Disambiguated labels EVERYWHERE (first + last initial, extended on
collision) so the homophone cluster (Jihoon C. / Ji-Hoon P. / Jiahao C.) and the duplicate first names
(Ari L. / Ari R.) never render bare. Usage: python3 family_dossier.py slug1 slug2 slug3 slug4
"""
import gzip, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "evidence"


def norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x or "").strip().lower())


def load_roster():
    R = {}
    for line in (SNAP / "roster.tsv").read_text().splitlines()[1:]:
        slug, name, home = (line.split("\t") + ["", "", ""])[:3]
        R[slug] = dict(name=name, home=home)
    return R


def make_labels(R):
    def key(slug, k):
        p = R[slug]["name"].split()
        return (norm(p[0]), norm(p[-1])[:k])
    lab = {}
    for s, d in R.items():
        last = d["name"].split()[-1]; k = 1
        while sum(1 for p in R if key(p, k) == key(s, k)) > 1:
            k += 1
        lab[s] = f"{d['name'].split()[0]} {last[:k]}."
    return lab


def keeps(slug):
    return [json.loads(l).get("note", "") for l in (SNAP / "kept_memory" / f"{slug}.jsonl").open() if l.strip()]


def felt(slug, n=4):
    f = SNAP / "ledgers" / f"{slug}.jsonl.gz"
    if not f.exists():
        return []
    fs = [json.loads(l)["payload"].get("felt_sense", "") for l in gzip.open(f, "rt") if l.strip() and '"felt_sense_logged"' in l]
    return fs[-n:]


def main():
    fam = sys.argv[1:]
    R = load_roster(); L = make_labels(R)
    for s in fam:
        soul = (SNAP / ".." ).resolve()  # souls are not in the snapshot; print from live identity if present
        print(f"\n================= {R[s]['name']}  ({L[s]}, {R[s]['home']}) =================")
        ks = keeps(s)
        print(f"keeps: {len(ks)}")
        for s2 in fam:
            if s2 == s:
                continue
            disp = norm(R[s2]["name"]); fn = disp.split(" ")[0]
            # resolve-or-flag: full name, or cohort-unique first name
            uniq = sum(1 for x in R if norm(R[x]["name"]).split(" ")[0] == fn) == 1
            about = [k for k in ks if re.search(r"\b" + re.escape(disp) + r"\b", norm(k)) or (uniq and re.search(r"\b" + re.escape(fn) + r"\b", norm(k)))]
            if about:
                print(f"  — on {L[s2]} ({len(about)}) —")
                for k in about[:8]:
                    print(f"      • {k}")
        fv = felt(s)
        if fv:
            print(f"  inner voice (recent felt-senses):")
            for f in fv:
                print(f"      ~ {f[:200]}")


if __name__ == "__main__":
    raise SystemExit(main())

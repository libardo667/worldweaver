# WorldWeaver public-readiness audit

Date: 2026-07-20

WorldWeaver commit reviewed: `fce1873`

Hekswerk site commit reviewed: `1157ab1`

This audit asks whether an unrelated person can understand, inspect, try, and respond to WorldWeaver safely.
It does not decide whether the project's ideas are correct, and it does not authorize a public resident run.

## Verdict

WorldWeaver is ready to be shown to selected outsiders for source and architecture review. It is not yet ready
to promise a working fresh-clone demonstration, invite unknown people into Alderbank, or operate Alderbank as
an unattended public service.

The project already has unusually useful foundations for a solo prototype: a plain current manual, a full CI
gate, public research records, separate public and steward surfaces, signed node identities, a real HTTPS test
deployment, and explicit statements about unfinished security. The largest gaps are not a lack of code. They
are a broken newcomer path, drift between preserved exhibits and current architecture, missing participation
and security instructions, and a development web server exposed as the live client.

## Four different readiness levels

| Level | Rating | What the rating means |
| --- | --- | --- |
| Outside source review | **Conditionally ready** | A reviewer can inspect the public code, tests, manual, and research record now. The repository does not yet tell them what kind of review is wanted or how to report security concerns. |
| Fresh-clone local demonstration | **Not ready** | The documented Alderbank command depends on ignored local shard configuration that a new clone does not contain. There is no supported bootstrap step in the tutorial. |
| Invited, supervised playtest | **Not ready yet** | The town works for the current operator, but the public client is served by Vite development mode and account recovery, privacy, moderation, reporting, and shutdown expectations are incomplete. |
| Unattended public service | **Not ready** | The deployment remains a single-computer test. It lacks the production client, operational policy, abuse handling, tested recovery, and independent-host proof needed for an open service. |

These ratings are deliberately separate. Fixing the GitHub landing page does not make the node production-safe,
and closing production blockers is not required before asking a small number of experts to review source.

## What is already strong

- `python dev.py check` covers engine lint, two web builds, engine tests, agent lint, and agent tests. The
  GitHub gate also scans the tracked tree for a narrow set of public leaks.
- GitHub secret scanning and push protection are enabled.
- The current manual uses a small Diátaxis-style surface: tutorial, how-to guides, explanations, and reference.
- The Docusaurus site builds successfully against the current `worldweaver/docs/` directory and preserves the
  Hekswerk visual system without copying the technical manual.
- The live directory and Alderbank API answer over HTTPS, use a separately admitted signed node identity, and
  report healthy as of this audit.
- Runtime homes, shard `.env` files, node private keys, prompt traces, and private resident memory are ignored.
- `research/README.md` explicitly labels the research tree as public and describes its copied evidence model.
- The current architecture documentation states that federation is not resident ownership and that generation
  fencing cannot prove a malicious former host erased a copy.

## Findings

### PR-01 — The advertised local tutorial cannot start from a fresh clone

Severity: **blocker for local demonstration**

Remediation status: **implemented in source on 2026-07-20; clean Docker proof pending**

Evidence:

- `README.md` and `docs/tutorials/run-a-local-town.md` instruct a newcomer to run
  `python dev.py weave-up --city ww_alderbank` after installation.
- The tracked `shards/ww_alderbank/` contains its Compose file, README, `.gitignore`, and public `node.json`, but
  not the required `.env` or copied city data.
- `worldweaver_engine/scripts/dev.py::_validate_shard_spec` refuses `weave-up` when the shard `.env` is absent.
- The tutorial contains no initialization or demo-materialization command.

Disposition:

`python dev.py demo-init` now creates fresh local-only secrets and node identities, copies Alderbank's tracked
pack, leaves residents absent, does nothing on a complete second run, and refuses unmarked or partial existing
state. The tutorial uses it before `weave-up`. Its filesystem behavior is covered by tests; the remaining proof
is to run the documented sequence in a clean exported checkout with Docker.

### PR-02 — The live public client is Vite development mode

Severity: **blocker for invited playtest and public service**

Evidence:

The live `https://world-weaver.org` response includes `/@vite/client`, React refresh injection, and source
development modules. The current local client Compose service also runs `npm run dev`. Major 18 already records
replacement of the development client server as unfinished.

Disposition:

Serve a built `client-public/dist` from a small static server or reverse proxy with immutable assets and a
documented deployment version. Keep development hot reload local.

### PR-03 — Public account expectations are not complete

Severity: **blocker for unknown participants**

Evidence:

- The live node permits registration while email delivery is unconfigured. A participant can create an account
  but cannot receive the password-reset email described by the client.
- The terms say only that participants must not harass people or agents, must respect the collaborative fiction,
  and must participate in good faith. They do not explain email storage, public speech retention, account
  deletion, data export, moderation, reporting, or operator contact.
- No account deletion or data-export route was found.
- No user-facing report, mute, block, or steward moderation flow was found.

Disposition:

Before inviting unknown participants, either configure and prove email recovery or use an explicit disposable
invitation-account model. Add a short privacy and retention notice, an operator contact/report path, a steward
stop procedure, and a decision about account deletion and export. A small supervised session with known testers
may use a narrower written protocol; it must not be presented as an open service.

### PR-04 — Preserved exhibits contradict the current architecture without a strong historical label

Severity: **high accuracy risk**

Remediation status: **resolved on 2026-07-20**

Evidence:

At the time of the audit, the Hekswerk research page actively recommended preserved June exhibits. Those
exhibits described:

- `the-stable` as the active home of familiars;
- `prune` as a separate repository and planning system;
- the substrate as a mind and the model as a proven or nearly proven "swappable pen";
- the federation as the party that "holds the soul"; and
- CognitiveCore mechanisms as established mental or safety mechanisms.

Current WorldWeaver work explicitly rejects several of these claims or treats them as unproven questions. The
files are legitimate dated artifacts and should not be silently rewritten. Presenting them in the selected
current research path without a prominent superseded-context notice makes the public architecture misleading.

Disposition:

After review with the project owner, the obsolete exhibits were removed from the published Hekswerk source
instead of being kept as a prominent current surface. Their source remains available in Git history. The current
research page now states why those exhibits were withdrawn and points to the current manual and CognitiveCore
audit.

### PR-05 — GitHub has almost no discovery or participation metadata

Severity: **high discoverability gap**

Evidence as of the audit:

- description: `unified project repo for worldweaver engine and agent runtime with example shards and residents`;
- no homepage URL;
- no repository topics;
- Discussions disabled;
- zero issues and no issue templates;
- no `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, or Code of Conduct.

Disposition:

Set a plain description, link `https://www.hekswerk.com/worldweaver`, and add a restrained set of accurate
topics. Add one short contribution guide, one security-reporting policy, and two or three issue forms for setup
failure, design criticism, and security concerns. Enable Discussions only when there is a concrete first prompt
and capacity to respond. Do not create empty corporate process.

### PR-06 — The public doorway describes concepts but shows no experience

Severity: **high conversion gap**

Evidence:

The repository README contains no screenshot, recording, diagram, or sample receipt. The Hekswerk homepage uses
the logo and four conceptual claims but no image of Alderbank or one concrete human/resident consequence. A
newcomer reaches unfamiliar words before seeing the software do anything.

Disposition:

After the clean-clone path works, record one short, reproducible Alderbank sequence using only public scene
information. Add a small architecture diagram and a status table. Keep the source commit and limitations beside
the media. Do not use private resident prose or prompt traces.

### PR-07 — Current documentation and deployed documentation can drift

Severity: **high accuracy and reproducibility gap**

Remediation status: **partly resolved on 2026-07-20**

Evidence:

- `docs/index.md` still lists independent signed node identities as unfinished even though the code, tests, and
  live deployment use them.
- The Hekswerk workflow checks out whatever WorldWeaver `main` contains when Hekswerk happens to deploy. A
  WorldWeaver documentation change does not itself rebuild the site.
- The deployed site does not identify the WorldWeaver commit used to build its manual.
- The Hekswerk build warns rather than fails on broken Markdown links.

Disposition:

The known signed-node status drift is corrected. Make WorldWeaver documentation changes trigger or request a
site build, record the included WorldWeaver commit in the result, and fail on broken documentation links. Keep
WorldWeaver's own `docs/` canonical.

### PR-08 — Maintained checked-in development shards retain broad backend bindings

Severity: **high local safety gap**

Remediation status: **resolved on 2026-07-20**

Evidence:

New folders generated by `new_shard.py` bind backend ports to `127.0.0.1`. The tracked `ww_alderbank`, `ww_sfo`,
`ww_pdx`, and `ww_world` Compose files still use `${BACKEND_PORT}:8000`, which may expose them beyond loopback
depending on the host firewall. The local tutorial starts the tracked Alderbank and world folders.

Disposition:

All four checked-in Compose files now use the generated loopback default, with a regression test covering the
tracked folders. Public ingress remains an explicit tunnel/operator choice.

### PR-09 — The publication leak check is helpful but incomplete

Severity: **medium privacy gap**

Evidence:

`scripts/check-public.sh` checks tracked files for two historical personal-path prefixes and three token shapes.
It does not scan Git history, generic private keys, Cloudflare credentials, emails, broader personal paths, or
compressed research evidence. GitHub secret scanning and push protection provide a useful second layer, but
non-provider patterns and validity checks are disabled.

The tracked research tree deliberately includes compressed ledgers and recordings. `research/README.md` calls
them public, secret-free evidence, but many run directories lack a nearby data card stating whether their
participants are synthetic, what prose is included, and what publication review occurred.

Disposition:

Expand the local check without printing suspected secret values. Add a small data card to every publicly linked
run before promoting it. Do not delete cold-verification evidence merely because it is large or compressed.

### PR-10 — The public client has no browser behavior or accessibility harness

Severity: **medium quality gap**

Evidence:

`client-public/package.json` builds TypeScript and Vite but defines no unit, browser, or accessibility test. The
engine tests cover contracts, but they cannot establish that a new person can register, choose a name, move,
make, use a stoop, recover from errors, or navigate with a keyboard in the built client.

Disposition:

Add a deliberately small browser smoke suite for anonymous entry, account entry, the tutorial's object loop,
keyboard navigation, and visible API failures. Do not attempt exhaustive frontend coverage before the first
demonstration.

### PR-11 — Creative-artifact licensing is described but not packaged

Severity: **medium legal clarity gap**

Evidence:

The repository includes AGPL license files and says resident-produced creative artifacts use CC BY-SA 4.0, but
does not include the CC license text or a file-level scope manifest. Raw research ledgers mix software events and
generated prose, making the boundary difficult for a reuser to determine.

Disposition:

Add `LICENSES/CC-BY-SA-4.0.txt` and a short scope document identifying which tracked paths, if any, contain
separately licensed creative work. Do not retroactively assign resident authorship where provenance is unclear.

### PR-12 — Minor live diagnostics expose deployment internals

Severity: **low information-exposure gap**

Remediation status: **resolved in source on 2026-07-20; deployment pending**

Evidence:

The public readiness response includes `http://host.docker.internal:9100` and whether the backend process has an
inference model or key. These are not credentials, but public readiness needs less operator detail than a private
steward diagnostic.

Disposition:

The public response no longer returns the internal federation URL or resident inference key/model state. It
retains the intentionally public shard URL and participant-relevant readiness checks. The live container must be
rebuilt before the deployed response reflects this change.

### PR-13 — Two site checkouts could have caused accidental rollback

Severity: **resolved during audit**

Evidence:

The old Windows checkout was clean but stopped at `ce048a1`, before the Docusaurus conversion. The WSL sibling
checkout was clean and current at `1157ab1`.

Disposition:

The user designated the WSL checkout authoritative and explicitly authorized removing the Windows copy. The
Windows checkout was deleted during this audit. The WSL checkout remains clean and matches `origin/main`.

## Recommended implementation order

Each numbered slice should be independently reviewable and committed separately.

1. **Truth and safety corrections:** fix current documentation drift, label or temporarily de-select obsolete
   exhibits, narrow public readiness output, and bind maintained local backends to loopback.
2. **Reproducible local entry:** build and test a non-destructive Alderbank demo bootstrap; rewrite the tutorial
   around a clean checkout.
3. **Repository invitation:** update description, topics, and homepage; add short contribution and security
   documents plus focused issue forms.
4. **Production-shaped demonstration surface:** serve a built public client, add the small browser smoke suite,
   and display the deployed commit and experimental status.
5. **Participation boundary:** write privacy/retention expectations, choose recovery and reporting paths, and
   prepare a supervised playtest stop procedure.
6. **One honest demonstration:** capture the bounded Alderbank object/stoop sequence and add the status table and
   small architecture diagram.
7. **Five informed responses:** only then begin the bounded outreach item. Keep residents stopped unless a
   separate reviewed session explicitly needs them.

## What should not happen during this work

- Do not resume real-resident hearth migration or add deletion machinery.
- Do not silently rewrite dated research records to make the project look more consistent.
- Do not publish private resident ledgers, prompts, workshops, correspondence, or operator screens as a demo.
- Do not call the live single-computer topology a secure decentralized network.
- Do not mass-promote the repository before one unrelated person can complete the clean-clone path.
- Do not add large-company ceremony that a solo maintainer cannot realistically operate.

## Audit method and limits

This review inspected the tracked repository, current documentation, work-item catalog, GitHub repository
metadata and security settings, CI workflows, current WSL Hekswerk source, a clean Docusaurus production build,
and read-only responses from the live Hekswerk, directory, and Alderbank URLs. It did not create an account,
mutate the live town, read private resident prose, decompress and inspect every research ledger, scan all Git
history with a dedicated secret scanner, conduct penetration testing, or recruit an outside newcomer. Those
limits are part of the findings rather than evidence that the omitted surfaces are safe.

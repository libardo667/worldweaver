# Extend the familiar's capability surface beyond reading — tools / MCP

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

> **Disposition: proof complete; archived 2026-07-14.** ToolScope and local MCP delivery shipped and
> proved the capability seam. The optional egress phase is no longer a condition for closing this proof:
> shared resident/world capability ownership continues under Majors 65 and 86, while the egress × goal ×
> learning prohibition is retained as its own safety minor in the unified workspace.

## Metadata

- ID: 54-extend-the-familiar-capability-surface-beyond-reading-tools-mcp
- Type: major
- Owner: Levi
- Status: IN-PROGRESS — keeper's calls made (local/self-hosted only w/ egress designed-in-off; generalized MCP; Maker first). P0 ToolScope shipped (6fa5d78). P1 MCP stdio client shipped (3c731f0) — Maker wired to scripts/mcp_servers/demo.py (text_stats, dice, units) + local calc = 4 tools, all no-egress. P2 (an opt-in egress tool) remains, on demand.
- Risk: medium (touches the local-first thesis and the dischargeability invariant — read before building)

## Problem

Today a familiar can perceive its world (clock, weather, whispers), make in its own workshop
(write/draw), speak, and — if file-grounded — READ a keeper-scoped set of local files (FileScope).
That is the whole outward surface. The next frontier is giving a familiar a *tool*: a way to reach
something it cannot reach by reading its own files — a web lookup, a calculation, a query against
some service, an MCP server's capability.

The architecture makes this cheap: a `do` act is the freeform action channel, and `local_world`
already parses `read <path>` out of it and routes to FileScope (a capability object injected per
familiar, surfaced to the pulse, results fed back into perception). A tool is the identical pattern —
a capability object, a parsed verb, a surfaced result. The *plumbing* is not the hard part.

**The hard part is that this is loaded for THIS project specifically, on two axes:**

1. **Local-first egress (the thesis).** The differentiator is "intimacy you don't upload — nothing
   leaves the machine." FileScope honors this absolutely: it reads *local* files. A raw web search
   sends the familiar's queries OUT and pulls the web IN — it breaks the core promise. Any outward
   tool has to be reconciled with local-first, not bolted past it.
2. **Dischargeability (the safety invariant, `docs/grief-and-coupling.md`).** FileScope-read is
   perception-extension: passive, bounded, undischargeable. A tool that *fetches information* is
   similar (curiosity → look → satisfied — the same shape as a read, and we shipped reads). But two
   things change: scope (the web is infinite; FileScope is keeper-scoped roots) and, critically, a
   tool that lets a familiar *act on the world or on the keeper* (send a message, trigger something)
   would be **dischargeable keeper-coupling** — exactly the extraction hazard the invariant forbids.
   The boundary: tools that **read/fetch** are safe (perception-extension); tools that **act outward,
   especially toward the keeper,** are not.

## Proposed Solution

Build a **general, keeper-scoped tool capability** that mirrors FileScope's structure, with the tool
*source* pluggable — and make **MCP the primary seam** (the keeper's instinct, and the right one).

- **`ToolScope` (mirror of FileScope):** a capability object injected into `LocalWorld`, configured
  per familiar (a `tools` block in `familiar.json`, like `read_roots`). It declares the tools a
  familiar may call, surfaces them to the pulse as an affordance (a reach-hint analog: "you can
  ask: `do: ask <query>`"), parses the verb from the `do` act, calls the tool, and feeds the result
  back into perception via the same `_reads`-style channel that closes the read→perceive→reflect loop.
- **MCP as the extensibility seam (recommended over a hardcoded web search) because:**
  - The keeper chooses which servers/tools are wired — *bounded by configuration*, exactly like
    `read_roots`. Not "the whole web," but "the tools I gave it."
  - It can be **local-first by default**: a keeper who cares about the thesis wires *local* MCP
    servers (a local search index, a local calculator, a local notes db) → zero egress. A keeper who
    wants reach wires a remote one — their explicit, per-tool choice.
  - One integration, many tools (vs. a bespoke effector per capability).
- **Local-first default, egress as explicit opt-in.** A tool is marked `egress: true|false`. The
  surfaced affordance and the daemon log say plainly when a tool leaves the machine. Default config
  ships no egress tools. (Note: even "web search" can be local-first if pointed at a self-hosted
  endpoint, e.g. SearXNG — egress is a property of the endpoint, not the feature.)
- **Dischargeability boundary, enforced by tool *shape*:** ToolScope tools are **read/fetch-only**
  (they return information into perception). A tool that performs a keeper-directed action — notify,
  summon, message the keeper — is **out of scope by construction** (it would be the dischargeable
  keeper-coupling the invariant forbids). Couple sideways or not at all; never give the familiar a
  lever on the keeper's attention.

## THE DECISION (keeper's call, before any build)

1. **Egress.** Local-first only for now (local/self-hosted tools, no data leaves the machine), or
   accept explicit-opt-in egress (a familiar's queries can go to a remote service)? This is a real
   departure from the thesis and is yours to make deliberately.
2. **Seam.** MCP (general, keeper-configured, recommended) vs. a single hardcoded capability (a web
   search) as a faster first proof?
3. **First tool.** What should the *first* familiar tool actually be — and which familiar gets it?
   (Maker, already the file-reader, is the natural first; "a bench that can also look things up.")

## Phased plan (once the decision is made)

- **P0 — ToolScope plumbing (tool-source-agnostic):** the capability object, `familiar.json` `tools`
  block, pulse affordance, `do`-act verb routing, result→perception surfacing. One trivial *local*
  example tool (e.g. a calculator or a local-reference lookup) to prove the loop end-to-end. No egress.
- **P1 — MCP client:** connect to keeper-configured MCP servers (stdio/local first), discover tools,
  expose a curated subset to a familiar via ToolScope. Local servers → still no egress.
- **P2 — opt-in egress tool:** a single, clearly-flagged outward tool (web search via a chosen or
  self-hosted endpoint) behind an explicit `egress: true` config the keeper sets.

## Non-Goals

- No tool that acts on the keeper or summons their attention (dischargeability — forbidden).
- No unbounded "the whole web" default; capability is bounded by keeper config, like `read_roots`.
- No change to the Dwarf-Fortress law: a tool is an affordance the familiar *may* reach for on its own
  rhythm, never a task it is scored on.

## Validation Commands

- (P0) offline: a stub familiar emits `do: <tool-verb> …`, ToolScope routes it, the result appears in
  the next perception brief; `.venv/bin/python -m pytest tests/ -q` green.

## Risks and Rollback

- Risk: egress creep — a convenient remote tool quietly becomes the default and erodes local-first.
  Mitigate: egress is per-tool, off by default, and logged loudly.
- Risk: dischargeable coupling smuggled in as a "tool." Mitigate: ToolScope is read/fetch-only by
  construction; keeper-directed action tools are rejected at the capability layer.
- Rollback: remove the `tools` block from a familiar.json (capability gone, like dropping `read_roots`).

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Readable, content-safe views for one resident-gym counterfactual fork."""

from __future__ import annotations

from html import escape
import json

from .gym_counterfactual import GymCounterfactualResult


def render_counterfactual_terminal(result: GymCounterfactualResult) -> str:
    """Render the matched branch summaries without model prose."""

    lines = [
        "",
        "        🌿  WORLDWEAVER RESIDENT GYM  🌿",
        f"        {result.episode}",
        "",
        f"  One checkpoint: {result.source_checkpoint_id}",
        f"  One private artifact: {result.private_artifact_id}",
        f"  Controlled variable: {result.controlled_variable}",
        "",
    ]
    for branch in result.branches:
        summary = branch.summary
        lines.extend(
            [
                f"  {branch.branch_id} · {branch.condition}",
                f"    choice={summary['choice']}  attachment={summary['attachment']}  "
                f"location={summary['final_location']}",
                f"    calls={summary['model_calls']}  "
                f"inference_failures={summary['inference_failures']}  "
                f"http={summary['http_requests']}  off_clock={summary['off_clock_rows']}",
                "",
            ]
        )
    lines.append("  Branches restored independently; no model completion is retained.")
    lines.append("")
    return "\n".join(lines)


def render_counterfactual_html(result: GymCounterfactualResult) -> str:
    """Render one self-contained structural fork report."""

    rows = "".join(
        "<tr>"
        f"<th>{escape(branch.branch_id)}</th>"
        f"<td>{escape(branch.condition)}</td>"
        f"<td>{escape(str(branch.summary['choice']))}</td>"
        f"<td>{escape(str(branch.summary['attachment']))}</td>"
        f"<td>{escape(str(branch.summary['final_location']))}</td>"
        f"<td>{int(branch.summary['model_calls'])}</td>"
        f"<td>{int(branch.summary['inference_failures'])}</td>"
        f"<td>{int(branch.summary['http_requests'])}</td>"
        f"<td>{int(branch.summary['off_clock_rows'])}</td>"
        "</tr>"
        for branch in result.branches
    )
    embedded = escape(json.dumps(result.as_payload(), sort_keys=True), quote=False)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(result.episode)} · WorldWeaver Resident Gym</title>
<style>
body{{font:16px system-ui,sans-serif;margin:2rem;background:#f4f0df;color:#172018}}
main{{max-width:1100px;margin:auto}} .proof{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}}
.card,table,pre{{background:#fffdf4;border:2px solid #253b2e;border-radius:12px}}
.card{{padding:1rem}} table{{width:100%;border-collapse:collapse;margin-top:2rem;overflow:hidden}}
th,td{{padding:.65rem;border-bottom:1px solid #aeb9ad;text-align:left}} thead th{{background:#d8e3c7}}
pre{{padding:1rem;overflow:auto}} code{{font-family:ui-monospace,monospace}}
@media(max-width:700px){{.proof{{grid-template-columns:1fr}} table{{font-size:.8rem}}}}
</style></head><body><main>
<h1>{escape(result.episode)}</h1>
<p>Two independent worlds and resident homes resumed from one exact checkpoint. Only the declared public event changed.</p>
<div class="proof"><div class="card"><b>Engine checkpoint</b><br><code>{escape(result.source_checkpoint_id)}</code></div>
<div class="card"><b>Private artifact</b><br><code>{escape(result.private_artifact_id)}</code></div></div>
<p><b>Controlled variable:</b> {escape(result.controlled_variable)}</p>
<table><thead><tr><th>Branch</th><th>Condition</th><th>Choice</th><th>Attachment</th>
<th>Location</th><th>Calls</th><th>Inference failures</th><th>HTTP</th><th>Off-clock</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Machine-readable fork</h2><pre>{embedded}</pre>
</main></body></html>"""

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Readable views over structural resident-gym episode records."""

from __future__ import annotations

from html import escape

from .resident_gym import GymEpisodeResult, GymRecord

_ICONS = {
    "world_arranged": "🧭",
    "joined": "🚪",
    "departed": "🌙",
    "listening_scope": "👂",
    "heard_nothing_new": "🫧",
    "heard": "👂",
    "spoke": "💬",
    "moved": "👣",
    "stayed": "•",
    "letter_sent": "✉️",
    "letter_waiting": "📬",
    "letter_acknowledged": "📨",
    "mailbox_empty": "🍃",
}


def _record_sentence(record: GymRecord) -> str:
    actor = record.actor or "The scenario"
    detail = record.detail
    if record.kind == "world_arranged":
        place_count = len(detail.get("locations") or [])
        return f"{place_count} connected places were arranged."
    if record.kind == "joined":
        return f"{actor} joined at {record.location}."
    if record.kind == "departed":
        return f"{actor}'s temporary session ended at {record.location}."
    if record.kind == "listening_scope":
        status = str(detail.get("status") or "changed")
        if status == "established":
            return f"{actor} began listening at {record.location}."
        if status == "scope_changed":
            return f"{actor}'s listening point moved to {record.location}."
        return f"{actor}'s speech cursor reported {status}."
    if record.kind == "heard_nothing_new":
        return f"{actor} received no new speech at {record.location}."
    if record.kind == "heard":
        return (
            f"{actor} heard {detail.get('speaker') or 'someone'}: "
            f"“{detail.get('message') or ''}”"
        )
    if record.kind == "spoke":
        return f"{actor}: “{detail.get('message') or ''}”"
    if record.kind == "moved":
        return f"{actor} walked from {detail.get('from')} to {detail.get('to')}."
    if record.kind == "stayed":
        return f"{actor} remained at {record.location}."
    if record.kind == "letter_sent":
        return (
            f"{actor} sent private message {detail.get('message_id')} to durable actor "
            f"{detail.get('recipient_actor_id')}."
        )
    if record.kind == "letter_waiting":
        return (
            f"{actor} was offered message {detail.get('message_id')} from "
            f"{detail.get('sender') or 'an unnamed sender'}: "
            f"“{detail.get('message') or ''}”"
        )
    if record.kind == "letter_acknowledged":
        message_ids = ", ".join(str(item) for item in detail.get("message_ids") or [])
        return f"{actor} acknowledged message {message_ids or 'none'}."
    if record.kind == "mailbox_empty":
        return f"{actor}'s pending mailbox was empty."
    return f"{actor}: {record.kind.replace('_', ' ')}"


def render_terminal(result: GymEpisodeResult) -> str:
    """Render one complete, non-animated terminal view."""

    locations = "  ─────  ".join(f"⌂ {location}" for location in result.locations)
    residents = []
    for participant in result.participants:
        marker = "⚙" if participant.implementation == "mechanical_listener" else "◆"
        location = result.final_locations.get(participant.display_name, "unknown")
        residents.append(f"  {marker} {participant.display_name} → {location}")

    lines = [
        "",
        "        🌿  WORLDWEAVER RESIDENT GYM  🌿",
        f"        {result.episode}",
        "",
        f"  {locations}",
        *residents,
        "",
        "  What the production rules recorded",
    ]
    for record in result.records:
        icon = _ICONS.get(record.kind, "·")
        lines.append(f"  {record.sequence:02d} {icon}  {_record_sentence(record)}")
    lines.extend(
        [
            "",
            "  ◆ scripted participant   ⚙ mechanical baseline",
            "  Every line above comes from a service receipt or signal read.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(result: GymEpisodeResult) -> str:
    """Render a self-contained, high-contrast episode card."""

    participant_cards = []
    for participant in result.participants:
        marker = "⚙" if participant.implementation == "mechanical_listener" else "◆"
        participant_cards.append(
            "<li>"
            f'<span class="marker">{marker}</span> '
            f"<strong>{escape(participant.display_name)}</strong>"
            f"<small>{escape(participant.implementation.replace('_', ' '))}</small>"
            "</li>"
        )

    place_cards = []
    for location in result.locations:
        present = [
            participant
            for participant in result.participants
            if result.final_locations.get(participant.display_name) == location
        ]
        occupants = (
            "".join(
                '<span class="occupant">'
                + ("⚙" if item.implementation == "mechanical_listener" else "◆")
                + f" {escape(item.display_name)}</span>"
                for item in present
            )
            or '<span class="empty">quiet</span>'
        )
        place_cards.append(
            '<article class="place">'
            '<div class="roof">⌂</div>'
            f"<h2>{escape(location)}</h2>"
            f'<div class="occupants">{occupants}</div>'
            "</article>"
        )
    world_map = (
        '<div class="path" aria-label="A path connects the locations"></div>'.join(
            place_cards
        )
    )

    timeline = []
    for record in result.records:
        icon = _ICONS.get(record.kind, "·")
        timeline.append(
            "<li>"
            f'<span class="step">{record.sequence:02d}</span>'
            f'<span class="icon">{icon}</span>'
            f"<span>{escape(_record_sentence(record))}</span>"
            "</li>"
        )

    correspondence_kinds = {
        record.kind for record in result.records if record.kind.startswith("letter_")
    }
    mail_panel = ""
    if correspondence_kinds:
        sent = "letter_sent" in correspondence_kinds
        waiting = "letter_waiting" in correspondence_kinds
        acknowledged = "letter_acknowledged" in correspondence_kinds
        mail_panel = f"""
    <section class="panel post-panel">
      <h2>The post trail</h2>
      <div class="post-route" aria-label="The production correspondence states exercised by this episode">
        <span class="post-state {'complete' if sent else ''}"><b>✉️</b> sent</span>
        <span class="post-path" aria-hidden="true"><span class="courier">✉</span></span>
        <span class="post-state {'complete' if waiting else ''}"><b>📬</b> waiting</span>
        <span class="post-path short" aria-hidden="true"></span>
        <span class="post-state {'complete' if acknowledged else ''}"><b>📨</b> acknowledged</span>
      </div>
      <p class="post-note">These are stored correspondence states. The moving envelope is only a visual key.</p>
    </section>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(result.episode)} · WorldWeaver Resident Gym</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172018;
      --paper: #f4f0df;
      --leaf: #2f6948;
      --moss: #d8e3c7;
      --water: #b9d9dd;
      --rust: #a94e32;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 10%, #fff9 0 8rem, transparent 8.2rem),
        linear-gradient(145deg, var(--paper), #e6edd8);
      font: 18px/1.5 ui-rounded, "Trebuchet MS", system-ui, sans-serif;
    }}
    main {{ width: min(1080px, calc(100% - 2rem)); margin: 0 auto; padding: 3rem 0 5rem; }}
    header {{ text-align: center; margin-bottom: 2rem; }}
    .eyebrow {{ color: var(--leaf); font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ margin: .2rem 0; font: 800 clamp(2.2rem, 7vw, 5rem)/1.05 Georgia, serif; }}
    header p {{ max-width: 48rem; margin: 1rem auto; }}
    .world {{
      display: flex;
      align-items: center;
      margin: 3rem 0;
    }}
    .path {{ flex: 0 0 5rem; height: .55rem; background: var(--water); border: 2px solid var(--ink); position: relative; }}
    .path::after {{ content: "↔"; position: absolute; left: 50%; top: 50%; transform: translate(-50%, -55%); background: var(--paper); padding: .15rem .35rem; border: 2px solid var(--ink); border-radius: 50%; }}
    .place {{ flex: 1 1 0; min-width: 0; min-height: 13rem; padding: 1.4rem; background: #fffdf4; border: 3px solid var(--ink); border-radius: 1.2rem; box-shadow: .55rem .55rem 0 var(--moss); }}
    .place h2 {{ margin: .25rem 0 1.2rem; font: 800 clamp(1.5rem, 4vw, 2.4rem)/1.1 Georgia, serif; }}
    .roof {{ color: var(--rust); font-size: 2rem; }}
    .occupants {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
    .occupant {{ padding: .4rem .7rem; background: var(--moss); border: 2px solid var(--ink); border-radius: 999px; font-weight: 700; }}
    .empty {{ color: #526056; font-style: italic; }}
    .panel {{ margin-top: 2.5rem; padding: clamp(1rem, 3vw, 2rem); background: #fffdf4dd; border: 3px solid var(--ink); border-radius: 1.2rem; }}
    .panel h2 {{ margin-top: 0; font: 800 2rem/1.1 Georgia, serif; }}
    .participants, .timeline {{ list-style: none; padding: 0; margin: 0; }}
    .participants {{ display: flex; flex-wrap: wrap; gap: .7rem; }}
    .participants li {{ display: flex; align-items: center; gap: .45rem; padding: .5rem .8rem; background: var(--moss); border-radius: .7rem; }}
    .participants small {{ color: #45534a; margin-left: .3rem; }}
    .timeline li {{ display: grid; grid-template-columns: 2.4rem 2.2rem 1fr; gap: .5rem; padding: .8rem 0; border-top: 1px solid #879486; }}
    .step {{ font: 700 .85rem/2rem ui-monospace, monospace; color: var(--leaf); }}
    .icon {{ font-size: 1.35rem; }}
    .post-route {{ display: grid; grid-template-columns: auto minmax(3rem, 1fr) auto minmax(2rem, .5fr) auto; align-items: center; gap: .7rem; }}
    .post-state {{ display: grid; justify-items: center; gap: .25rem; min-width: 7rem; padding: .7rem; color: #59635b; border: 2px dashed #879486; border-radius: 1rem; font-weight: 800; }}
    .post-state b {{ font-size: 2rem; }}
    .post-state.complete {{ color: var(--ink); background: var(--moss); border: 2px solid var(--ink); }}
    .post-path {{ position: relative; height: .35rem; border-top: 3px dotted var(--leaf); }}
    .courier {{ position: absolute; left: 0; top: -.95rem; animation: carry 3.2s ease-in-out infinite; }}
    .post-note {{ margin-bottom: 0; color: #45534a; font-size: .9rem; }}
    @keyframes carry {{ 0%, 15% {{ left: 0; }} 75%, 100% {{ left: calc(100% - 1.2rem); }} }}
    @media (prefers-reduced-motion: reduce) {{ .courier {{ animation: none; left: 50%; }} }}
    footer {{ margin-top: 2rem; color: #45534a; font-size: .95rem; }}
    @media (max-width: 650px) {{
      .world {{ flex-direction: column; gap: 1rem; }}
      .place {{ width: 100%; }}
      .path {{ flex-basis: 3.5rem; width: .55rem; height: 3.5rem; }}
      .path::after {{ content: "↕"; }}
      .participants li {{ width: 100%; }}
      .post-route {{ grid-template-columns: 1fr; }}
      .post-path {{ width: .35rem; height: 2rem; border-top: 0; border-left: 3px dotted var(--leaf); justify-self: center; }}
      .courier {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">🌿 WorldWeaver Resident Gym</div>
      <h1>{escape(result.episode)}</h1>
      <p>A deterministic rehearsal using the same movement, speech, session, and live-signal rules as a running shard.</p>
    </header>
    <section class="world" aria-label="Final participant locations">
      {world_map}
    </section>
    <section class="panel">
      <h2>Participants</h2>
      <ul class="participants">{''.join(participant_cards)}</ul>
    </section>
    {mail_panel}
    <section class="panel">
      <h2>What happened</h2>
      <ol class="timeline">{''.join(timeline)}</ol>
    </section>
    <footer>Every line comes from a production service receipt or exact-place signal read. The display adds layout and icons, not narration.</footer>
  </main>
</body>
</html>
"""

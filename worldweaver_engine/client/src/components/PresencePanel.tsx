// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

type PresenceEntry = {
  session_id: string;
  location: string;
  display_name?: string | null;
  player_name?: string | null;
};

type PresencePanelProps = {
  roster: PresenceEntry[];
  sessionId: string;
};

export function PresencePanel({ roster, sessionId }: PresencePanelProps) {
  if (roster.length === 0) {
    return (
      <div className="ww-presence-tab">
        <p className="ww-digest-empty">No one is publicly present right now.</p>
      </div>
    );
  }

  return (
    <div className="ww-presence-tab">
      <p className="ww-digest-empty">Public presence only: who is here and where they are.</p>
      <ul className="ww-presence-list">
        {roster.map((entry) => {
          const name = entry.display_name || entry.player_name || entry.session_id.slice(0, 12);
          return (
            <li key={entry.session_id} className="ww-presence-entry">
              <div className="ww-presence-line">
                <span className="ww-roster-name">
                  {name}
                  {entry.session_id === sessionId && <span className="ww-roster-you"> (you)</span>}
                </span>
              </div>
              <div className="ww-presence-meta">{entry.location.replace(/_/g, " ")}</div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

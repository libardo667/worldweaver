// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { MapNode } from "../api/types";

/**
 * Who is actually at this place, by name — an encounter, not a roster.
 * Residents and visitors are listed the same way; everyone here is a person.
 */
export function PresenceHere({ node }: { node: MapNode | undefined }) {
  const names = node?.present_names ?? [];
  return (
    <section className="place-section">
      <h3 className="place-section-title">Here now</h3>
      {names.length === 0 ? (
        <p className="place-empty">No one at the moment — the town keeps on anyway.</p>
      ) : (
        <div className="presence-chips">
          {names.map((name) => (
            <span key={name} className="presence-chip">{name}</span>
          ))}
        </div>
      )}
    </section>
  );
}

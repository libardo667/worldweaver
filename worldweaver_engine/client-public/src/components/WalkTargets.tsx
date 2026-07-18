// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useMemo } from "react";
import type { MapEdge, MapNode } from "../api/types";
import { isVisitablePlace } from "../lib/places";

type Props = {
  node: MapNode | undefined;
  nodes: MapNode[];
  edges: MapEdge[];
  onWalk: (node: MapNode) => void;
};

/** The places you can walk to from here — the graph's honest adjacency. */
export function WalkTargets({ node, nodes, edges, onWalk }: Props) {
  const neighbors = useMemo(() => {
    if (!node) return [];
    const byKey = new Map(nodes.map((n) => [n.key, n]));
    const neighborKeys = new Set<string>();
    for (const edge of edges) {
      if (edge.from === edge.to) continue;
      if (edge.from === node.key) neighborKeys.add(edge.to);
      if (edge.to === node.key) neighborKeys.add(edge.from);
    }
    neighborKeys.delete(node.key);
    // Streets lead to main places; the landmarks AT those places live in
    // the Nearby list instead.
    return [...neighborKeys]
      .map((key) => byKey.get(key))
      .filter((n): n is MapNode => n != null && n.node_type === "location" && isVisitablePlace(n))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [node, nodes, edges]);

  if (neighbors.length === 0) return null;

  return (
    <section className="place-section">
      <h3 className="place-section-title">From here you can walk to</h3>
      <div className="walk-targets">
        {neighbors.map((neighbor) => (
          <button key={neighbor.key} className="walk-target" onClick={() => onWalk(neighbor)}>
            {neighbor.name}
            {(neighbor.present_count ?? 0) > 0 && <span className="walk-target-live" title="Someone is there" />}
          </button>
        ))}
      </div>
    </section>
  );
}

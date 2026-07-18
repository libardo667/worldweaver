// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { MapEdge, MapNode } from "../api/types";
import { usePlace } from "../hooks/usePlace";
import { findNodeBySlug, slugifyPlace } from "../lib/places";
import { NearbyLandmarks } from "./NearbyLandmarks";
import { Overheard } from "./Overheard";
import { PresenceHere } from "./PresenceHere";
import { StoopHere } from "./StoopHere";
import { WalkTargets } from "./WalkTargets";

type Props = {
  slug: string;
  node: MapNode | undefined;
  nodes: MapNode[];
  edges: MapEdge[];
  onWalk: (node: MapNode) => void;
  onClose: () => void;
};

function prettifySlug(slug: string): string {
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** The place you are looking at, side-loaded over the map. */
export function PlacePanel({ slug, node, nodes, edges, onWalk, onClose }: Props) {
  const name = node?.name ?? prettifySlug(slug);
  const details = usePlace(node?.name ?? null);

  return (
    <aside className="place-panel" aria-label={`At ${name}`}>
      <header className="place-header">
        <div>
          <p className="place-kicker">You are looking at</p>
          <h2 className="place-name">{name}</h2>
        </div>
        <button className="place-close" onClick={onClose} title="Back to the map" aria-label="Close place panel">
          ✕
        </button>
      </header>

      <div className="place-body">
        {node?.description && <p className="place-description">{node.description}</p>}

        <PresenceHere node={node} />
        {node && <Overheard location={node.name} />}
        {node && <StoopHere location={node.name} stoops={details.stoops} />}
        <WalkTargets node={node} nodes={nodes} edges={edges} onWalk={onWalk} />
        <NearbyLandmarks
          landmarks={details.landmarks}
          onVisit={(landmarkName) => {
            const target = findNodeBySlug(nodes, slugifyPlace(landmarkName));
            if (target) onWalk(target);
          }}
        />

        {details.context?.available && details.context.context && (
          <details className="place-context">
            <summary>The lay of the land</summary>
            <p>{details.context.context}</p>
          </details>
        )}

        {!node && <p className="place-empty">Finding this place on the map…</p>}
      </div>
    </aside>
  );
}

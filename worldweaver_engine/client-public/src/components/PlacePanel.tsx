// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import type { MapEdge, MapNode } from "../api/types";
import { usePlace } from "../hooks/usePlace";
import { findNodeBySlug, slugifyPlace } from "../lib/places";
import { NearbyLandmarks } from "./NearbyLandmarks";
import { Overheard } from "./Overheard";
import { PresenceHere } from "./PresenceHere";
import { SpeakBar } from "./SpeakBar";
import { StoopHere } from "./StoopHere";
import { WalkTargets } from "./WalkTargets";

type Me = { sessionId: string; displayName: string; place: string };

type Props = {
  slug: string;
  node: MapNode | undefined;
  nodes: MapNode[];
  edges: MapEdge[];
  /** The participant, when someone has joined; null while spectating. */
  me: Me | null;
  /** Look at a place without moving anyone. */
  onWalk: (node: MapNode) => void;
  /** Physically walk the participant there, hop by hop. */
  onTravel: (node: MapNode) => void;
  onClose: () => void;
};

function prettifySlug(slug: string): string {
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** The place you are looking at, side-loaded over the map. */
export function PlacePanel({ slug, node, nodes, edges, me, onWalk, onTravel, onClose }: Props) {
  const name = node?.name ?? prettifySlug(slug);
  const details = usePlace(node?.name ?? null);
  const [spokeCount, setSpokeCount] = useState(0);

  const standingHere = me != null && node != null && me.place === node.name;

  return (
    <aside className="place-panel" aria-label={`At ${name}`}>
      <header className="place-header">
        <div>
          <p className="place-kicker">{standingHere ? "You are standing at" : "You are looking at"}</p>
          <h2 className="place-name">{name}</h2>
        </div>
        <button className="place-close" onClick={onClose} title="Back to the map" aria-label="Close place panel">
          ✕
        </button>
      </header>

      <div className="place-body">
        {node?.description && <p className="place-description">{node.description}</p>}

        {me && node && !standingHere && (
          <button className="btn btn-primary place-walk-here" onClick={() => onTravel(node)}>
            Walk here from {me.place}
          </button>
        )}

        <PresenceHere node={node} />
        {node && <Overheard location={node.name} refreshKey={spokeCount} />}
        {node && (
          <StoopHere location={node.name} stoops={details.stoops} takerSessionId={standingHere ? me.sessionId : null} />
        )}
        <WalkTargets node={node} nodes={nodes} edges={edges} onWalk={standingHere ? onTravel : onWalk} />
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

      {standingHere && (
        <SpeakBar
          location={node.name}
          sessionId={me.sessionId}
          displayName={me.displayName}
          onSpoke={() => setSpokeCount((count) => count + 1)}
        />
      )}
    </aside>
  );
}

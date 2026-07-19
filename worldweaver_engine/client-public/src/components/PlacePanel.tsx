// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef, useState } from "react";
import type { MapEdge, MapNode } from "../api/types";
import type { PendingDeparture } from "../session/store";
import { usePlace } from "../hooks/usePlace";
import { findNodeBySlug, slugifyPlace } from "../lib/places";
import { MakeHere } from "./MakeHere";
import { MarksHere } from "./MarksHere";
import { AccessHere } from "./AccessHere";
import { NearbyLandmarks } from "./NearbyLandmarks";
import { ObjectsHere } from "./ObjectsHere";
import { Overheard } from "./Overheard";
import { PresenceHere } from "./PresenceHere";
import { SpeakBar } from "./SpeakBar";
import { StoopHere } from "./StoopHere";
import { ThemeToggle } from "./ThemeToggle";
import { TravelHere } from "./TravelHere";
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
  onCrossCityTravel: (destinationClientUrl: string, travelId: string) => void;
  onCrossCityTravelPending: (pending: PendingDeparture) => void;
  onClose: () => void;
};

function prettifySlug(slug: string): string {
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** The place you are looking at, side-loaded over the map. */
export function PlacePanel({ slug, node, nodes, edges, me, onWalk, onTravel, onCrossCityTravel, onCrossCityTravelPending, onClose }: Props) {
  const name = node?.name ?? prettifySlug(slug);
  // Bumped whenever a verb changes the world here (made/took/left/moved a
  // thing) so stoop counts and object lists refetch together.
  const [worldBump, setWorldBump] = useState(0);
  const details = usePlace(node?.name ?? null, worldBump);
  const [spokeCount, setSpokeCount] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [slug]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const standingHere = me != null && node != null && me.place === node.name;
  const bumpWorld = () => setWorldBump((count) => count + 1);

  return (
    <aside className="place-panel" aria-label={`At ${name}`}>
      <header className="place-header">
        <div>
          <p className="place-kicker">{standingHere ? "You are standing at" : "You are looking at"}</p>
          <h2 ref={headingRef} tabIndex={-1} className="place-name">{name}</h2>
        </div>
        <div className="place-header-actions">
          <ThemeToggle inline />
          <button className="place-close" onClick={onClose} title="Back to the map" aria-label="Close place panel">
            ✕
          </button>
        </div>
      </header>

      <div className="place-body">
        {node?.description && <p className="place-description">{node.description}</p>}

        {me && node && !standingHere && (
          <button className="btn btn-primary place-walk-here" onClick={() => onTravel(node)}>
            Walk here from {me.place}
          </button>
        )}

        {me && node && <AccessHere location={node.name} sessionId={me.sessionId} />}

        <PresenceHere node={node} />
        {node && <Overheard location={node.name} refreshKey={spokeCount} />}
        {node && (
          <StoopHere
            location={node.name}
            stoops={details.stoops}
            takerSessionId={standingHere ? me.sessionId : null}
            refreshKey={worldBump}
            onTook={bumpWorld}
          />
        )}
        {standingHere && (
          <>
            <TravelHere
              location={node.name}
              sessionId={me.sessionId}
              onDeparted={onCrossCityTravel}
              onDeparturePending={onCrossCityTravelPending}
            />
            <MarksHere location={node.name} sessionId={me.sessionId} />
            <ObjectsHere location={node.name} sessionId={me.sessionId} stoops={details.stoops} refreshKey={worldBump} onChanged={bumpWorld} />
            <MakeHere location={node.name} sessionId={me.sessionId} onMade={bumpWorld} />
          </>
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

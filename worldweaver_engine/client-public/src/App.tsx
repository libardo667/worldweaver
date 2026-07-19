// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Route, useLocation, useRoute, useSearch } from "wouter";
import { getEntry, getShardExperience, postLeaveSession, postMove, queryMap } from "./api/ww";
import type { EntryInfo, MapEdge, MapNode, ShardExperience } from "./api/types";
import { JoinFlow } from "./components/JoinFlow";
import { PlacePanel } from "./components/PlacePanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { ThresholdOverlay } from "./components/ThresholdOverlay";
import { WorldMap, type MapBounds } from "./components/WorldMap";
import { useGrounding } from "./hooks/useGrounding";
import { usePoll } from "./hooks/usePoll";
import { findNodeBySlug, isVisitablePlace, slugifyPlace } from "./lib/places";
import { clearParticipant, getJwt, getPlayer, getSessionId, getStandingPlace, setStandingPlace } from "./session/store";

/** A participant: someone standing in the world, not just looking at it. */
type Me = { sessionId: string; displayName: string; place: string };

function rememberedMe(): Me | null {
  const player = getPlayer();
  const sessionId = getSessionId();
  const place = getStandingPlace();
  if (getJwt() && player && sessionId && place) {
    return { sessionId, displayName: player.display_name, place };
  }
  return null;
}

/** Where "look around" drops you: the liveliest entry place, else any entry place. */
function pickLookAroundTarget(entry: EntryInfo | null, nodes: MapNode[]): string | null {
  const entryNames = new Set((entry?.entry_nodes ?? []).map((n) => n.name));
  if (entryNames.size === 0) return null;
  const candidates = nodes.filter((n) => entryNames.has(n.name) && isVisitablePlace(n));
  candidates.sort((a, b) => (b.present_count ?? 0) - (a.present_count ?? 0));
  const liveliest = candidates[0];
  if (liveliest) return slugifyPlace(liveliest.name);
  const fallback = entry?.entry_nodes?.[Math.floor(Math.random() * (entry?.entry_nodes.length ?? 1))];
  return fallback ? slugifyPlace(fallback.name) : null;
}

function entryFrame(entry: EntryInfo | null): MapBounds | null {
  const coords = (entry?.entry_nodes ?? []).filter((n) => n.lat != null && n.lon != null);
  if (coords.length === 0) return null;
  const lats = coords.map((n) => n.lat as number);
  const lons = coords.map((n) => n.lon as number);
  return {
    north: Math.max(...lats),
    south: Math.min(...lats),
    east: Math.max(...lons),
    west: Math.min(...lons),
  };
}

export function App() {
  const [experience, setExperience] = useState<ShardExperience | null>(null);
  const [entry, setEntry] = useState<EntryInfo | null>(null);
  const [nodes, setNodes] = useState<MapNode[]>([]);
  const [edges, setEdges] = useState<MapEdge[]>([]);
  // The threshold greets every fresh page load, whatever the URL — deep links
  // included. It closes on an explicit choice (or walking off) and stays
  // closed for client-side navigation within this load.
  const [thresholdOpen, setThresholdOpen] = useState(true);
  const [me, setMe] = useState<Me | null>(rememberedMe);
  const viewportRef = useRef<MapBounds | null>(null);
  const atmosphere = useGrounding();
  const [, navigate] = useLocation();
  const [, placeParams] = useRoute("/place/:slug");
  const search = useSearch();

  // Password-reset emails point at the public root. Carry their one-time token
  // into the join card instead of making the person dismiss the town threshold.
  useEffect(() => {
    const resetToken = new URLSearchParams(search).get("reset_token");
    if (!resetToken || placeParams) return;
    setThresholdOpen(false);
    navigate(`/join?reset_token=${encodeURIComponent(resetToken)}`, { replace: true });
  }, [navigate, placeParams, search]);

  useEffect(() => {
    getShardExperience().then(setExperience).catch(() => setExperience(null));
    getEntry().then(setEntry).catch(() => setEntry(null));
  }, []);

  const refreshMap = useCallback(async () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    try {
      const result = await queryMap(viewport);
      setNodes(result.nodes);
      setEdges(result.edges);
    } catch {
      // Keep the last honest view on a failed refresh.
    }
  }, []);

  const handleViewportChange = useCallback(
    (bounds: MapBounds) => {
      viewportRef.current = bounds;
      void refreshMap();
    },
    [refreshMap],
  );

  // Watching a place deserves a livelier pulse than ambient map-gazing:
  // presence chips and glow both come from this query.
  usePoll(refreshMap, placeParams ? 5_000 : 15_000);

  const focusNode = useMemo(
    () => (placeParams?.slug ? findNodeBySlug(nodes, placeParams.slug) : undefined),
    [nodes, placeParams?.slug],
  );

  const handleNodeClick = useCallback(
    (node: MapNode) => {
      if (!isVisitablePlace(node)) return;
      setThresholdOpen(false);
      navigate(`/place/${slugifyPlace(node.name)}`);
    },
    [navigate],
  );

  const handleLookAround = useCallback(() => {
    setThresholdOpen(false);
    // A deep-linked place already is the look-around; otherwise pick one.
    if (placeParams?.slug) return;
    const slug = pickLookAroundTarget(entry, nodes);
    if (slug) navigate(`/place/${slug}`);
  }, [entry, nodes, navigate, placeParams?.slug]);

  // Actually walk there: one real move per hop, so residents see you pass
  // through, then look at where you've arrived (or wherever you got stuck).
  const walkTo = useCallback(
    async (target: MapNode) => {
      if (!me) return;
      let current = me.place;
      for (let hop = 0; hop < 8 && current !== target.name; hop++) {
        try {
          const result = await postMove(me.sessionId, target.name);
          if (!result.moved) break;
          current = result.to_location;
          setStandingPlace(current);
          setMe((prev) => (prev ? { ...prev, place: result.to_location } : prev));
        } catch {
          break;
        }
      }
      void refreshMap();
      navigate(`/place/${slugifyPlace(current === target.name ? target.name : current)}`);
    },
    [me, navigate, refreshMap],
  );

  const leaveWorld = useCallback(async () => {
    if (!me) return;
    try {
      await postLeaveSession(me.sessionId);
    } catch {
      // Best effort; the identity is cleared locally regardless.
    }
    clearParticipant();
    setMe(null);
    void refreshMap();
  }, [me, refreshMap]);

  const suggestedJoinPlace = useMemo(() => {
    const slug = new URLSearchParams(search).get("place");
    return slug ? (findNodeBySlug(nodes, slug)?.name ?? null) : null;
  }, [search, nodes]);

  return (
    <div className="app-shell" data-phase={atmosphere.phase} data-haze={atmosphere.hazy ? "true" : "false"}>
      <WorldMap
        nodes={nodes}
        edges={edges}
        mapStyle={entry?.map_style ?? null}
        focusKey={focusNode?.key ?? null}
        onNodeClick={handleNodeClick}
        onViewportChange={handleViewportChange}
        frame={entryFrame(entry)}
      />
      <div className="sky-tint" aria-hidden="true" />

      <Route path="/place/:slug">
        {(params) => (
          <PlacePanel
            slug={params.slug}
            node={findNodeBySlug(nodes, params.slug)}
            nodes={nodes}
            edges={edges}
            me={me}
            onWalk={handleNodeClick}
            onTravel={walkTo}
            onClose={() => navigate("/")}
          />
        )}
      </Route>
      <Route path="/join">
        {me ? (
          <div className="threshold">
            <div className="threshold-card">
              <h1 className="threshold-title">You're already here</h1>
              <p className="threshold-summary">
                Standing at {me.place} as {me.displayName}.
              </p>
              <div className="threshold-actions">
                <button className="btn btn-primary" onClick={() => navigate(`/place/${slugifyPlace(me.place)}`)}>
                  Back to {me.place}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <JoinFlow
            entry={entry}
            suggestedPlace={suggestedJoinPlace}
            onJoined={(place) => {
              setMe(rememberedMe());
              void refreshMap();
              navigate(`/place/${slugifyPlace(place)}`);
            }}
            onClose={() => navigate("/")}
          />
        )}
      </Route>

      {me && (
        <div className="me-chip">
          <button className="me-chip-name" onClick={() => navigate(`/place/${slugifyPlace(me.place)}`)} title="Back to where you are standing">
            {me.displayName} · at {me.place}
          </button>
          <button className="me-chip-leave" onClick={() => void leaveWorld()} title="Leave the world">
            leave
          </button>
        </div>
      )}

      {thresholdOpen && (
        <ThresholdOverlay
          experience={experience}
          entry={entry}
          grounding={atmosphere.grounding}
          nodes={nodes}
          onLookAround={handleLookAround}
          onJoin={() => {
            setThresholdOpen(false);
            navigate("/join");
          }}
        />
      )}

      <ThemeToggle />
    </div>
  );
}

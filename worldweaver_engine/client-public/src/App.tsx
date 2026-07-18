// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Route, useLocation, useRoute } from "wouter";
import { getEntry, getShardExperience, queryMap } from "./api/ww";
import type { EntryInfo, MapEdge, MapNode, ShardExperience } from "./api/types";
import { PlacePanel } from "./components/PlacePanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { ThresholdOverlay } from "./components/ThresholdOverlay";
import { WorldMap, type MapBounds } from "./components/WorldMap";
import { useGrounding } from "./hooks/useGrounding";
import { usePoll } from "./hooks/usePoll";
import { findNodeBySlug, isVisitablePlace, slugifyPlace } from "./lib/places";

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
  const viewportRef = useRef<MapBounds | null>(null);
  const atmosphere = useGrounding();
  const [, navigate] = useLocation();
  const [, placeParams] = useRoute("/place/:slug");

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

  usePoll(refreshMap, 30_000);

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

  return (
    <div className="app-shell" data-phase={atmosphere.phase} data-haze={atmosphere.hazy ? "true" : "false"}>
      <WorldMap
        nodes={nodes}
        edges={edges}
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
            onWalk={handleNodeClick}
            onClose={() => navigate("/")}
          />
        )}
      </Route>
      <Route path="/join">
        <div className="dev-caption">join flow lands in the next slice</div>
      </Route>

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

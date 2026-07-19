// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef } from "react";
import type * as Leaflet from "leaflet";
import type { GeneratedMapArtifact, MapEdge, MapNode } from "../api/types";
import "leaflet/dist/leaflet.css";

export type MapBounds = { north: number; south: number; east: number; west: number };

type Props = {
  nodes: MapNode[];
  edges: MapEdge[];
  /** Fictional packs are drawn as their own schematic, never over a real town. */
  mapStyle: "schematic" | "geographic" | null;
  /** Key of the place the viewer is currently at/looking at; drawn as "here". */
  focusKey?: string | null;
  onNodeClick?: (node: MapNode) => void;
  onViewportChange?: (bounds: MapBounds) => void;
  /** One-shot framing applied when it first becomes available. */
  frame?: MapBounds | null;
  generatedMap?: GeneratedMapArtifact | null;
  generatedMapUrl?: string | null;
};

function occupancyClass(node: MapNode): string {
  const present = node.present_count ?? 0;
  // Landmarks and corridors are furniture and paths, not main places —
  // unless someone is actually there, which always glows.
  if (present >= 3) return "mk-busy";
  if (present >= 1) return "mk-warm";
  if (node.node_type !== "location") return "mk-landmark";
  return "mk-empty";
}

function markerRadius(node: MapNode, isFocus: boolean): number {
  if (isFocus) return 11;
  const present = node.present_count ?? 0;
  if (present >= 3) return 10;
  if (present >= 1) return 9;
  return node.node_type !== "location" ? 4 : 7;
}

function stableOffsetAngle(key: string): number {
  // The angle belongs to the node identity, not its current API-array index.
  // Presence changes may reorder nodes, but must never rearrange the town.
  let hash = 2166136261;
  for (let index = 0; index < key.length; index += 1) {
    hash ^= key.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 0xffffffff) * Math.PI * 2;
}

export function WorldMap({ nodes, edges, mapStyle, focusKey, onNodeClick, onViewportChange, frame, generatedMap, generatedMapUrl }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Leaflet.Map | null>(null);
  const markersRef = useRef<Leaflet.LayerGroup | null>(null);
  const tileLayerRef = useRef<Leaflet.TileLayer | null>(null);
  const generatedLayerRef = useRef<Leaflet.ImageOverlay | null>(null);
  const generatedLayerUrlRef = useRef("");
  const generatedBoundsRef = useRef<MapBounds | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const onViewportChangeRef = useRef(onViewportChange);
  const onNodeClickRef = useRef(onNodeClick);
  const lastViewportSignatureRef = useRef("");
  const framedRef = useRef(false);
  const lastFocusRef = useRef<string | null>(null);

  onViewportChangeRef.current = onViewportChange;
  onNodeClickRef.current = onNodeClick;
  generatedBoundsRef.current = mapStyle === "schematic" ? generatedMap?.bounds ?? null : null;

  useEffect(() => {
    if (!containerRef.current) return;
    let active = true;

    import("leaflet").then((mod) => {
      if (!active || !containerRef.current) return;
      const L = mod.default;
      const keepGeneratedSheetFilled = (map: Leaflet.Map, bounds: MapBounds) => {
        const sheetBounds = L.latLngBounds(
          [bounds.south, bounds.west],
          [bounds.north, bounds.east],
        );
        // `inside: true` chooses the first zoom where the viewport fits inside
        // the generated sheet. The town may crop at the edges on a wide or tall
        // screen, but empty space can never surround it.
        const coverZoom = map.getBoundsZoom(sheetBounds, true);
        map.setMinZoom(coverZoom);
        map.setMaxBounds(sheetBounds);
        if (map.getZoom() < coverZoom) map.setZoom(coverZoom, { animate: false });
        map.panInsideBounds(sheetBounds, { animate: false });
      };

      if (!mapRef.current) {
        const map = L.map(containerRef.current, {
          center: [45.014, -122.0],
          zoom: 14,
          zoomSnap: 0.1,
          zoomDelta: 0.5,
          zoomControl: false,
          maxBoundsViscosity: 1,
        });
        L.control.zoom({ position: "bottomright" }).addTo(map);
        markersRef.current = L.layerGroup().addTo(map);
        mapRef.current = map;

        const emitViewport = () => {
          const b = map.getBounds();
          const viewport = { north: b.getNorth(), south: b.getSouth(), east: b.getEast(), west: b.getWest() };
          const signature = [viewport.north, viewport.south, viewport.east, viewport.west].map((v) => v.toFixed(5)).join("|");
          if (signature === lastViewportSignatureRef.current) return;
          lastViewportSignatureRef.current = signature;
          onViewportChangeRef.current?.(viewport);
        };
        map.on("moveend", emitViewport);
        map.on("zoomend", emitViewport);
        if (typeof ResizeObserver !== "undefined") {
          const observer = new ResizeObserver(() => {
            map.invalidateSize();
            const currentBounds = generatedBoundsRef.current;
            if (currentBounds) keepGeneratedSheetFilled(map, currentBounds);
          });
          observer.observe(containerRef.current);
          resizeObserverRef.current = observer;
        }
        requestAnimationFrame(() => {
          map.invalidateSize();
          emitViewport();
        });
      }

      const map = mapRef.current;
      const markers = markersRef.current;
      if (!map || !markers) return;

      if (mapStyle === "geographic" && !tileLayerRef.current) {
        tileLayerRef.current = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
          maxZoom: 19,
        }).addTo(map);
      } else if (mapStyle === "schematic" && tileLayerRef.current) {
        map.removeLayer(tileLayerRef.current);
        tileLayerRef.current = null;
      }

      const generatedBounds = generatedMap?.bounds;
      if (mapStyle === "schematic" && generatedBounds && generatedMapUrl) {
        if (generatedLayerRef.current && generatedLayerUrlRef.current !== generatedMapUrl) {
          map.removeLayer(generatedLayerRef.current);
          generatedLayerRef.current = null;
        }
        if (!generatedLayerRef.current) {
          generatedLayerRef.current = L.imageOverlay(
            generatedMapUrl,
            L.latLngBounds(
              [generatedBounds.south, generatedBounds.west],
              [generatedBounds.north, generatedBounds.east],
            ),
            { opacity: 0.94, interactive: false, className: "generated-map-layer" },
          ).addTo(map);
          generatedLayerRef.current.bringToBack();
          generatedLayerUrlRef.current = generatedMapUrl;
        }
        keepGeneratedSheetFilled(map, generatedBounds);
      } else if (generatedLayerRef.current) {
        map.removeLayer(generatedLayerRef.current);
        generatedLayerRef.current = null;
        generatedLayerUrlRef.current = "";
      }

      // One-shot framing (entry bounds) the first time it arrives.
      if (frame && !framedRef.current) {
        framedRef.current = true;
        map.fitBounds(
          L.latLngBounds([frame.south, frame.west], [frame.north, frame.east]).pad(0.25),
          { maxZoom: 15 },
        );
      }

      const georef = nodes.filter((n) => n.lat != null && n.lon != null);
      const byKey = new Map(georef.map((n) => [n.key, n]));

      // Fan out markers sharing one authored coordinate. The displayed point
      // is derived from stable node identity, so presence-driven API ordering
      // cannot make two places trade positions.
      const buckets = new Map<string, MapNode[]>();
      for (const node of georef) {
        const key = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        buckets.set(key, [...(buckets.get(key) ?? []), node]);
      }
      const displayPointByKey = new Map<string, [number, number]>();
      for (const node of georef) {
        const bucketKey = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        const bucket = buckets.get(bucketKey) ?? [node];
        const angle = bucket.length > 1 ? stableOffsetAngle(node.key) : 0;
        const offset = bucket.length > 1 ? 0.0012 : 0;
        displayPointByKey.set(node.key, [
          (node.lat as number) + Math.cos(angle) * offset,
          (node.lon as number) + Math.sin(angle) * offset,
        ]);
      }

      markers.clearLayers();
      const compiledRoutesVisible = mapStyle === "schematic" && generatedLayerRef.current != null;
      const drawnPathPairs = new Set<string>();
      for (const edge of edges) {
        // Containment says that a landmark belongs to a larger place. It is
        // useful to the place UI, but it is not a visible walking route.
        if (edge.kind !== "path") continue;
        // The compiled sheet draws the same canonical edges with their authored
        // path shape and surface. The plain fallback line would cut across it.
        if (compiledRoutesVisible) continue;
        const pairKey = [edge.from, edge.to].sort().join("\u0000");
        if (drawnPathPairs.has(pairKey)) continue;
        drawnPathPairs.add(pairKey);
        const from = byKey.get(edge.from);
        const to = byKey.get(edge.to);
        const fromPoint = from ? displayPointByKey.get(from.key) : undefined;
        const toPoint = to ? displayPointByKey.get(to.key) : undefined;
        if (!fromPoint || !toPoint) continue;
        L.polyline(
          [fromPoint, toPoint],
          { className: "map-path", interactive: false },
        ).addTo(markers);
      }
      for (const node of georef) {
        const isFocus = focusKey != null && node.key === focusKey;
        const displayPoint = displayPointByKey.get(node.key);
        if (!displayPoint) continue;

        const marker = L.circleMarker(
          displayPoint,
          {
            radius: markerRadius(node, isFocus),
            className: `mk ${occupancyClass(node)}${isFocus ? " mk-here" : ""}`,
          },
        );
        const primaryPlace = node.node_type === "location";
        marker.bindTooltip(node.name, {
          direction: "top",
          permanent: primaryPlace,
          className: primaryPlace ? "map-label map-label--place" : "map-label",
          offset: L.point(0, -markerRadius(node, isFocus) - 2),
        });
        marker.on("click", () => onNodeClickRef.current?.(node));
        marker.addTo(markers);
        const element = marker.getElement();
        if (element && onNodeClickRef.current && isVisitableMapNode(node)) {
          element.setAttribute("tabindex", "0");
          element.setAttribute("role", "button");
          element.setAttribute("aria-label", `Look at ${node.name}`);
          element.addEventListener("keydown", (event) => {
            const key = (event as KeyboardEvent).key;
            if (key !== "Enter" && key !== " ") return;
            event.preventDefault();
            onNodeClickRef.current?.(node);
          });
        }
      }

      // Ease over to a newly focused place.
      if (focusKey && focusKey !== lastFocusRef.current) {
        lastFocusRef.current = focusKey;
        const node = byKey.get(focusKey);
        const target = node ? displayPointByKey.get(node.key) : undefined;
        if (target) {
          // A fictional town already has an exact, sheet-filling minimum zoom.
          // Focusing a place should pan there, not immediately punch back in.
          const targetZoom = generatedBoundsRef.current
            ? Math.max(map.getZoom(), map.getMinZoom())
            : Math.max(map.getZoom(), 15);
          if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            map.setView(target, targetZoom, { animate: false });
          } else {
            map.flyTo(target, targetZoom, { duration: 0.9 });
          }
        }
      }
      if (!focusKey) lastFocusRef.current = null;
    });

    return () => {
      active = false;
    };
  }, [nodes, edges, mapStyle, focusKey, frame, generatedMap, generatedMapUrl]);

  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      tileLayerRef.current = null;
      generatedLayerRef.current = null;
      generatedLayerUrlRef.current = "";
    };
  }, []);

  return <div ref={containerRef} className={`world-map world-map--${mapStyle ?? "loading"}`} role="region" aria-label="Town map" />;
}

function isVisitableMapNode(node: MapNode): boolean {
  return node.node_type === "location" || node.node_type === "landmark" || node.node_type === "sublocation";
}

// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef } from "react";
import type * as Leaflet from "leaflet";
import type { MapEdge, MapNode } from "../api/types";
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

export function WorldMap({ nodes, edges, mapStyle, focusKey, onNodeClick, onViewportChange, frame }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Leaflet.Map | null>(null);
  const markersRef = useRef<Leaflet.LayerGroup | null>(null);
  const tileLayerRef = useRef<Leaflet.TileLayer | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const onViewportChangeRef = useRef(onViewportChange);
  const onNodeClickRef = useRef(onNodeClick);
  const lastViewportSignatureRef = useRef("");
  const framedRef = useRef(false);
  const lastFocusRef = useRef<string | null>(null);

  onViewportChangeRef.current = onViewportChange;
  onNodeClickRef.current = onNodeClick;

  useEffect(() => {
    if (!containerRef.current) return;
    let active = true;

    import("leaflet").then((mod) => {
      if (!active || !containerRef.current) return;
      const L = mod.default;

      if (!mapRef.current) {
        const map = L.map(containerRef.current, {
          center: [45.014, -122.0],
          zoom: 14,
          zoomControl: false,
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
          const observer = new ResizeObserver(() => map.invalidateSize());
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

      markers.clearLayers();
      for (const edge of edges) {
        const from = byKey.get(edge.from);
        const to = byKey.get(edge.to);
        if (from?.lat == null || from.lon == null || to?.lat == null || to.lon == null) continue;
        L.polyline(
          [
            [from.lat, from.lon],
            [to.lat, to.lon],
          ],
          { className: "map-path", interactive: false },
        ).addTo(markers);
      }
      // Fan out markers sharing one coordinate so none hides another.
      const buckets = new Map<string, MapNode[]>();
      for (const node of georef) {
        const key = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        buckets.set(key, [...(buckets.get(key) ?? []), node]);
      }
      for (const node of georef) {
        const bucketKey = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        const bucket = buckets.get(bucketKey) ?? [node];
        const index = bucket.findIndex((candidate) => candidate.key === node.key);
        const angle = bucket.length > 1 ? (Math.PI * 2 * index) / bucket.length : 0;
        const offset = bucket.length > 1 ? 0.0012 : 0;
        const isFocus = focusKey != null && node.key === focusKey;

        const marker = L.circleMarker(
          [(node.lat as number) + Math.cos(angle) * offset, (node.lon as number) + Math.sin(angle) * offset],
          {
            radius: markerRadius(node, isFocus),
            className: `mk ${occupancyClass(node)}${isFocus ? " mk-here" : ""}`,
          },
        );
        marker.bindTooltip(node.name, { direction: "top" });
        marker.on("click", () => onNodeClickRef.current?.(node));
        marker.addTo(markers);
      }

      // Ease over to a newly focused place.
      if (focusKey && focusKey !== lastFocusRef.current) {
        lastFocusRef.current = focusKey;
        const node = byKey.get(focusKey);
        if (node) {
          map.flyTo([node.lat as number, node.lon as number], Math.max(map.getZoom(), 15), { duration: 0.9 });
        }
      }
      if (!focusKey) lastFocusRef.current = null;
    });

    return () => {
      active = false;
    };
  }, [nodes, edges, mapStyle, focusKey, frame]);

  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      tileLayerRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className={`world-map world-map--${mapStyle ?? "loading"}`} />;
}

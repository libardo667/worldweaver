import { useEffect, useRef } from "react";
import type { LocationGraphEdge, LocationGraphNode } from "../api/wwClient";
import "leaflet/dist/leaflet.css";

type Props = {
  nodes: LocationGraphNode[];
  edges: LocationGraphEdge[];
  onNodeClick?: (name: string) => void;
  pendingDest?: string | null;
  pendingPath?: string[];
  onViewportChange?: (bounds: { north: number; south: number; east: number; west: number }) => void;
  searchQuery?: string;
};

const SF_CENTER: [number, number] = [37.7749, -122.4194];
const SF_ZOOM = 12;

export function LocationMap({ nodes, onNodeClick, pendingDest, pendingPath, onViewportChange, searchQuery }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersGroupRef = useRef<L.LayerGroup | null>(null);
  const lastPlayerPosRef = useRef<[number, number] | null>(null);
  const onViewportChangeRef = useRef<Props["onViewportChange"]>(onViewportChange);
  const suppressViewportEventsRef = useRef(0);
  const lastSearchFitSignatureRef = useRef("");
  const lastPassiveFitSignatureRef = useRef("");
  const lastViewportSignatureRef = useRef("");
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    onViewportChangeRef.current = onViewportChange;
  }, [onViewportChange]);

  useEffect(() => {
    if (!containerRef.current) return;

    let isAsyncActive = true;

    import("leaflet").then((Lmod) => {
      if (!isAsyncActive) return;
      const L = Lmod.default;

      // 1. Initialize map only once
      if (!mapRef.current) {
        const map = L.map(containerRef.current!, {
          center: SF_CENTER,
          zoom: SF_ZOOM,
          zoomControl: true,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
          maxZoom: 19,
        }).addTo(map);

        markersGroupRef.current = L.layerGroup().addTo(map);
        mapRef.current = map;

        const emitViewport = () => {
          if (suppressViewportEventsRef.current > 0) {
            suppressViewportEventsRef.current -= 1;
            return;
          }
          const currentBounds = map.getBounds();
          const nextViewport = {
            north: currentBounds.getNorth(),
            south: currentBounds.getSouth(),
            east: currentBounds.getEast(),
            west: currentBounds.getWest(),
          };
          const signature = [
            nextViewport.north,
            nextViewport.south,
            nextViewport.east,
            nextViewport.west,
          ]
            .map((value) => value.toFixed(5))
            .join("|");
          if (signature === lastViewportSignatureRef.current) {
            return;
          }
          lastViewportSignatureRef.current = signature;
          onViewportChangeRef.current?.(nextViewport);
        };

        map.on("moveend", emitViewport);
        map.on("zoomend", emitViewport);
        if (typeof ResizeObserver !== "undefined") {
          const observer = new ResizeObserver(() => {
            map.invalidateSize();
          });
          observer.observe(containerRef.current!);
          resizeObserverRef.current = observer;
        }
        emitViewport();
        requestAnimationFrame(() => {
          map.invalidateSize();
        });
      }

      const map = mapRef.current;
      const markersGroup = markersGroupRef.current;
      if (!map || !markersGroup) return;

      // 2. Update markers
      markersGroup.clearLayers();
      const georef = nodes.filter((n) => n.lat != null && n.lon != null);
      const pathSet = new Set(pendingPath ?? []);
      const overlapBuckets = new Map<string, typeof georef>();
      for (const node of georef) {
        const key = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        const bucket = overlapBuckets.get(key) ?? [];
        bucket.push(node);
        overlapBuckets.set(key, bucket);
      }

      georef.forEach((node) => {
        const isPending = pendingDest === node.name;
        const isOnPath = !node.is_player && pathSet.has(node.name);
        const totalCount = node.present_count ?? ((node.count ?? 0) + (node.agent_count ?? 0));
        const isLandmark = node.node_type === "landmark";
        const overlapKey = `${Number(node.lat).toFixed(5)}:${Number(node.lon).toFixed(5)}`;
        const bucket = overlapBuckets.get(overlapKey) ?? [node];
        const overlapIndex = bucket.findIndex((candidate) => candidate.key === node.key);
        const overlapCount = bucket.length;
        const angle = overlapCount > 1 ? (Math.PI * 2 * overlapIndex) / overlapCount : 0;
        const offsetRadius = overlapCount > 1 ? 0.0012 : 0;
        const markerLat = (node.lat as number) + Math.cos(angle) * offsetRadius;
        const markerLon = (node.lon as number) + Math.sin(angle) * offsetRadius;

        const occupiedColor = totalCount >= 4 ? "#c2410c" : totalCount >= 2 ? "#f97316" : "#fdba74";
        const occupiedBorder = totalCount >= 4 ? "#9a3412" : totalCount >= 2 ? "#ea580c" : "#fb923c";

        const color = node.is_player ? "#f59e0b" : isPending ? "#22c55e" : isOnPath ? "#4ade80" : totalCount > 0 ? occupiedColor : isLandmark ? "#14b8a6" : "#0891b2";
        const borderColor = node.is_player ? "#d97706" : isPending ? "#16a34a" : isOnPath ? "#16a34a" : totalCount > 0 ? occupiedBorder : isLandmark ? "#0f766e" : "#0e7490";
        const radius = node.is_player ? 10 : isPending ? 9 : totalCount > 0 ? (isLandmark ? 7 : 8) : isLandmark ? 5 : 6;

        const marker = L.circleMarker([markerLat, markerLon], {
          radius,
          fillColor: color,
          color: borderColor,
          weight: isPending || isOnPath ? 2.5 : 2,
          opacity: 1,
          fillOpacity: 0.85,
        });

        const allNames = node.present_names ?? [...(node.player_names ?? []), ...(node.agent_names ?? [])];
        let label = node.name;
        if (totalCount > 0) {
          label += ` (${totalCount} visitor${totalCount !== 1 ? "s" : ""})`;
          if (allNames.length > 0) {
            label += `<br><em style="font-size:0.85em;opacity:0.8">${allNames.join(" · ")}</em>`;
          }
        }
        if (node.description && !totalCount) {
          label += `<br><em style="font-size:0.85em;opacity:0.8">${node.description}</em>`;
        }
        marker.bindTooltip(label, { permanent: isPending || isOnPath, direction: "top", sticky: false });

        if (onNodeClick) {
          marker.on("click", () => onNodeClick(node.name));
        }

        marker.addTo(markersGroup);

        if (isOnPath || isPending) {
          setTimeout(() => {
            const el = marker.getElement();
            if (el) {
              el.classList.add("ww-locmap-path");
              el.classList.add("ww-locmap-clickable");
            }
          }, 0);
        } else if (onNodeClick) {
          setTimeout(() => {
            marker.getElement()?.classList.add("ww-locmap-clickable");
          }, 0);
        }
      });

      // 3. Smart Centering
      const playerNode = nodes.find((n) => n.is_player);
      if (playerNode?.lat != null && playerNode?.lon != null) {
        const newPos: [number, number] = [playerNode.lat, playerNode.lon];
        const hasMoved = !lastPlayerPosRef.current ||
          lastPlayerPosRef.current[0] !== newPos[0] ||
          lastPlayerPosRef.current[1] !== newPos[1];

        if (hasMoved) {
          map.setView(newPos, 14);
          lastPlayerPosRef.current = newPos;
        }
      }

      const normalizedSearch = searchQuery?.trim() ?? "";
      if (!normalizedSearch) {
        lastSearchFitSignatureRef.current = "";
      }
      const passiveFitSignature = georef.map((node) => node.key).sort().join("|");
      const searchFitSignature = normalizedSearch
        ? `${normalizedSearch}|${georef.map((node) => node.key).sort().join("|")}`
        : "";
      if (
        normalizedSearch &&
        georef.length > 0 &&
        lastSearchFitSignatureRef.current !== searchFitSignature
      ) {
        const bounds = L.latLngBounds(georef.map((node) => [node.lat as number, node.lon as number] as [number, number]));
        if (bounds.isValid()) {
          suppressViewportEventsRef.current = 2;
          map.fitBounds(bounds.pad(0.2), { maxZoom: georef.length === 1 ? 16 : 15 });
          lastSearchFitSignatureRef.current = searchFitSignature;
        }
      }
      if (
        !normalizedSearch &&
        !playerNode &&
        georef.length > 0 &&
        lastPassiveFitSignatureRef.current !== passiveFitSignature
      ) {
        const bounds = L.latLngBounds(
          georef.map((node) => [node.lat as number, node.lon as number] as [number, number]),
        );
        if (bounds.isValid()) {
          suppressViewportEventsRef.current = 2;
          map.fitBounds(bounds.pad(0.15), { maxZoom: georef.length === 1 ? 15 : 13 });
          lastPassiveFitSignatureRef.current = passiveFitSignature;
        }
      }
      if (playerNode) {
        lastPassiveFitSignatureRef.current = "";
      }
    });

    return () => {
      isAsyncActive = false;
      // Note: We don't remove the map on every effect run, only on unmount.
      // But how do we know it's a true unmount in a consolidated effect?
      // React 18 in dev might run this twice.
      // We'll rely on the actual unmount of the component to clean up.
    };
  }, [nodes, onNodeClick, pendingDest, pendingPath, searchQuery]);

  // Handle true unmount
  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}

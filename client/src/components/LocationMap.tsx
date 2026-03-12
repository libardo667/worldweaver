import { useEffect, useRef } from "react";
import type { LocationGraphEdge, LocationGraphNode } from "../api/wwClient";
import "leaflet/dist/leaflet.css";

type Props = {
  nodes: LocationGraphNode[];
  edges: LocationGraphEdge[];
  onNodeClick?: (name: string) => void;
  pendingDest?: string | null;
  pendingPath?: string[];
};

const SF_CENTER: [number, number] = [37.7749, -122.4194];
const SF_ZOOM = 12;

export function LocationMap({ nodes, edges, onNodeClick, pendingDest, pendingPath }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersGroupRef = useRef<L.LayerGroup | null>(null);
  const lastPlayerPosRef = useRef<[number, number] | null>(null);

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
      }

      const map = mapRef.current;
      const markersGroup = markersGroupRef.current;
      if (!map || !markersGroup) return;

      // 2. Update markers
      markersGroup.clearLayers();
      const georef = nodes.filter((n) => n.lat != null && n.lon != null);
      const pathSet = new Set(pendingPath ?? []);

      georef.forEach((node) => {
        const isPending = pendingDest === node.name;
        const isOnPath = !node.is_player && pathSet.has(node.name);
        const agentCount = node.agent_count ?? 0;

        const agentColor = agentCount >= 4 ? "#c2410c" : agentCount >= 2 ? "#f97316" : "#fdba74";
        const agentBorder = agentCount >= 4 ? "#9a3412" : agentCount >= 2 ? "#ea580c" : "#fb923c";

        const color = node.is_player ? "#f59e0b" : isPending ? "#22c55e" : isOnPath ? "#4ade80" : agentCount > 0 ? agentColor : "#0891b2";
        const borderColor = node.is_player ? "#d97706" : isPending ? "#16a34a" : isOnPath ? "#16a34a" : agentCount > 0 ? agentBorder : "#0e7490";
        const radius = node.is_player ? 10 : isPending ? 9 : node.count > 0 || agentCount > 0 ? 8 : 5;

        const marker = L.circleMarker([node.lat as number, node.lon as number], {
          radius,
          fillColor: color,
          color: borderColor,
          weight: isPending || isOnPath ? 2.5 : 2,
          opacity: 1,
          fillOpacity: 0.85,
        });

        const parts: string[] = [node.name];
        if (node.count > 0) parts.push(`${node.count} visitor${node.count !== 1 ? "s" : ""}`);
        if (agentCount > 0) parts.push(`${agentCount} agent${agentCount !== 1 ? "s" : ""}`);
        const label = parts.length > 1 ? `${parts[0]} (${parts.slice(1).join(", ")})` : parts[0];
        marker.bindTooltip(label, { permanent: isPending || isOnPath, direction: "top" });

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

      // 4. Force Leaflet to re-detect size to prevent gray screens
      map.invalidateSize();
    });

    return () => {
      isAsyncActive = false;
      // Note: We don't remove the map on every effect run, only on unmount.
      // But how do we know it's a true unmount in a consolidated effect?
      // React 18 in dev might run this twice.
      // We'll rely on the actual unmount of the component to clean up.
    };
  }, [nodes, edges, onNodeClick, pendingDest, pendingPath]);

  // Handle true unmount
  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}

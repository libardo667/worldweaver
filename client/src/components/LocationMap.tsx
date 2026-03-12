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

  useEffect(() => {
    if (!containerRef.current) return;

    import("leaflet").then((Lmod) => {
      const L = Lmod.default;

      // Tear down previous map instance when props change
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      const map = L.map(containerRef.current!, {
        center: SF_CENTER,
        zoom: SF_ZOOM,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
        maxZoom: 19,
      }).addTo(map);

      // Only plot nodes that have real coordinates
      const georef = nodes.filter((n) => n.lat != null && n.lon != null);

      // Path set for blinking green route preview (excludes player's current location)
      const pathSet = new Set(pendingPath ?? []);

      georef.forEach((node) => {
        const isPending = pendingDest === node.name;
        const isOnPath = !node.is_player && pathSet.has(node.name);
        const agentCount = node.agent_count ?? 0;

        // Agent-presence orange gradient (light → medium → dark)
        const agentColor =
          agentCount >= 4 ? "#c2410c" : agentCount >= 2 ? "#f97316" : "#fdba74";
        const agentBorder =
          agentCount >= 4 ? "#9a3412" : agentCount >= 2 ? "#ea580c" : "#fb923c";

        const color = node.is_player
          ? "#f59e0b"
          : isPending
            ? "#22c55e"
            : isOnPath
              ? "#4ade80"
              : agentCount > 0
                ? agentColor
                : "#0891b2";
        const borderColor = node.is_player
          ? "#d97706"
          : isPending
            ? "#16a34a"
            : isOnPath
              ? "#16a34a"
              : agentCount > 0
                ? agentBorder
                : "#0e7490";
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
          marker.getElement()?.classList.add("ww-locmap-clickable");
        }

        marker.addTo(map);

        // Apply blink animation after the marker element is in the DOM
        if (isOnPath || isPending) {
          setTimeout(() => {
            marker.getElement()?.classList.add("ww-locmap-path");
          }, 0);
        }
      });

      // Pan to player location if available
      const playerNode = nodes.find((n) => n.is_player);
      if (playerNode?.lat != null && playerNode?.lon != null) {
        map.setView([playerNode.lat, playerNode.lon], 14);
      }

      mapRef.current = map;
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [nodes, edges, onNodeClick, pendingDest, pendingPath]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}

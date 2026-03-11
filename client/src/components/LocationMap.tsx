import { useEffect, useRef } from "react";
import type { LocationGraphEdge, LocationGraphNode } from "../api/wwClient";
import "leaflet/dist/leaflet.css";

type Props = {
  nodes: LocationGraphNode[];
  edges: LocationGraphEdge[];
  onNodeClick?: (name: string) => void;
  pendingDest?: string | null;
};

const SF_CENTER: [number, number] = [37.7749, -122.4194];
const SF_ZOOM = 12;

export function LocationMap({ nodes, edges, onNodeClick, pendingDest }: Props) {
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

      georef.forEach((node) => {
        const isPending = pendingDest === node.name;
        const color = node.is_player
          ? "#f59e0b"
          : isPending
            ? "#fb923c"
            : "#0891b2";
        const borderColor = node.is_player
          ? "#d97706"
          : isPending
            ? "#ea580c"
            : "#0e7490";
        const radius = node.is_player ? 10 : node.count > 0 ? 8 : 5;

        const marker = L.circleMarker([node.lat as number, node.lon as number], {
          radius,
          fillColor: color,
          color: borderColor,
          weight: 2,
          opacity: 1,
          fillOpacity: 0.85,
        });

        const label = node.count > 0 ? `${node.name} (${node.count})` : node.name;
        marker.bindTooltip(label, { permanent: false, direction: "top" });

        if (onNodeClick) {
          marker.on("click", () => onNodeClick(node.name));
          marker.getElement()?.classList.add("ww-locmap-clickable");
        }

        marker.addTo(map);
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
  }, [nodes, edges, onNodeClick, pendingDest]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}

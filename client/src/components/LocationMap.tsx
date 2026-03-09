import type { LocationGraphEdge, LocationGraphNode } from "../api/wwClient";

type Props = {
  nodes: LocationGraphNode[];
  edges: LocationGraphEdge[];
  onNodeClick?: (name: string) => void;
};

const W = 220;
const H = 180;
const CX = W / 2;
const CY = H / 2;
const ORBIT = 60;
const NODE_R = 14;

function layoutNodes(nodes: LocationGraphNode[]) {
  if (nodes.length === 0) return [];
  if (nodes.length === 1) {
    return [{ ...nodes[0], x: CX, y: CY }];
  }
  return nodes.map((n, i) => {
    const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    return {
      ...n,
      x: CX + Math.cos(angle) * ORBIT,
      y: CY + Math.sin(angle) * ORBIT,
    };
  });
}

export function LocationMap({ nodes, edges, onNodeClick }: Props) {
  if (nodes.length === 0) return null;

  const laid = layoutNodes(nodes);
  const byKey = new Map(laid.map((n) => [n.key, n]));

  // Deduplicate edges (A→B and B→A both exist in the DB)
  const seen = new Set<string>();
  const dedupedEdges = edges.filter((e) => {
    const fwd = `${e.from}|${e.to}`;
    const rev = `${e.to}|${e.from}`;
    if (seen.has(fwd) || seen.has(rev)) return false;
    seen.add(fwd);
    return true;
  });

  return (
    <svg
      className="ww-location-map"
      viewBox={`0 0 ${W} ${H}`}
      aria-label="World location map"
    >
      {/* Edges */}
      <g aria-hidden="true">
        {dedupedEdges.map((e, i) => {
          const src = byKey.get(e.from);
          const tgt = byKey.get(e.to);
          if (!src || !tgt) return null;
          return (
            <line
              key={i}
              className="ww-locmap-edge"
              x1={src.x} y1={src.y}
              x2={tgt.x} y2={tgt.y}
            />
          );
        })}
      </g>

      {/* Nodes */}
      {laid.map((n) => {
        const labelY = n.y + NODE_R + 8;
        const clipped = n.name.length > 16 ? n.name.slice(0, 15) + "…" : n.name;
        return (
          <g
            key={n.key}
            className={`ww-locmap-node${n.is_player ? " ww-locmap-node--you" : ""}${onNodeClick ? " ww-locmap-node--clickable" : ""}`}
            onClick={onNodeClick ? () => onNodeClick(n.name) : undefined}
          >
            <circle cx={n.x} cy={n.y} r={NODE_R} className="ww-locmap-circle" />
            {n.count > 0 && (
              <text
                x={n.x} y={n.y + 1}
                className="ww-locmap-count"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {n.count}
              </text>
            )}
            <text
              x={n.x} y={labelY}
              className="ww-locmap-label"
              textAnchor="middle"
              dominantBaseline="hanging"
            >
              {clipped}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

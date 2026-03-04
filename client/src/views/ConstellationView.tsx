import { useEffect, useMemo, useState } from "react";

import { getSemanticConstellation } from "../api/wwClient";
import type {
  ConstellationStorylet,
  SemanticConstellationResponse,
} from "../types";

type ConstellationViewProps = {
  sessionId: string;
  onJumpToLocation: (location: string) => Promise<void>;
};

type GraphNode = {
  storylet: ConstellationStorylet;
  x: number;
  y: number;
  radius: number;
  intensity: number;
};

type GraphEdge = {
  key: string;
  sourceId: number;
  targetId: number;
  kind: "semantic" | "spatial" | "both";
  selected: boolean;
};

const TOP_N_OPTIONS = [10, 20, 40, 60];
const RADIUS_OPTIONS: Array<{ label: string; value: number }> = [
  { label: "Any", value: 0 },
  { label: "<= 2", value: 2 },
  { label: "<= 4", value: 4 },
  { label: "<= 8", value: 8 },
];
const GRAPH_WIDTH = 920;
const GRAPH_HEIGHT = 440;
const GRAPH_PADDING = 28;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function pseudoRandom(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function hasPosition(storylet: ConstellationStorylet): boolean {
  return Boolean(
    storylet.position &&
      Number.isFinite(storylet.position.x) &&
      Number.isFinite(storylet.position.y),
  );
}

export function ConstellationView({
  sessionId,
  onJumpToLocation,
}: ConstellationViewProps) {
  const [topN, setTopN] = useState(20);
  const [showAccessibleOnly, setShowAccessibleOnly] = useState(false);
  const [radiusLimit, setRadiusLimit] = useState(0);
  const [pending, setPending] = useState(false);
  const [jumping, setJumping] = useState(false);
  const [error, setError] = useState<string>("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [payload, setPayload] = useState<SemanticConstellationResponse | null>(null);
  const [showSemanticEdges, setShowSemanticEdges] = useState(true);
  const [showSpatialEdges, setShowSpatialEdges] = useState(true);
  const [layoutSeed, setLayoutSeed] = useState(0);

  async function refresh() {
    setPending(true);
    setError("");
    try {
      const data = await getSemanticConstellation(sessionId, topN);
      setPayload(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, topN]);

  const filteredStorylets = useMemo(() => {
    const items = payload?.storylets ?? [];
    return items.filter((storylet) => {
      if (showAccessibleOnly && !storylet.accessible) {
        return false;
      }
      if (radiusLimit > 0) {
        if (typeof storylet.distance !== "number") {
          return false;
        }
        return storylet.distance <= radiusLimit;
      }
      return true;
    });
  }, [payload?.storylets, showAccessibleOnly, radiusLimit]);

  useEffect(() => {
    if (!filteredStorylets.length) {
      setSelectedId(null);
      return;
    }
    if (selectedId == null || !filteredStorylets.some((item) => item.id === selectedId)) {
      setSelectedId(filteredStorylets[0].id);
    }
  }, [filteredStorylets, selectedId]);

  const selectedStorylet = useMemo<ConstellationStorylet | null>(
    () =>
      selectedId == null
        ? null
        : filteredStorylets.find((item) => item.id === selectedId) ?? null,
    [filteredStorylets, selectedId],
  );

  const graph = useMemo(() => {
    if (!filteredStorylets.length) {
      return {
        nodes: [] as GraphNode[],
        nodeById: new Map<number, GraphNode>(),
        edges: [] as GraphEdge[],
      };
    }

    const minScore = Math.min(...filteredStorylets.map((storylet) => storylet.score));
    const maxScore = Math.max(...filteredStorylets.map((storylet) => storylet.score));
    const scoreRange = maxScore - minScore || 1;
    const positioned = filteredStorylets.filter((storylet) => hasPosition(storylet));
    const canUseSpatialLayout = positioned.length >= 2;

    let minX = 0;
    let maxX = 1;
    let minY = 0;
    let maxY = 1;
    if (canUseSpatialLayout) {
      minX = Math.min(...positioned.map((storylet) => storylet.position!.x));
      maxX = Math.max(...positioned.map((storylet) => storylet.position!.x));
      minY = Math.min(...positioned.map((storylet) => storylet.position!.y));
      maxY = Math.max(...positioned.map((storylet) => storylet.position!.y));
    }
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);

    const nodes = filteredStorylets.map((storylet, index) => {
      const normalizedScore = clamp((storylet.score - minScore) / scoreRange, 0, 1);
      const radius = 8 + normalizedScore * 12;
      const intensity = 0.45 + normalizedScore * 0.55;

      let x = GRAPH_WIDTH * 0.5;
      let y = GRAPH_HEIGHT * 0.5;

      if (canUseSpatialLayout && hasPosition(storylet)) {
        const nx = (storylet.position!.x - minX) / spanX;
        const ny = (storylet.position!.y - minY) / spanY;
        x = GRAPH_PADDING + nx * (GRAPH_WIDTH - GRAPH_PADDING * 2);
        y = GRAPH_PADDING + ny * (GRAPH_HEIGHT - GRAPH_PADDING * 2);
      } else {
        const angle = (index / filteredStorylets.length) * Math.PI * 2 + layoutSeed * 0.55;
        const orbit = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * (0.28 + (index % 3) * 0.05);
        x = GRAPH_WIDTH * 0.5 + Math.cos(angle) * orbit;
        y = GRAPH_HEIGHT * 0.5 + Math.sin(angle) * (orbit * 0.72);
      }

      x += (pseudoRandom(storylet.id * 11 + layoutSeed * 17 + 1) - 0.5) * 24;
      y += (pseudoRandom(storylet.id * 13 + layoutSeed * 19 + 1) - 0.5) * 20;
      x = clamp(x, GRAPH_PADDING, GRAPH_WIDTH - GRAPH_PADDING);
      y = clamp(y, GRAPH_PADDING, GRAPH_HEIGHT - GRAPH_PADDING);

      return { storylet, x, y, radius, intensity };
    });

    const nodeById = new Map<number, GraphNode>();
    for (const node of nodes) {
      nodeById.set(node.storylet.id, node);
    }

    const edgeMap = new Map<
      string,
      { sourceId: number; targetId: number; semantic: boolean; spatial: boolean }
    >();
    const upsertEdge = (left: number, right: number) => {
      const sourceId = Math.min(left, right);
      const targetId = Math.max(left, right);
      if (sourceId === targetId || !nodeById.has(sourceId) || !nodeById.has(targetId)) {
        return null;
      }
      const key = `${sourceId}:${targetId}`;
      const existing = edgeMap.get(key);
      if (existing) {
        return existing;
      }
      const next = { sourceId, targetId, semantic: false, spatial: false };
      edgeMap.set(key, next);
      return next;
    };

    for (const storylet of filteredStorylets) {
      for (const neighborId of storylet.edges.semantic_neighbors) {
        const entry = upsertEdge(storylet.id, neighborId);
        if (entry) {
          entry.semantic = true;
        }
      }
      for (const neighborId of Object.values(storylet.edges.spatial_neighbors)) {
        const entry = upsertEdge(storylet.id, neighborId);
        if (entry) {
          entry.spatial = true;
        }
      }
    }

    const edges = Array.from(edgeMap.entries())
      .filter(([, edge]) => {
        const allowSemantic = showSemanticEdges && edge.semantic;
        const allowSpatial = showSpatialEdges && edge.spatial;
        return allowSemantic || allowSpatial;
      })
      .map(([key, edge]) => {
        const kind =
          edge.semantic && edge.spatial
            ? "both"
            : edge.semantic
              ? "semantic"
              : "spatial";
        return {
          key,
          sourceId: edge.sourceId,
          targetId: edge.targetId,
          kind,
          selected:
            selectedId != null &&
            (edge.sourceId === selectedId || edge.targetId === selectedId),
        } as GraphEdge;
      });

    return { nodes, nodeById, edges };
  }, [
    filteredStorylets,
    layoutSeed,
    selectedId,
    showSemanticEdges,
    showSpatialEdges,
  ]);

  async function handleJump() {
    if (!selectedStorylet?.location) {
      return;
    }
    setJumping(true);
    try {
      await onJumpToLocation(selectedStorylet.location);
    } finally {
      setJumping(false);
    }
  }

  return (
    <main className="constellation-view" aria-label="Constellation mode">
      <section className="panel constellation-controls">
        <header className="panel-header">
          <h2>Constellation</h2>
          <span className="panel-meta">Semantic debug view</span>
        </header>
        <div className="reflect-controls-row">
          <label htmlFor="constellation-topn">Top-N</label>
          <select
            id="constellation-topn"
            value={String(topN)}
            onChange={(event) => setTopN(Number(event.target.value))}
          >
            {TOP_N_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <label htmlFor="constellation-radius">Radius</label>
          <select
            id="constellation-radius"
            value={String(radiusLimit)}
            onChange={(event) => setRadiusLimit(Number(event.target.value))}
          >
            {RADIUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <label className="constellation-check">
            <input
              type="checkbox"
              checked={showAccessibleOnly}
              onChange={(event) => setShowAccessibleOnly(event.target.checked)}
            />
            Accessible only
          </label>
          <label className="constellation-check">
            <input
              type="checkbox"
              checked={showSemanticEdges}
              onChange={(event) => setShowSemanticEdges(event.target.checked)}
            />
            Semantic edges
          </label>
          <label className="constellation-check">
            <input
              type="checkbox"
              checked={showSpatialEdges}
              onChange={(event) => setShowSpatialEdges(event.target.checked)}
            />
            Spatial edges
          </label>
          <button
            type="button"
            className="text-btn"
            onClick={() => setLayoutSeed((value) => value + 1)}
          >
            Reset layout
          </button>
          <button type="button" className="text-btn" onClick={refresh} disabled={pending}>
            Refresh
          </button>
        </div>
        <p className="muted">
          Context: {payload?.context.location ?? "unknown"} | Showing {filteredStorylets.length} of{" "}
          {payload?.count ?? 0}
        </p>
        {error ? <p className="muted">Load failed: {error}</p> : null}
      </section>

      <section className="panel constellation-graph-panel">
        <header className="panel-header">
          <h3>Graph</h3>
          <span className="panel-meta">
            {graph.nodes.length} nodes | {graph.edges.length} edges
          </span>
        </header>
        <div className="constellation-graph-shell">
          {graph.nodes.length > 0 ? (
            <svg
              className="constellation-graph"
              viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
              role="img"
              aria-label="Constellation node link graph"
            >
              <g aria-hidden="true">
                {graph.edges.map((edge) => {
                  const source = graph.nodeById.get(edge.sourceId);
                  const target = graph.nodeById.get(edge.targetId);
                  if (!source || !target) {
                    return null;
                  }
                  return (
                    <line
                      key={edge.key}
                      className={`constellation-edge ${edge.kind}${edge.selected ? " active" : ""}`}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                    />
                  );
                })}
              </g>
              <g>
                {graph.nodes.map((node) => {
                  const selected = node.storylet.id === selectedId;
                  return (
                    <g
                      key={node.storylet.id}
                      className={`constellation-node ${node.storylet.accessible ? "accessible" : "blocked"}${selected ? " selected" : ""}`}
                      transform={`translate(${node.x} ${node.y})`}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedId(node.storylet.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(node.storylet.id);
                        }
                      }}
                    >
                      <title>
                        {node.storylet.title} score {node.storylet.score.toFixed(4)}{" "}
                        {node.storylet.accessible ? "accessible" : "blocked"}
                      </title>
                      <circle className="constellation-node-hit" r={node.radius + 9} />
                      <circle className="constellation-node-ring" r={node.radius + 3} />
                      <circle
                        className="constellation-node-core"
                        r={node.radius}
                        opacity={node.intensity}
                      />
                    </g>
                  );
                })}
              </g>
            </svg>
          ) : (
            <p className="muted constellation-graph-empty">
              No candidates match current filters.
            </p>
          )}
        </div>
        <p className="muted">
          Click a node to inspect details. Selected node remains synced with the list.
        </p>
      </section>

      <section className="panel constellation-list-panel">
        <header className="panel-header">
          <h3>Scored Storylets</h3>
          <span className="panel-meta">{pending ? "Refreshing..." : "Click for details"}</span>
        </header>
        <ul className="constellation-list">
          {filteredStorylets.map((storylet) => (
            <li key={storylet.id}>
              <button
                type="button"
                className={`constellation-item ${storylet.id === selectedId ? "active" : ""}`}
                onClick={() => setSelectedId(storylet.id)}
              >
                <strong>{storylet.title}</strong>
                <span>score {storylet.score.toFixed(4)}</span>
                <span>{storylet.accessible ? "accessible" : "blocked"}</span>
              </button>
            </li>
          ))}
          {filteredStorylets.length === 0 ? <li className="muted">No candidates match filters.</li> : null}
        </ul>
      </section>

      <section className="panel constellation-detail-panel">
        <header className="panel-header">
          <h3>Details</h3>
          <span className="panel-meta">Selected candidate</span>
        </header>
        {selectedStorylet ? (
          <div className="constellation-detail">
            <p>
              <strong>{selectedStorylet.title}</strong> (#{selectedStorylet.id})
            </p>
            <p>Score: {selectedStorylet.score.toFixed(6)}</p>
            <p>Accessible: {selectedStorylet.accessible ? "yes" : "no"}</p>
            <p>
              Position:{" "}
              {selectedStorylet.position
                ? `(${selectedStorylet.position.x}, ${selectedStorylet.position.y})`
                : "none"}
            </p>
            <p>Distance: {typeof selectedStorylet.distance === "number" ? selectedStorylet.distance : "n/a"}</p>
            <p>Location var: {selectedStorylet.location ?? "n/a"}</p>
            <p>
              Spatial neighbors:{" "}
              {Object.keys(selectedStorylet.edges.spatial_neighbors).length > 0
                ? Object.entries(selectedStorylet.edges.spatial_neighbors)
                    .map(([direction, id]) => `${direction}:${id}`)
                    .join(", ")
                : "none"}
            </p>
            <p>
              Semantic neighbors:{" "}
              {selectedStorylet.edges.semantic_neighbors.length > 0
                ? selectedStorylet.edges.semantic_neighbors.join(", ")
                : "none"}
            </p>
            <button
              type="button"
              className="text-btn"
              onClick={handleJump}
              disabled={!selectedStorylet.location || jumping}
            >
              Jump to location
            </button>
          </div>
        ) : (
          <p className="muted">Select a storylet to inspect details.</p>
        )}
      </section>
    </main>
  );
}

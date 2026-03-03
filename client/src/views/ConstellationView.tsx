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

const TOP_N_OPTIONS = [10, 20, 40, 60];
const RADIUS_OPTIONS: Array<{ label: string; value: number }> = [
  { label: "Any", value: 0 },
  { label: "<= 2", value: 2 },
  { label: "<= 4", value: 4 },
  { label: "<= 8", value: 8 },
];

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

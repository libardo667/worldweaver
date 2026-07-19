// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef } from "react";
import type { EntryInfo, Grounding, MapNode, ShardExperience } from "../api/types";

type Props = {
  experience: ShardExperience | null;
  entry: EntryInfo | null;
  grounding: Grounding | null;
  nodes: MapNode[];
  onLookAround: () => void;
  onJoin: () => void;
};

export function townName(experience: ShardExperience | null): string {
  const raw = String(experience?.shard_id ?? "")
    .replace(/^ww[_-]/, "")
    .replace(/[_-]+/g, " ")
    .trim();
  if (!raw) return "WorldWeaver";
  return raw.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ThresholdOverlay({ experience, entry, grounding, onLookAround, onJoin }: Props) {
  const summary = experience?.entry_disclosure?.summary ?? "";
  const hasWorld = entry != null;
  const firstActionRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (hasWorld) firstActionRef.current?.focus();
  }, [hasWorld]);

  return (
    <div className="threshold">
      <div className="threshold-card" role="dialog" aria-labelledby="threshold-title">
        <h1 id="threshold-title" className="threshold-title">{townName(experience)}</h1>
        {grounding && (
          <p className="threshold-weather">
            {grounding.datetime_str} · {grounding.weather_description}
          </p>
        )}
        {summary && <p className="threshold-summary">{summary}</p>}
        <div className="threshold-actions">
          <button ref={firstActionRef} className="btn btn-primary" onClick={onLookAround} disabled={!hasWorld}>
            Look around
          </button>
          <button className="btn btn-quiet" onClick={onJoin} disabled={!hasWorld}>
            Join the world
          </button>
        </div>
        <p className="threshold-footnote">A small town that keeps living whether or not anyone is watching.</p>
      </div>
    </div>
  );
}

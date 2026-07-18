// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { ShardInfo } from "../types";

type AppTopbarProps = {
  worldContextLabel: string;
  shards: ShardInfo[];
  selectedShardUrl: string;
  onCitySwitch: (shardUrl: string) => void;
  digestLoaded: boolean;
  sceneTotalCount: number;
  worldPresenceCount: number;
  restMetricsLoaded: boolean;
  restingPresenceCount: number;
  observerMode: boolean;
  sessionId: string;
  shortSession: string;
  onNewSession: () => void;
  onOpenSettings: () => void;
};

function nodeLabel(shard: ShardInfo): string {
  const city = String(shard.city_id ?? "").replace(/_/g, " ").trim();
  if (!city || shard.shard_id === shard.city_id) return city || shard.shard_id;
  return `${city} — ${shard.shard_id}`;
}

export function AppTopbar({
  worldContextLabel,
  shards,
  selectedShardUrl,
  onCitySwitch,
  digestLoaded,
  sceneTotalCount,
  worldPresenceCount,
  restMetricsLoaded,
  restingPresenceCount,
  observerMode,
  sessionId,
  shortSession,
  onNewSession,
  onOpenSettings,
}: AppTopbarProps) {
  return (
    <header className="ww-topbar">
      <span className="ww-topbar-title">WorldWeaver</span>
      {worldContextLabel && (
        <span className="ww-world-context" title="Current world context">
          {worldContextLabel}
        </span>
      )}
      {shards.length > 0 && (
        <select
          className="ww-city-picker"
          value={selectedShardUrl}
          onChange={(e) => onCitySwitch(e.target.value)}
          title="Change community node; this starts a fresh local session, not cross-city travel"
        >
          {shards.length > 1 && (
            <option value="" disabled>
              select node
            </option>
          )}
          {shards.map((s) => (
            <option key={s.shard_id} value={s.browser_url}>
              {nodeLabel(s)}
            </option>
          ))}
        </select>
      )}
      <div className="ww-topbar-right">
        {digestLoaded && (
          <>
            <span className="ww-world-stat" title="People at your location">
              scene: {sceneTotalCount} here
            </span>
            <span className="ww-world-stat" title="People currently present across the shard">
              world: {worldPresenceCount} present
            </span>
            {restMetricsLoaded && (
              <span className="ww-world-stat" title="Residents currently resting across the shard">
                resting: {restingPresenceCount}
              </span>
            )}
          </>
        )}
        <span className="ww-session-label" title={observerMode ? "public threshold shell" : sessionId}>
          {observerMode ? "threshold" : `…${shortSession}`}
        </span>
        {!observerMode && (
          <>
            <button className="ww-icon-btn" onClick={onNewSession} title="New session">↺</button>
          </>
        )}
        {!observerMode && (
          <button className="ww-icon-btn" onClick={onOpenSettings} title="Settings">⚙</button>
        )}
      </div>
    </header>
  );
}

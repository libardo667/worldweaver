// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { ShardInfo } from "../types";

type ShardSelectScreenProps = {
  shards: ShardInfo[];
  onSelectShard: (shardUrl: string) => void;
};

function nodeLabel(shard: ShardInfo): string {
  const city = String(shard.city_id ?? "").replace(/_/g, " ").trim();
  if (!city || shard.shard_id === shard.city_id) return city || shard.shard_id;
  return `${city} — ${shard.shard_id}`;
}

export function ShardSelectScreen({ shards, onSelectShard }: ShardSelectScreenProps) {
  return (
    <div className="entry-overlay entry-overlay--alert">
      <div className="entry-alert-box">
        <p className="entry-alert-header">Choose a community node</p>
        <p className="entry-alert-text">
          Each node runs its own local city state. Pick the node where this session begins.
        </p>
        <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%" }}>
          {shards.map((shard) => (
            <button
              key={shard.shard_id}
              className="entry-alert-btn"
              onClick={() => onSelectShard(shard.browser_url)}
              style={{ width: "100%" }}
            >
              {nodeLabel(shard)}
              {shard.status ? ` · ${shard.status}` : ""}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

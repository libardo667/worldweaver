import type { ShardInfo } from "../types";

type ShardSelectScreenProps = {
  shards: ShardInfo[];
  onSelectShard: (shardUrl: string) => void;
};

export function ShardSelectScreen({ shards, onSelectShard }: ShardSelectScreenProps) {
  return (
    <div className="entry-overlay entry-overlay--alert">
      <div className="entry-alert-box">
        <p className="entry-alert-header">Choose a city</p>
        <p className="entry-alert-text">
          The world now spans multiple city shards. Pick where this session begins.
        </p>
        <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%" }}>
          {shards.map((shard) => (
            <button
              key={shard.shard_id}
              className="entry-alert-btn"
              onClick={() => onSelectShard(shard.shard_url)}
              style={{ width: "100%" }}
            >
              {(shard.city_id ?? shard.shard_id).replace(/_/g, " ")}
              {shard.status ? ` · ${shard.status}` : ""}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

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
  mentorBoardMode: boolean;
  observerMode: boolean;
  sessionId: string;
  shortSession: string;
  onNewSession: () => void;
  onOpenSettings: () => void;
};

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
  mentorBoardMode,
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
          title="Switch city"
        >
          {shards.length > 1 && (
            <option value="" disabled>
              select city
            </option>
          )}
          {shards.map((s) => (
            <option key={s.shard_id} value={s.shard_url}>
              {s.city_id ?? s.shard_id}
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
        <span className="ww-session-label" title={mentorBoardMode ? "mentor board" : observerMode ? "public threshold shell" : sessionId}>
          {mentorBoardMode ? "mentor board" : observerMode ? "threshold" : `…${shortSession}`}
        </span>
        {!observerMode && (
          <>
            <button className="ww-icon-btn" onClick={onNewSession} title="New session">↺</button>
            <button className="ww-icon-btn" onClick={onOpenSettings} title="Settings">⚙</button>
          </>
        )}
      </div>
    </header>
  );
}

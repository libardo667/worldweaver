type ParticipationModeScreenProps = {
  allowObserverEntry: boolean;
  onLookAround: () => void;
  onJoinTheWorld: () => void;
};

export function ParticipationModeScreen({
  allowObserverEntry,
  onLookAround,
  onJoinTheWorld,
}: ParticipationModeScreenProps) {
  return (
    <div className="entry-auth-tabs" style={{ flexDirection: "column", gap: "0.75rem", width: "100%", marginTop: "0.75rem" }}>
      {allowObserverEntry && (
        <button className="entry-alert-btn" onClick={onLookAround} style={{ width: "100%" }}>
          Look around
        </button>
      )}
      <button className="entry-alert-btn" onClick={onJoinTheWorld} style={{ width: "100%" }}>
        Join the world
      </button>
    </div>
  );
}

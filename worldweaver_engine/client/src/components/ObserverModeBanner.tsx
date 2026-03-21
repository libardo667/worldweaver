type ObserverModeBannerProps = {
  onJoinWorld: () => void;
  onReturnToWelcome: () => void;
};

export function ObserverModeBanner({ onJoinWorld, onReturnToWelcome }: ObserverModeBannerProps) {
  return (
    <div className="ww-recovery-strip-stack">
      <div className="ww-recovery-strip ww-recovery-strip--info">
        <div className="ww-recovery-strip-copy">
          <p className="ww-recovery-strip-title">Observer Mode</p>
          <p className="ww-recovery-strip-text">
            You are looking through a read-only porthole into the active world.
          </p>
        </div>
        <div className="ww-recovery-strip-actions">
          <button className="ww-recovery-strip-btn" onClick={onJoinWorld}>
            Join the world
          </button>
          <button className="ww-recovery-strip-btn" onClick={onReturnToWelcome}>
            Return to welcome
          </button>
        </div>
      </div>
    </div>
  );
}

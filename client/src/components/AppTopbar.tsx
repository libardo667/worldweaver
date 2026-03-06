import { type ClientMode } from "../app/appHelpers";

type AppTopbarProps = {
  mode: ClientMode;
  onModeChange: (mode: ClientMode) => void;
  enableConstellation: boolean;
  onOpenSettings: () => void;
  sessionLabel: string;
  anyBusy: boolean;
  backendNotice: string;
  onResetSession: () => void;
  pendingScene: boolean;
  enableDevReset: boolean;
  onDevHardReset: () => void;
};

function describeMode(mode: ClientMode): string {
  switch (mode) {
    case "reflect":
      return "Reflect mode chronicle view";
    case "create":
      return "Create mode preference and lens controls";
    case "constellation":
      return "Semantic constellation debug view";
    default:
      return "API-first Explore mode v1";
  }
}

export function AppTopbar({
  mode,
  onModeChange,
  enableConstellation,
  onOpenSettings,
  sessionLabel,
  anyBusy,
  backendNotice,
  onResetSession,
  pendingScene,
  enableDevReset,
  onDevHardReset,
}: AppTopbarProps) {
  return (
    <header className="topbar">
      <div>
        <h1>WorldWeaver Explorer</h1>
        <p>{describeMode(mode)}</p>
      </div>
      <div className="topbar-meta">
        <div className="mode-toggle" role="tablist" aria-label="Client mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "explore"}
            className={`text-btn mode-toggle-btn ${mode === "explore" ? "active" : ""}`}
            onClick={() => onModeChange("explore")}
          >
            Explore
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "reflect"}
            className={`text-btn mode-toggle-btn ${mode === "reflect" ? "active" : ""}`}
            onClick={() => onModeChange("reflect")}
          >
            Reflect
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "create"}
            className={`text-btn mode-toggle-btn ${mode === "create" ? "active" : ""}`}
            onClick={() => onModeChange("create")}
          >
            Create
          </button>
          {enableConstellation ? (
            <button
              type="button"
              role="tab"
              aria-selected={mode === "constellation"}
              className={`text-btn mode-toggle-btn ${mode === "constellation" ? "active" : ""}`}
              onClick={() => onModeChange("constellation")}
            >
              Constellation
            </button>
          ) : null}
        </div>
        <button
          type="button"
          className="settings-toggle-btn"
          onClick={onOpenSettings}
          aria-label="Open settings"
          title="Model and API Settings"
        >
          {"\u2699"}
        </button>
        <span>Session ...{sessionLabel}</span>
        <span className={`backend-status ${anyBusy ? "active" : ""}`}>
          {anyBusy && backendNotice ? backendNotice : "Backend ready"}
        </span>
        <button
          type="button"
          className="danger-btn"
          onClick={onResetSession}
          disabled={anyBusy}
          data-loading={pendingScene ? "true" : "false"}
        >
          Reset session
        </button>
        {enableDevReset ? (
          <button
            type="button"
            className="danger-btn"
            onClick={onDevHardReset}
            disabled={anyBusy}
            data-loading={pendingScene ? "true" : "false"}
          >
            Dev hard reset
          </button>
        ) : null}
      </div>
    </header>
  );
}

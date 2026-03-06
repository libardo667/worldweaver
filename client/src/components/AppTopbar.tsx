import type {
  ClientMode,
  RuntimeBudgetHealth,
  RuntimeLaneState,
  TopbarRuntimeStatusModel,
} from "../app/appHelpers";

type AppTopbarProps = {
  mode: ClientMode;
  onModeChange: (mode: ClientMode) => void;
  enableConstellation: boolean;
  onOpenSettings: () => void;
  sessionLabel: string;
  anyBusy: boolean;
  runtimeStatus: TopbarRuntimeStatusModel;
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

function formatLaneChipLabel(label: string, state: RuntimeLaneState): string {
  if (state === "active") {
    return `${label}: active`;
  }
  if (state === "off") {
    return `${label}: off`;
  }
  return `${label}: idle`;
}

function laneChipTone(state: RuntimeLaneState): "active" | "idle" | "off" {
  if (state === "active") {
    return "active";
  }
  if (state === "off") {
    return "off";
  }
  return "idle";
}

function budgetChipTone(
  health: RuntimeBudgetHealth,
): "ok" | "warn" | "off" {
  if (health === "healthy") {
    return "ok";
  }
  if (health === "warming" || health === "cold") {
    return "warn";
  }
  return "off";
}

export function AppTopbar({
  mode,
  onModeChange,
  enableConstellation,
  onOpenSettings,
  sessionLabel,
  anyBusy,
  runtimeStatus,
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
        <span className={`backend-status ${runtimeStatus.summaryActive ? "active" : ""}`}>
          {runtimeStatus.summaryText}
        </span>
        {runtimeStatus.chipsEnabled ? (
          <div className="runtime-chip-row" aria-live="polite">
            <span
              className={`runtime-chip runtime-chip-${laneChipTone(runtimeStatus.laneStates.scene)}`}
            >
              {formatLaneChipLabel("Scene", runtimeStatus.laneStates.scene)}
            </span>
            <span
              className={`runtime-chip runtime-chip-${laneChipTone(runtimeStatus.laneStates.world)}`}
            >
              {formatLaneChipLabel("World", runtimeStatus.laneStates.world)}
            </span>
            <span
              className={`runtime-chip runtime-chip-${laneChipTone(runtimeStatus.laneStates.player)}`}
            >
              {formatLaneChipLabel("Player", runtimeStatus.laneStates.player)}
            </span>
            <span
              className={`runtime-chip runtime-chip-${budgetChipTone(runtimeStatus.budget.health)}`}
            >
              {runtimeStatus.budget.label}
            </span>
          </div>
        ) : null}
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

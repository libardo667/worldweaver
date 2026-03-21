import type { ReactNode, RefObject } from "react";

import { MagicFingerLoader } from "./MagicFingerLoader";

type TurnRecord = {
  id: string;
  ts: string;
  action: string;
  ackLine: string | null;
  narrative: string;
  location: string | null;
};

type AgentFeedItem = {
  ts: string;
  displayName: string;
  agentAction: string | null;
  narrative: string | null;
};

type WorldActionPaneProps = {
  isMobile: boolean;
  isInfoPaneCollapsed: boolean;
  leftWidth: number;
  showingEntryScreen: boolean;
  entryScreen: ReactNode;
  observerMode: boolean;
  mentorBoardMode: boolean;
  turns: TurnRecord[];
  agentFeed: AgentFeedItem[];
  draftNarrative: string;
  draftAckLine: string;
  pending: boolean;
  narrativeEndRef: RefObject<HTMLDivElement | null>;
  authRecoveryMessage: string | null;
  startupRecoveryMessage: string | null;
  observerModeRequired: boolean;
  observerModeDetail: string;
  onRetrySync: () => void;
  onRestartArrival: () => void;
  onOpenSettings: () => void;
  onRefreshStatus: () => void;
  actionText: string;
  actionPlaceholder: string;
  actionComposerDisabled: boolean;
  onActionTextChange: (value: string) => void;
  onActionKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSendAction: () => void;
};

export function WorldActionPane({
  isMobile,
  isInfoPaneCollapsed,
  leftWidth,
  showingEntryScreen,
  entryScreen,
  observerMode,
  mentorBoardMode,
  turns,
  agentFeed,
  draftNarrative,
  draftAckLine,
  pending,
  narrativeEndRef,
  authRecoveryMessage,
  startupRecoveryMessage,
  observerModeRequired,
  observerModeDetail,
  onRetrySync,
  onRestartArrival,
  onOpenSettings,
  onRefreshStatus,
  actionText,
  actionPlaceholder,
  actionComposerDisabled,
  onActionTextChange,
  onActionKeyDown,
  onSendAction,
}: WorldActionPaneProps) {
  return (
    <div
      className={`ww-action-col${isMobile ? " ww-action-col--mobile" : " ww-action-col--desktop"}`}
      style={
        isMobile
          ? undefined
          : {
              width: isInfoPaneCollapsed ? "calc(100% - 32px)" : `${leftWidth}%`,
            }
      }
    >
      <div className="ww-narrative-scroll" style={{ flex: 1, overflowY: "auto", padding: "1rem" }}>
        {showingEntryScreen && entryScreen}
        {observerMode && !showingEntryScreen && turns.length === 0 && !draftNarrative && !draftAckLine && (
          <div className="ww-turn ww-turn--agent">
            <div className="ww-turn-agent-name">{mentorBoardMode ? "Mentor Board" : "Observer Mode"}</div>
            <div className="ww-turn-narrative">
              {mentorBoardMode
                ? "You are moving through the shard under mentor access. Map movement changes your local view; quest tools live in the Guild tab."
                : "You are moving through the shard as a read-only witness. Map movement changes your point of view locally, but does not write to the world."}
            </div>
          </div>
        )}
        {[
          ...turns.map((t) => ({ kind: "turn" as const, ts: t.ts, data: t })),
          ...agentFeed.map((a) => ({ kind: "agent" as const, ts: a.ts, data: a })),
        ]
          .sort((a, b) => a.ts.localeCompare(b.ts))
          .map((item) =>
            item.kind === "turn" ? (
              <div key={item.data.id} className="ww-turn">
                <div className="ww-turn-action">&gt; {item.data.action}</div>
                {item.data.ackLine && <div className="ww-turn-ack">{item.data.ackLine}</div>}
                <div className="ww-turn-narrative">{item.data.narrative}</div>
                {item.data.location && (
                  <div className="ww-turn-location">
                    {item.data.location.replace(/_/g, " ")}
                  </div>
                )}
              </div>
            ) : (
              <div key={`${item.data.ts}-${item.data.displayName}`} className="ww-turn ww-turn--agent">
                <div className="ww-turn-agent-name">{item.data.displayName}</div>
                <div className="ww-turn-narrative">{item.data.narrative ?? item.data.agentAction}</div>
              </div>
            ),
          )}
        {(draftNarrative || pending) && (
          <div className="ww-turn ww-turn--draft">
            {draftNarrative ? <div>{draftNarrative}</div> : <span className="ww-typing"><MagicFingerLoader size={40} /></span>}
          </div>
        )}
        <div ref={narrativeEndRef as RefObject<HTMLDivElement>} />
      </div>

      {(authRecoveryMessage || startupRecoveryMessage || observerModeRequired) && (
        <div className="ww-recovery-strip-stack">
          {authRecoveryMessage && (
            <section className="ww-recovery-strip ww-recovery-strip--warn">
              <div className="ww-recovery-strip-copy">
                <p className="ww-recovery-strip-title">Signed out on this shard</p>
                <p className="ww-recovery-strip-text">{authRecoveryMessage}</p>
              </div>
              <div className="ww-recovery-strip-actions">
                <button className="ww-recovery-strip-btn" onClick={onRestartArrival}>
                  Restart arrival
                </button>
              </div>
            </section>
          )}
          {startupRecoveryMessage && (
            <section className="ww-recovery-strip ww-recovery-strip--error">
              <div className="ww-recovery-strip-copy">
                <p className="ww-recovery-strip-title">Shard state needs recovery</p>
                <p className="ww-recovery-strip-text">{startupRecoveryMessage}</p>
              </div>
              <div className="ww-recovery-strip-actions">
                <button className="ww-recovery-strip-btn" onClick={onRetrySync}>
                  Retry sync
                </button>
                <button className="ww-recovery-strip-btn" onClick={onRestartArrival}>
                  Restart arrival
                </button>
              </div>
            </section>
          )}
          {observerModeRequired && (
            <section className="ww-recovery-strip ww-recovery-strip--info">
              <div className="ww-recovery-strip-copy">
                <p className="ww-recovery-strip-title">Observer mode</p>
                <p className="ww-recovery-strip-text">
                  {observerModeDetail || "Add your own API key to continue acting on this shard."}
                </p>
              </div>
              <div className="ww-recovery-strip-actions">
                <button className="ww-recovery-strip-btn" onClick={onOpenSettings}>
                  Open settings
                </button>
                <button className="ww-recovery-strip-btn" onClick={onRefreshStatus}>
                  Refresh status
                </button>
              </div>
            </section>
          )}
        </div>
      )}

      <div className="ww-input-row">
        <textarea
          className="ww-action-input"
          placeholder={actionPlaceholder}
          rows={2}
          value={actionText}
          onChange={(e) => onActionTextChange(e.target.value)}
          onKeyDown={onActionKeyDown}
          disabled={actionComposerDisabled}
          autoFocus={!isMobile}
        />
        <button
          className="ww-send-btn"
          onClick={onSendAction}
          disabled={actionComposerDisabled || !actionText.trim()}
        >
          {pending ? <MagicFingerLoader size={20} /> : "→"}
        </button>
      </div>
    </div>
  );
}

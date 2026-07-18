// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { ReactNode, RefObject } from "react";

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
  turns: TurnRecord[];
  agentFeed: AgentFeedItem[];
  narrativeEndRef: RefObject<HTMLDivElement | null>;
  authRecoveryMessage: string | null;
  startupRecoveryMessage: string | null;
  onRetrySync: () => void;
  onRestartArrival: () => void;
};

export function WorldActionPane({
  isMobile,
  isInfoPaneCollapsed,
  leftWidth,
  showingEntryScreen,
  entryScreen,
  observerMode,
  turns,
  agentFeed,
  narrativeEndRef,
  authRecoveryMessage,
  startupRecoveryMessage,
  onRetrySync,
  onRestartArrival,
}: WorldActionPaneProps) {
  return (
    <div
      className={`ww-action-col${isMobile ? " ww-action-col--mobile" : " ww-action-col--desktop"}`}
      style={
        isMobile
          ? undefined
          : {
              width: isInfoPaneCollapsed ? "calc(100% - 32px)" : `${leftWidth}%`,
              flex: isInfoPaneCollapsed ? "1 1 auto" : `0 0 ${leftWidth}%`,
            }
      }
    >
      <div className="ww-narrative-scroll" style={{ flex: 1, overflowY: "auto", padding: "1rem" }}>
        {showingEntryScreen && entryScreen}
        {observerMode && !showingEntryScreen && turns.length === 0 && (
          <div className="ww-turn ww-turn--agent">
            <div className="ww-turn-agent-name">Observer Mode</div>
            <div className="ww-turn-narrative">
              You are moving through the shard as a read-only witness. Map movement changes your point of view locally, but does not write to the world.
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
        <div ref={narrativeEndRef as RefObject<HTMLDivElement>} />
      </div>

      {(authRecoveryMessage || startupRecoveryMessage) && (
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
        </div>
      )}
    </div>
  );
}

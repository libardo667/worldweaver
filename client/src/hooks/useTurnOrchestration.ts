import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
} from "react";

import {
  getStateSummary,
  postAction,
  postNext,
  postSpatialMove,
  streamAction,
} from "../api/wwClient";
import {
  BLOCKED_MOVE_DETAIL,
  BLOCKED_MOVE_TOAST_COOLDOWN_MS,
  buildChoiceTakenDelta,
  extractPreferenceVars,
  getErrorDetail,
  mergePreferenceVars,
  normalizeVars,
  toNextPayloadVars,
} from "../app/appHelpers";
import {
  getNarratorLaneAdapter,
  getSceneLaneDefaultNotice,
  type NarratorLane,
  type NarratorTurnOperation,
  type V3NarratorHooks,
} from "../app/v3NarratorStubs";
import type {
  ChangeItem,
  Choice,
  ToastItem,
  TurnPhase,
  VarsRecord,
} from "../types";
import { buildWhatChangedReceipts } from "../utils/diffVars";

type TurnPendingSetter = (value: boolean) => void;

type UseTurnOrchestrationArgs = {
  sessionId: string;
  vars: VarsRecord;
  historyLimit: number;
  enableAssistiveSpatial: boolean;
  isStaleSession: (requestSessionId: string) => boolean;
  persistVars: (nextVars: VarsRecord) => void;
  pushToast: (title: string, detail?: string, kind?: ToastItem["kind"]) => void;
  setSceneText: Dispatch<SetStateAction<string>>;
  setChoices: Dispatch<SetStateAction<Choice[]>>;
  setTurnPhase: Dispatch<SetStateAction<TurnPhase>>;
  setDraftSceneText: Dispatch<SetStateAction<string>>;
  setChanges: Dispatch<SetStateAction<ChangeItem[]>>;
  setPendingScene: Dispatch<SetStateAction<boolean>>;
  setPendingAction: Dispatch<SetStateAction<boolean>>;
  setPendingMove: Dispatch<SetStateAction<boolean>>;
  beginTurnOperation: (args: {
    notice: string;
    phase: TurnPhase;
    setPending: TurnPendingSetter;
  }) => void;
  finishTurnOperation: (setPending: TurnPendingSetter) => void;
  refreshMemory: (limit?: number, requestSessionId?: string) => Promise<void>;
  scheduleBestEffortPlaceRefresh: (requestSessionId?: string) => void;
  actionStreamAbortRef: MutableRefObject<AbortController | null>;
  lastBlockedMoveToastAtRef: MutableRefObject<number>;
  narratorHooks?: V3NarratorHooks;
};

type UseTurnOrchestrationResult = {
  refreshPostTurnContext: (requestSessionId?: string) => Promise<void>;
  fetchScene: (
    requestSessionId: string,
    initialVars: VarsRecord,
    omitLocation?: boolean,
  ) => Promise<void>;
  handleChoice: (choice: Choice) => Promise<void>;
  handleAction: (actionText: string, inputVars?: VarsRecord) => Promise<void>;
  handleMove: (direction: string) => Promise<void>;
};

const ACTIVE_NARRATOR_LANES: NarratorLane[] = ["scene", "world", "player"];

function resolveSceneLaneNotice(
  narratorHooks: V3NarratorHooks | undefined,
  operation: NarratorTurnOperation,
  context: {
    sessionId: string;
    vars: VarsRecord;
    actionText?: string;
    choiceLabel?: string;
    direction?: string;
  },
): string {
  const sceneLaneAdapter = getNarratorLaneAdapter(narratorHooks, "scene");
  const fallbackNotice = getSceneLaneDefaultNotice(operation);
  const customNotice = sceneLaneAdapter.beforeTurn?.({
    lane: "scene",
    operation,
    sessionId: context.sessionId,
    vars: context.vars,
    actionText: context.actionText,
    choiceLabel: context.choiceLabel,
    direction: context.direction,
  });
  if (!customNotice) {
    return fallbackNotice;
  }
  const trimmed = customNotice.trim();
  return trimmed || fallbackNotice;
}

function emitLaneTurnResult(args: {
  narratorHooks: V3NarratorHooks | undefined;
  operation: NarratorTurnOperation;
  sessionId: string;
  ok: boolean;
  nextVars?: VarsRecord;
  choices?: Choice[];
}) {
  for (const lane of ACTIVE_NARRATOR_LANES) {
    const laneAdapter = getNarratorLaneAdapter(args.narratorHooks, lane);
    laneAdapter.afterTurn?.({
      lane,
      operation: args.operation,
      sessionId: args.sessionId,
      ok: args.ok,
      nextVars: args.nextVars,
      choices: args.choices,
    });
  }
}

export function useTurnOrchestration({
  sessionId,
  vars,
  historyLimit,
  enableAssistiveSpatial,
  isStaleSession,
  persistVars,
  pushToast,
  setSceneText,
  setChoices,
  setTurnPhase,
  setDraftSceneText,
  setChanges,
  setPendingScene,
  setPendingAction,
  setPendingMove,
  beginTurnOperation,
  finishTurnOperation,
  refreshMemory,
  scheduleBestEffortPlaceRefresh,
  actionStreamAbortRef,
  lastBlockedMoveToastAtRef,
  narratorHooks,
}: UseTurnOrchestrationArgs): UseTurnOrchestrationResult {
  const refreshPostTurnContext = useCallback(async (requestSessionId = sessionId) => {
    await refreshMemory(historyLimit, requestSessionId);
    if (enableAssistiveSpatial) {
      scheduleBestEffortPlaceRefresh(requestSessionId);
    }
  }, [enableAssistiveSpatial, historyLimit, refreshMemory, scheduleBestEffortPlaceRefresh, sessionId]);

  const fetchScene = useCallback(async (
    requestSessionId: string,
    initialVars: VarsRecord,
    omitLocation = false,
  ) => {
    const scene = await postNext(
      requestSessionId,
      toNextPayloadVars(initialVars, omitLocation),
    );
    if (isStaleSession(requestSessionId)) {
      return;
    }
    setSceneText(scene.text);
    setChoices(scene.choices ?? []);
    persistVars(mergePreferenceVars(normalizeVars(scene.vars), initialVars));
  }, [isStaleSession, persistVars, setChoices, setSceneText]);

  const handleChoice = useCallback(async (choice: Choice) => {
    const requestSessionId = sessionId;
    const previousVars = vars;
    beginTurnOperation({
      notice: resolveSceneLaneNotice(narratorHooks, "choice", {
        sessionId: requestSessionId,
        vars: previousVars,
        choiceLabel: choice.label,
      }),
      phase: "confirming",
      setPending: setPendingScene,
    });
    try {
      const intentDelta = buildChoiceTakenDelta(normalizeVars(choice.set));
      const scene = await postNext(requestSessionId, toNextPayloadVars(previousVars), intentDelta);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(scene.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(scene.text);
      setChoices(scene.choices ?? []);
      persistVars(nextVars);

      setChanges(
        buildWhatChangedReceipts({
          eventLabel: `Choice: ${choice.label}`,
          previousVars,
          nextVars,
          choiceSet: normalizeVars(choice.set),
        }),
      );
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
      emitLaneTurnResult({
        narratorHooks,
        operation: "choice",
        sessionId: requestSessionId,
        ok: true,
        nextVars,
        choices: scene.choices ?? [],
      });
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Choice failed to resolve.", String(error));
      emitLaneTurnResult({
        narratorHooks,
        operation: "choice",
        sessionId: requestSessionId,
        ok: false,
      });
    } finally {
      if (!isStaleSession(requestSessionId)) {
        finishTurnOperation(setPendingScene);
      }
    }
  }, [
    beginTurnOperation,
    finishTurnOperation,
    isStaleSession,
    narratorHooks,
    persistVars,
    pushToast,
    refreshPostTurnContext,
    sessionId,
    setChanges,
    setChoices,
    setPendingScene,
    setSceneText,
    setTurnPhase,
    vars,
  ]);

  const handleAction = useCallback(async (actionText: string, inputVars?: VarsRecord) => {
    const requestSessionId = sessionId;
    const previousVars = inputVars ?? vars;
    beginTurnOperation({
      notice: resolveSceneLaneNotice(narratorHooks, "action", {
        sessionId: requestSessionId,
        vars: previousVars,
        actionText,
      }),
      phase: "interpreting",
      setPending: setPendingAction,
    });
    const actionPreferenceVars = extractPreferenceVars(previousVars);
    actionStreamAbortRef.current?.abort();
    const controller = new AbortController();
    actionStreamAbortRef.current = controller;
    try {
      let result;
      let receivedDraft = false;
      try {
        result = await streamAction(
          requestSessionId,
          actionText,
          actionPreferenceVars,
          (draftText) => {
            receivedDraft = true;
            if (!isStaleSession(requestSessionId)) {
              setTurnPhase("rendering");
              setDraftSceneText(draftText);
            }
          },
          controller.signal,
        );
      } catch (streamError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!receivedDraft) {
          setTurnPhase("confirming");
          result = await postAction(requestSessionId, actionText, actionPreferenceVars);
        } else {
          throw streamError;
        }
      }
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(result.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(
        result.triggered_storylet
          ? `${result.narrative}\n\n${result.triggered_storylet}`
          : result.narrative,
      );
      setDraftSceneText("");
      setChoices(result.choices ?? []);
      persistVars(nextVars);

      setChanges(
        buildWhatChangedReceipts({
          eventLabel: `Action: ${actionText}`,
          previousVars,
          nextVars,
          stateChanges: normalizeVars(result.state_changes),
        }),
      );
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
      emitLaneTurnResult({
        narratorHooks,
        operation: "action",
        sessionId: requestSessionId,
        ok: true,
        nextVars,
        choices: result.choices ?? [],
      });
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("Your action lost coherence.", String(error));
      emitLaneTurnResult({
        narratorHooks,
        operation: "action",
        sessionId: requestSessionId,
        ok: false,
      });
    } finally {
      if (actionStreamAbortRef.current === controller) {
        actionStreamAbortRef.current = null;
      }
      if (!isStaleSession(requestSessionId)) {
        finishTurnOperation(setPendingAction);
      }
    }
  }, [
    actionStreamAbortRef,
    beginTurnOperation,
    finishTurnOperation,
    isStaleSession,
    narratorHooks,
    persistVars,
    pushToast,
    refreshPostTurnContext,
    sessionId,
    setChanges,
    setChoices,
    setDraftSceneText,
    setPendingAction,
    setSceneText,
    setTurnPhase,
    vars,
  ]);

  const handleMove = useCallback(async (direction: string) => {
    const requestSessionId = sessionId;
    const previousVars = vars;
    beginTurnOperation({
      notice: resolveSceneLaneNotice(narratorHooks, "move", {
        sessionId: requestSessionId,
        vars: previousVars,
        direction,
      }),
      phase: "confirming",
      setPending: setPendingMove,
    });
    try {
      const movement = await postSpatialMove(requestSessionId, direction);
      const summary = await getStateSummary(requestSessionId);
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const serverVars = normalizeVars(summary.variables);
      const mergedRequestVars = mergePreferenceVars(serverVars, previousVars);
      const nextScene = await postNext(
        requestSessionId,
        toNextPayloadVars(mergedRequestVars, false),
      );
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const nextVars = mergePreferenceVars(normalizeVars(nextScene.vars), previousVars);

      setTurnPhase("rendering");
      setSceneText(nextScene.text);
      setChoices(nextScene.choices ?? []);
      persistVars(nextVars);
      setChanges(
        buildWhatChangedReceipts({
          eventLabel: movement.result,
          previousVars,
          nextVars,
        }),
      );
      lastBlockedMoveToastAtRef.current = 0;
      setTurnPhase("weaving_ahead");
      await refreshPostTurnContext(requestSessionId);
      emitLaneTurnResult({
        narratorHooks,
        operation: "move",
        sessionId: requestSessionId,
        ok: true,
        nextVars,
        choices: nextScene.choices ?? [],
      });
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      const detail = getErrorDetail(error);
      if (detail === BLOCKED_MOVE_DETAIL) {
        const now = Date.now();
        if (now - lastBlockedMoveToastAtRef.current >= BLOCKED_MOVE_TOAST_COOLDOWN_MS) {
          lastBlockedMoveToastAtRef.current = now;
          pushToast(
            "Movement blocked.",
            "That route is currently impassable. Try a different direction.",
            "info",
          );
        }
        scheduleBestEffortPlaceRefresh(requestSessionId);
        return;
      }
      pushToast("Movement failed.", detail);
      emitLaneTurnResult({
        narratorHooks,
        operation: "move",
        sessionId: requestSessionId,
        ok: false,
      });
    } finally {
      if (!isStaleSession(requestSessionId)) {
        finishTurnOperation(setPendingMove);
      }
    }
  }, [
    beginTurnOperation,
    finishTurnOperation,
    isStaleSession,
    lastBlockedMoveToastAtRef,
    narratorHooks,
    persistVars,
    pushToast,
    refreshPostTurnContext,
    scheduleBestEffortPlaceRefresh,
    sessionId,
    setChanges,
    setChoices,
    setPendingMove,
    setSceneText,
    setTurnPhase,
    vars,
  ]);

  return {
    refreshPostTurnContext,
    fetchScene,
    handleChoice,
    handleAction,
    handleMove,
  };
}

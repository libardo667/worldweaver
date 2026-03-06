import { type MutableRefObject, useCallback } from "react";

import {
  postDevHardReset,
  postResetSession,
  postSessionBootstrap,
} from "../api/wwClient";
import {
  buildPromptVars,
  CHARACTER_PROFILE_KEY,
  extractPreferenceVars,
  makeId,
  normalizeVars,
  PLAYER_ROLE_KEY,
  WORLD_THEME_KEY,
} from "../app/appHelpers";
import {
  clearSessionStorage,
  replaceSessionId,
  setOnboardedSessionId,
} from "../state/sessionStore";
import type { TurnPhase, ToastItem, VarsRecord } from "../types";

type TurnPendingSetter = (value: boolean) => void;

type UseSessionLifecycleArgs = {
  sessionId: string;
  vars: VarsRecord;
  worldThemeInput: string;
  characterInput: string;
  noticeFirstInput: string;
  oneHopeInput: string;
  oneFearInput: string;
  vibeLensInput: string;
  beginTurnOperation: (args: {
    notice: string;
    phase: TurnPhase;
    setPending: TurnPendingSetter;
  }) => void;
  finishTurnOperation: (setPending: TurnPendingSetter) => void;
  setPendingScene: TurnPendingSetter;
  isStaleSession: (requestSessionId: string) => boolean;
  persistVars: (nextVars: VarsRecord) => void;
  setLongTurnVibe: (value: string) => void;
  setNeedsOnboarding: (value: boolean) => void;
  setSceneText: (value: string) => void;
  setTurnPhase: (value: TurnPhase) => void;
  setChanges: (value: Array<{ id: string; text: string }>) => void;
  setBootstrapNonce: (updater: (value: number) => number) => void;
  triggerPrefetch: (reason: string) => Promise<void>;
  pushToast: (title: string, detail?: string, kind?: ToastItem["kind"]) => void;
  actionStreamAbortRef: MutableRefObject<AbortController | null>;
  bootstrappedSceneKeyRef: MutableRefObject<string>;
  applyReplacementSessionState: (args: {
    replacementSessionId: string;
    nextSceneText: string;
    changeText: string;
  }) => void;
  refreshReadiness: () => Promise<void>;
};

type UseSessionLifecycleResult = {
  handleOnboardingSubmit: () => Promise<void>;
  handleResetSession: () => Promise<void>;
  handleDevHardReset: () => Promise<void>;
};

function clearWorldweaverLocalStoragePrefix(): void {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith("ww.")) {
      keys.push(key);
    }
  }
  for (const key of keys) {
    localStorage.removeItem(key);
  }
}

export function useSessionLifecycle({
  sessionId,
  vars,
  worldThemeInput,
  characterInput,
  noticeFirstInput,
  oneHopeInput,
  oneFearInput,
  vibeLensInput,
  beginTurnOperation,
  finishTurnOperation,
  setPendingScene,
  isStaleSession,
  persistVars,
  setLongTurnVibe,
  setNeedsOnboarding,
  setSceneText,
  setTurnPhase,
  setChanges,
  setBootstrapNonce,
  triggerPrefetch,
  pushToast,
  actionStreamAbortRef,
  bootstrappedSceneKeyRef,
  applyReplacementSessionState,
  refreshReadiness,
}: UseSessionLifecycleArgs): UseSessionLifecycleResult {
  const resetTurnRuntimeContext = useCallback(() => {
    actionStreamAbortRef.current?.abort();
    actionStreamAbortRef.current = null;
    bootstrappedSceneKeyRef.current = "";
  }, [actionStreamAbortRef, bootstrappedSceneKeyRef]);

  const invalidateProjectionCaches = useCallback(
    (scope: "thread" | "world") => {
      clearSessionStorage();
      if (scope === "world") {
        clearWorldweaverLocalStoragePrefix();
      }
    },
    [],
  );

  const handleResetSession = useCallback(async () => {
    beginTurnOperation({
      notice: "Resetting world state and clearing session context...",
      phase: "confirming",
      setPending: setPendingScene,
    });
    try {
      resetTurnRuntimeContext();
      const resetResult = await postResetSession();
      invalidateProjectionCaches("thread");
      const replacement = replaceSessionId();
      applyReplacementSessionState({
        replacementSessionId: replacement,
        nextSceneText: "A new thread begins.",
        changeText: "Session reset and rethreaded.",
      });
      pushToast(
        "Session reset.",
        resetResult.legacy_seed_mode
          ? `World cleared. Legacy seed mode inserted ${resetResult.storylets_seeded} storylets.`
          : "World cleared. Onboarding is required before the first scene.",
        "info",
      );
    } catch (error) {
      pushToast("Session reset failed.", String(error));
    } finally {
      finishTurnOperation(setPendingScene);
    }
  }, [
    applyReplacementSessionState,
    beginTurnOperation,
    finishTurnOperation,
    invalidateProjectionCaches,
    pushToast,
    resetTurnRuntimeContext,
    setPendingScene,
  ]);

  const handleDevHardReset = useCallback(async () => {
    if (
      !window.confirm(
        "Hard reset will wipe all world data and clear local WorldWeaver storage. Continue?",
      )
    ) {
      return;
    }

    beginTurnOperation({
      notice: "Running developer hard reset and rebuilding a clean thread...",
      phase: "confirming",
      setPending: setPendingScene,
    });
    try {
      resetTurnRuntimeContext();
      const resetResult = await postDevHardReset();
      invalidateProjectionCaches("world");
      const replacement = replaceSessionId();
      applyReplacementSessionState({
        replacementSessionId: replacement,
        nextSceneText: "Development hard reset complete.",
        changeText: "Developer hard reset wiped backend world + local state.",
      });
      await refreshReadiness();
      pushToast("Dev hard reset complete.", resetResult.message, "info");
    } catch (error) {
      pushToast("Dev hard reset failed.", String(error));
    } finally {
      finishTurnOperation(setPendingScene);
    }
  }, [
    applyReplacementSessionState,
    beginTurnOperation,
    finishTurnOperation,
    invalidateProjectionCaches,
    pushToast,
    refreshReadiness,
    resetTurnRuntimeContext,
    setPendingScene,
  ]);

  const handleOnboardingSubmit = useCallback(async () => {
    const theme = worldThemeInput.trim();
    const character = characterInput.trim();
    if (!theme || !character) {
      pushToast(
        "Setup incomplete.",
        "Please answer both onboarding questions before starting.",
      );
      return;
    }

    const requestSessionId = sessionId;
    beginTurnOperation({
      notice: "Generating your world and preparing the opening storylets...",
      phase: "confirming",
      setPending: setPendingScene,
    });
    try {
      const bootstrap = await postSessionBootstrap(requestSessionId, {
        world_theme: theme,
        player_role: character,
        description: `A player-authored world focused on ${theme}.`,
        bootstrap_source: "onboarding",
      });
      if (isStaleSession(requestSessionId)) {
        return;
      }

      const promptVars = buildPromptVars({
        noticeFirst: noticeFirstInput,
        oneHope: oneHopeInput,
        oneFear: oneFearInput,
        vibeLens: vibeLensInput,
      });
      const seededVars: VarsRecord = {
        ...normalizeVars(bootstrap.vars),
        ...extractPreferenceVars(vars),
        ...promptVars,
        [WORLD_THEME_KEY]: theme,
        [PLAYER_ROLE_KEY]: character,
        [CHARACTER_PROFILE_KEY]: character,
      };
      persistVars(seededVars);
      setLongTurnVibe(vibeLensInput.trim());
      setOnboardedSessionId(requestSessionId);
      setNeedsOnboarding(false);
      setSceneText("Weaving your world setup into the first scene...");
      setTurnPhase("weaving_ahead");
      setChanges([
        {
          id: makeId("evt"),
          text: `World setup: ${theme} | Character: ${character}`,
        },
      ]);
      setBootstrapNonce((value) => value + 1);
      void triggerPrefetch("onboarding-prompts");
      pushToast(
        "Setup captured.",
        `Generated ${bootstrap.storylets_created} opening storylets for this world.`,
        "info",
      );
    } catch (error) {
      if (isStaleSession(requestSessionId)) {
        return;
      }
      pushToast("World bootstrap failed.", String(error));
    } finally {
      if (!isStaleSession(requestSessionId)) {
        finishTurnOperation(setPendingScene);
      }
    }
  }, [
    beginTurnOperation,
    characterInput,
    finishTurnOperation,
    isStaleSession,
    noticeFirstInput,
    oneFearInput,
    oneHopeInput,
    persistVars,
    pushToast,
    sessionId,
    setBootstrapNonce,
    setChanges,
    setLongTurnVibe,
    setNeedsOnboarding,
    setPendingScene,
    setSceneText,
    setTurnPhase,
    triggerPrefetch,
    vars,
    vibeLensInput,
    worldThemeInput,
  ]);

  return {
    handleOnboardingSubmit,
    handleResetSession,
    handleDevHardReset,
  };
}

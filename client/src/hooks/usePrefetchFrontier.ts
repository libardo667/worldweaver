import { useCallback, useEffect, useRef, useState } from "react";

import { getPrefetchStatus, postPrefetchFrontier } from "../api/wwClient";
import type { PrefetchStatusResponse } from "../types";

type UsePrefetchFrontierOptions = {
  sessionId: string;
  enabled: boolean;
  sceneDebounceMs?: number;
  typingIdleMs?: number;
  onSoftError?: (detail: string) => void;
};

const EMPTY_STATUS: PrefetchStatusResponse = {
  stubs_cached: 0,
  expires_in_seconds: 0,
};

function normalizeStatus(value: unknown): PrefetchStatusResponse {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return EMPTY_STATUS;
  }
  const payload = value as Partial<PrefetchStatusResponse>;
  return {
    stubs_cached: Math.max(0, Number(payload.stubs_cached ?? 0) || 0),
    expires_in_seconds: Math.max(0, Number(payload.expires_in_seconds ?? 0) || 0),
  };
}

export function usePrefetchFrontier({
  sessionId,
  enabled,
  sceneDebounceMs = 850,
  typingIdleMs = 1200,
  onSoftError,
}: UsePrefetchFrontierOptions) {
  const [prefetchStatus, setPrefetchStatus] = useState<PrefetchStatusResponse>(
    EMPTY_STATUS,
  );
  const sceneTimerRef = useRef<number | null>(null);
  const typingTimerRef = useRef<number | null>(null);
  const requestVersionRef = useRef(0);
  const requestInFlightRef = useRef(false);
  const lastSoftErrorAtRef = useRef(0);

  const emitSoftError = useCallback(
    (detail: string) => {
      const now = Date.now();
      if (now - lastSoftErrorAtRef.current < 15000) {
        return;
      }
      lastSoftErrorAtRef.current = now;
      onSoftError?.(detail);
    },
    [onSoftError],
  );

  const clearTimers = useCallback(() => {
    if (sceneTimerRef.current !== null) {
      window.clearTimeout(sceneTimerRef.current);
      sceneTimerRef.current = null;
    }
    if (typingTimerRef.current !== null) {
      window.clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }
  }, []);

  const refreshPrefetchStatus = useCallback(async () => {
    if (!enabled || !sessionId) {
      return;
    }
    const requestVersion = ++requestVersionRef.current;
    try {
      const status = await getPrefetchStatus(sessionId);
      if (requestVersion !== requestVersionRef.current) {
        return;
      }
      setPrefetchStatus(normalizeStatus(status));
    } catch {
      emitSoftError("Background frontier status is currently unavailable.");
    }
  }, [enabled, emitSoftError, sessionId]);

  const triggerPrefetch = useCallback(
    async (reason: string) => {
      if (!enabled || !sessionId || requestInFlightRef.current) {
        return;
      }
      requestInFlightRef.current = true;
      try {
        await postPrefetchFrontier(sessionId);
        await refreshPrefetchStatus();
      } catch {
        emitSoftError(`Background weaving paused (${reason}).`);
      } finally {
        requestInFlightRef.current = false;
      }
    },
    [enabled, emitSoftError, refreshPrefetchStatus, sessionId],
  );

  const scheduleScenePrefetch = useCallback(
    (delayMs = sceneDebounceMs) => {
      if (!enabled || !sessionId) {
        return;
      }
      if (sceneTimerRef.current !== null) {
        window.clearTimeout(sceneTimerRef.current);
      }
      sceneTimerRef.current = window.setTimeout(() => {
        sceneTimerRef.current = null;
        void triggerPrefetch("scene-idle");
      }, Math.max(150, delayMs));
    },
    [enabled, sceneDebounceMs, sessionId, triggerPrefetch],
  );

  const notifyTypingActivity = useCallback(() => {
    if (!enabled || !sessionId) {
      return;
    }
    if (typingTimerRef.current !== null) {
      window.clearTimeout(typingTimerRef.current);
    }
    typingTimerRef.current = window.setTimeout(() => {
      typingTimerRef.current = null;
      void triggerPrefetch("typing-idle");
    }, Math.max(250, typingIdleMs));
  }, [enabled, sessionId, triggerPrefetch, typingIdleMs]);

  useEffect(() => {
    clearTimers();
    requestVersionRef.current += 1;
    requestInFlightRef.current = false;
    if (!enabled || !sessionId) {
      setPrefetchStatus(EMPTY_STATUS);
      return () => {
        clearTimers();
      };
    }
    void refreshPrefetchStatus();
    return () => {
      clearTimers();
    };
  }, [clearTimers, enabled, refreshPrefetchStatus, sessionId]);

  return {
    prefetchStatus,
    notifyTypingActivity,
    refreshPrefetchStatus,
    scheduleScenePrefetch,
    triggerPrefetch,
  };
}


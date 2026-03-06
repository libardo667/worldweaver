import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getPrefetchStatus, postPrefetchFrontier } from "../api/wwClient";
import {
  clearPrefetchBudgetCache,
  loadPrefetchBudgetCache,
  loadPrefetchStatusCache,
  savePrefetchBudgetCache,
  savePrefetchStatusCache,
  type PrefetchCacheScope,
} from "../state/sessionStore";
import type {
  PrefetchBudgetMetadata,
  PrefetchStatusResponse,
  ProjectionRef,
} from "../types";

type UsePrefetchFrontierOptions = {
  sessionId: string;
  enabled: boolean;
  projectionRef?: ProjectionRef | null;
  sceneDebounceMs?: number;
  typingIdleMs?: number;
  onSoftError?: (detail: string) => void;
};

const EMPTY_STATUS: PrefetchStatusResponse = {
  stubs_cached: 0,
  expires_in_seconds: 0,
};

type PrefetchStatusEnvelope = {
  status: PrefetchStatusResponse;
  budget: PrefetchBudgetMetadata | null;
};

function parseNonNegativeInteger(value: unknown): number | null {
  if (value === undefined || value === null) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.max(0, Math.floor(parsed));
}

function normalizeBudgetMetadata(value: unknown): PrefetchBudgetMetadata | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const nestedBudget =
    payload.budget && typeof payload.budget === "object" && !Array.isArray(payload.budget)
      ? (payload.budget as Record<string, unknown>)
      : null;

  const budgetMsRaw = nestedBudget?.budget_ms ?? payload.budget_ms;
  const maxNodesRaw = nestedBudget?.max_nodes ?? payload.max_nodes;
  const expansionDepthRaw = nestedBudget?.expansion_depth ?? payload.expansion_depth;
  const hasAnyBudgetField =
    budgetMsRaw !== undefined
    || maxNodesRaw !== undefined
    || expansionDepthRaw !== undefined;
  if (!hasAnyBudgetField) {
    return null;
  }
  return {
    budget_ms: parseNonNegativeInteger(budgetMsRaw) ?? 0,
    max_nodes: parseNonNegativeInteger(maxNodesRaw) ?? 0,
    expansion_depth: parseNonNegativeInteger(expansionDepthRaw) ?? 0,
  };
}

function normalizeStatusEnvelope(value: unknown): PrefetchStatusEnvelope {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { status: EMPTY_STATUS, budget: null };
  }
  const payload = value as Partial<PrefetchStatusResponse>;
  const budget = normalizeBudgetMetadata(value);
  const status: PrefetchStatusResponse = {
    stubs_cached: Math.max(0, Number(payload.stubs_cached ?? 0) || 0),
    expires_in_seconds: Math.max(0, Number(payload.expires_in_seconds ?? 0) || 0),
  };
  if (budget) {
    status.budget_ms = budget.budget_ms;
    status.max_nodes = budget.max_nodes;
    status.expansion_depth = budget.expansion_depth;
  }
  return { status, budget };
}

export function usePrefetchFrontier({
  sessionId,
  enabled,
  projectionRef = null,
  sceneDebounceMs = 850,
  typingIdleMs = 1200,
  onSoftError,
}: UsePrefetchFrontierOptions) {
  const [prefetchStatus, setPrefetchStatus] = useState<PrefetchStatusResponse>(
    EMPTY_STATUS,
  );
  const [prefetchBudget, setPrefetchBudget] = useState<PrefetchBudgetMetadata | null>(
    null,
  );
  const sceneTimerRef = useRef<number | null>(null);
  const typingTimerRef = useRef<number | null>(null);
  const requestVersionRef = useRef(0);
  const requestInFlightRef = useRef(false);
  const lastSoftErrorAtRef = useRef(0);

  const cacheScope = useMemo<PrefetchCacheScope>(
    () => ({
      sessionId,
      projectionRef,
    }),
    [
      sessionId,
      projectionRef?.projection_id,
      projectionRef?.canon_commit_id,
      projectionRef?.branch_id,
    ],
  );

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
      const envelope = normalizeStatusEnvelope(status);
      setPrefetchStatus(envelope.status);
      setPrefetchBudget(envelope.budget);
      savePrefetchStatusCache(cacheScope, envelope.status);
      if (envelope.budget) {
        savePrefetchBudgetCache(cacheScope, envelope.budget);
      } else {
        clearPrefetchBudgetCache(cacheScope);
      }
    } catch {
      emitSoftError("Background frontier status is currently unavailable.");
    }
  }, [cacheScope, enabled, emitSoftError, sessionId]);

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
      setPrefetchBudget(null);
      return () => {
        clearTimers();
      };
    }
    const cachedStatus = loadPrefetchStatusCache(cacheScope);
    const cachedBudget = loadPrefetchBudgetCache(cacheScope);
    setPrefetchStatus(cachedStatus ?? EMPTY_STATUS);
    setPrefetchBudget(cachedBudget);
    void refreshPrefetchStatus();
    return () => {
      clearTimers();
    };
  }, [cacheScope, clearTimers, enabled, refreshPrefetchStatus, sessionId]);

  return {
    prefetchStatus,
    prefetchBudget,
    notifyTypingActivity,
    refreshPrefetchStatus,
    scheduleScenePrefetch,
    triggerPrefetch,
  };
}


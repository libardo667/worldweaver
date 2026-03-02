import type {
  ActionResponse,
  NextResponse,
  SpatialMoveResponse,
  SpatialNavigationResponse,
  StateSummaryResponse,
  VarsRecord,
  WorldFactsResponse,
  WorldHistoryResponse,
} from "../types";

const API_BASE = (import.meta.env.VITE_WW_API_BASE as string | undefined) ?? "";

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function postNext(
  sessionId: string,
  vars: VarsRecord,
): Promise<NextResponse> {
  return requestJson<NextResponse>("/api/next", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      vars,
    }),
  });
}

export function postAction(
  sessionId: string,
  action: string,
): Promise<ActionResponse> {
  return requestJson<ActionResponse>("/api/action", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      action,
    }),
  });
}

export function getSpatialNavigation(
  sessionId: string,
): Promise<SpatialNavigationResponse> {
  return requestJson<SpatialNavigationResponse>(
    `/api/spatial/navigation/${encodeURIComponent(sessionId)}`,
  );
}

export function postSpatialMove(
  sessionId: string,
  direction: string,
): Promise<SpatialMoveResponse> {
  return requestJson<SpatialMoveResponse>(
    `/api/spatial/move/${encodeURIComponent(sessionId)}`,
    {
      method: "POST",
      body: JSON.stringify({ direction }),
    },
  );
}

export function getWorldHistory(
  sessionId: string,
  limit = 25,
): Promise<WorldHistoryResponse> {
  const params = new URLSearchParams({
    session_id: sessionId,
    limit: String(limit),
  });
  return requestJson<WorldHistoryResponse>(`/api/world/history?${params.toString()}`);
}

export function getWorldFacts(
  sessionId: string,
  query: string,
  limit = 12,
): Promise<WorldFactsResponse> {
  const params = new URLSearchParams({
    session_id: sessionId,
    query,
    limit: String(limit),
  });
  return requestJson<WorldFactsResponse>(`/api/world/facts?${params.toString()}`);
}

export function getStateSummary(sessionId: string): Promise<StateSummaryResponse> {
  return requestJson<StateSummaryResponse>(
    `/api/state/${encodeURIComponent(sessionId)}`,
  );
}

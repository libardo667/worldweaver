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

export function postResetSession(): Promise<{ success: boolean; message: string }> {
  return requestJson<{ success: boolean; message: string }>("/api/reset-session", {
    method: "POST",
  });
}

function parseSseBlock(
  block: string,
): { event: string; data: string } | null {
  const lines = block
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.length > 0);
  if (lines.length === 0) {
    return null;
  }

  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }
  return { event, data: dataLines.join("\n") };
}

export async function streamAction(
  sessionId: string,
  action: string,
  onDraftChunk?: (text: string) => void,
  signal?: AbortSignal,
): Promise<ActionResponse> {
  const response = await fetch(`${API_BASE}/api/action/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      session_id: sessionId,
      action,
    }),
    signal,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response body was not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload: ActionResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const raw = buffer.slice(0, sep).trim();
      buffer = buffer.slice(sep + 2);
      if (raw) {
        const parsed = parseSseBlock(raw);
        if (parsed) {
          if (parsed.event === "draft_chunk") {
            const payload = JSON.parse(parsed.data) as { text?: string };
            if (typeof payload.text === "string" && onDraftChunk) {
              onDraftChunk(payload.text);
            }
          } else if (parsed.event === "final") {
            finalPayload = JSON.parse(parsed.data) as ActionResponse;
          } else if (parsed.event === "error") {
            const payload = JSON.parse(parsed.data) as { detail?: string };
            throw new Error(payload.detail || "Action stream failed.");
          }
        }
      }
      sep = buffer.indexOf("\n\n");
    }
  }

  if (finalPayload) {
    return finalPayload;
  }
  throw new Error("Action stream ended before final payload.");
}

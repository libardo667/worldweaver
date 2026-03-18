import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getWorldDigest,
  getSettingsReadiness,
  getPlayerInbox,
  getPlayerThreads,
  markPlayerThreadRead,
  getLocationChat,
  postLocationChat,
  postMapMove,
  queryWorldMap,
  streamAction,
  getRestMetrics,
  getAuthMe,
  fetchShards,
  getApiBase,
  hasMixedContentApiBase,
  isApiRequestError,
  setApiBase,
  type WorldDigestResponse,
  type DigestRosterEntry,
  type DMThread,
  type InboxDM,
  type LocationChatEntry,
  type WorldMapQueryResponse,
  type RestMetricsResponse,
} from "./api/wwClient";
import {
  clearOnboardedSession,
  clearJwt,
  hasCompletedOnboarding,
  getJwt,
  getOnboardedSessionId,
  getOnboardedWorldId,
  getOrCreateSessionId,
  getPlayerInfo,
  replaceSessionId,
  setCompletedOnboarding,
  setJwt,
  setOnboardedSessionId,
  setOnboardedWorldId,
  setPlayerInfo,
  clearSelectedShardUrl,
  getSelectedShardUrl,
  setSelectedShardUrl,
  type PlayerInfo,
} from "./state/sessionStore";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SetupModal } from "./components/SetupModal";
import { ErrorToastStack } from "./components/ErrorToastStack";
import { EntryScreen } from "./components/EntryScreen";
import { LetterCompose } from "./components/LetterCompose";
import { LocationMap } from "./components/LocationMap";
import { MagicFingerLoader } from "./components/MagicFingerLoader";
import { OnboardingModal } from "./components/OnboardingModal";
import { PresencePanel } from "./components/PresencePanel";
import { RuntimeDiagnosticsBanner } from "./components/RuntimeDiagnosticsBanner";
import type { SettingsReadinessResponse, ShardInfo, ToastItem } from "./types";

type MapViewport = {
  north: number;
  south: number;
  east: number;
  west: number;
};

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function authRecoveryCopy(code?: string): string {
  switch (String(code || "").trim()) {
    case "legacy_auth_token":
      return "This saved login came from before shard-wide actor identity. Sign in again on this shard to keep acting as the same person.";
    case "invalid_auth_token":
      return "The saved login on this shard could not be read. Sign in again here if you want to keep acting as the same person.";
    case "actor_projection_unavailable":
      return "This shard could not recover your local account projection. Sign in again here to relink yourself.";
    default:
      return "The saved login on this shard is no longer valid. Sign in again here if you want to keep acting as the same person.";
  }
}

function _mentionVariants(raw: string): string[] {
  const base = String(raw || "").trim().toLowerCase();
  if (!base) return [];
  const collapsedSpace = base.replace(/\s+/g, " ").trim();
  const underscored = collapsedSpace.replace(/\s+/g, "_");
  const collapsed = collapsedSpace.replace(/\s+/g, "");
  const variants = new Set<string>([collapsedSpace, underscored, collapsed]);
  const first = collapsedSpace.split(" ", 1)[0]?.trim();
  if (first) variants.add(first);
  return [...variants].filter(Boolean);
}

function messageMentionsAnyName(message: string, names: Array<string | null | undefined>): boolean {
  const normalized = String(message || "").trim().toLowerCase();
  if (!normalized.includes("@")) return false;
  for (const name of names) {
    for (const variant of _mentionVariants(String(name || ""))) {
      if (variant && normalized.includes(`@${variant}`)) {
        return true;
      }
    }
  }
  return false;
}

type Turn = {
  id: string;
  ts: string;
  action: string;
  ackLine: string | null;
  narrative: string;
  location: string | null;
};

export default function App() {
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draftAckLine, setDraftAckLine] = useState<string>("");
  const [draftNarrative, setDraftNarrative] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [digest, setDigest] = useState<WorldDigestResponse | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsReadiness, setSettingsReadiness] = useState<SettingsReadinessResponse | null>(null);
  // Drawer/Map modals removed in favor of infoTabs
  const [playerInbox, setPlayerInbox] = useState<InboxDM[]>([]);
  const [playerThreads, setPlayerThreads] = useState<DMThread[]>([]);
  const [selectedThreadKey, setSelectedThreadKey] = useState<string | null>(null);
  const [agentFeed, setAgentFeed] = useState<Array<{ ts: string; displayName: string; agentAction: string | null; narrative: string | null }>>([]);
  const [chatMessages, setChatMessages] = useState<LocationChatEntry[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [chatPending, setChatPending] = useState(false);
  const [infoTab, setInfoTab] = useState<"map" | "presence" | "chats" | "notes">("chats");
  const [chatSubTab, setChatSubTab] = useState<"dms" | "local" | "city" | "global">("local");
  const [chatUnread, setChatUnread] = useState<Record<"dms" | "local" | "city" | "global", boolean>>({
    dms: false,
    local: false,
    city: false,
    global: false,
  });
  const [cityMessages, setCityMessages] = useState<LocationChatEntry[]>([]);
  const [cityInput, setCityInput] = useState("");
  const [cityPending, setCityPending] = useState(false);
  const [globalMessages, setGlobalMessages] = useState<LocationChatEntry[]>([]);
  const [globalInput, setGlobalInput] = useState("");
  const [globalPending, setGlobalPending] = useState(false);
  const [playerNotes, setPlayerNotes] = useState<string>(
    () => localStorage.getItem("ww-player-notes") ?? ""
  );
  const [leftWidth, setLeftWidth] = useState(60);
  const [isResizing, setIsResizing] = useState(false);
  const [isInfoPaneCollapsed, setIsInfoPaneCollapsed] = useState(false);
  const [, setPlayerInfoState] = useState<PlayerInfo | null>(() => getPlayerInfo());
  const [authRecoveryMessage, setAuthRecoveryMessage] = useState<string | null>(null);
  const [startupRecoveryMessage, setStartupRecoveryMessage] = useState<string | null>(null);
  const [observerModeMessage, setObserverModeMessage] = useState<string | null>(null);
  const [restMetrics, setRestMetrics] = useState<RestMetricsResponse | null>(null);

  const [shards, setShards] = useState<ShardInfo[]>([]);
  const [shardsLoaded, setShardsLoaded] = useState(false);
  const [selectedShardUrl, setSelectedShardUrlState] = useState<string>(
    () => getSelectedShardUrl() ?? ""
  );
  const [showOnboarding, setShowOnboarding] = useState<boolean>(() => !hasCompletedOnboarding());
  const startupShardSelectionRequired = shardsLoaded && shards.length > 1 && !selectedShardUrl;
  const standaloneShardMode = shardsLoaded && shards.length === 0;
  const apiBaseReady =
    standaloneShardMode ||
    (shardsLoaded &&
      !startupShardSelectionRequired &&
      Boolean(selectedShardUrl || getApiBase()));

  const narrativeEndRef = useRef<HTMLDivElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const cityEndRef = useRef<HTMLDivElement | null>(null);
  const globalEndRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const seenAgentTsRef = useRef<Set<string>>(new Set());
  const seenChatIdsRef = useRef<Set<number>>(new Set());
  const knownLocalChatIdsRef = useRef<Set<number>>(new Set());
  const knownCityChatIdsRef = useRef<Set<number>>(new Set());
  const knownGlobalChatIdsRef = useRef<Set<number>>(new Set());
  const knownInboxKeysRef = useRef<Set<string>>(new Set());
  const unreadBootstrappedRef = useRef({
    local: false,
    city: false,
    global: false,
    dms: false,
  });
  const hydratedRef = useRef(false);
  const playerLocationRef = useRef<string | null>(null);
  const digestBootFailureShownRef = useRef(false);
  const [pendingDest, setPendingDest] = useState<string | null>(null);
  const [activeRoute, setActiveRoute] = useState<{ destination: string; remaining: string[] } | null>(null);

  // Fetch available city shards from the federation world root on mount
  useEffect(() => {
    fetchShards().then((fetched) => {
      setShards(fetched);
      const stored = getSelectedShardUrl();
      const resolved =
        (stored && fetched.find((s) => s.shard_url === stored)) ||
        (selectedShardUrl && fetched.find((s) => s.shard_url === selectedShardUrl)) ||
        null;

      if (resolved) {
        setSelectedShardUrlState(resolved.shard_url);
        setApiBase(resolved.shard_url);
        setShardsLoaded(true);
        return;
      }

      if (fetched.length === 1) {
        const only = fetched[0];
        setSelectedShardUrlState(only.shard_url);
        setSelectedShardUrl(only.shard_url);
        setApiBase(only.shard_url);
        setShardsLoaded(true);
        return;
      }

      if (fetched.length > 1) {
        clearSelectedShardUrl();
        setSelectedShardUrlState("");
      }
      setShardsLoaded(true);
    }).catch(() => {
      const toast: ToastItem = {
        id: makeId("toast"),
        title: "Shard registry unavailable",
        detail: "Could not load the federation shard list. Falling back to the current backend only.",
        kind: "info",
      };
      setToasts((prev) => [
        toast,
        ...prev,
      ].slice(0, 4));
      setShardsLoaded(true);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCitySwitch = useCallback((shardUrl: string) => {
    if (shardUrl === selectedShardUrl) return;
    setSelectedShardUrl(shardUrl);
    clearJwt();
    clearOnboardedSession();
    window.location.reload();
  }, [selectedShardUrl]);

  const pushToast = useCallback(
    (title: string, detail?: string, kind: ToastItem["kind"] = "error") => {
      const toast: ToastItem = { id: makeId("toast"), title, detail, kind };
      setToasts((prev) => [toast, ...prev].slice(0, 4));
    },
    [],
  );

  const notifyMention = useCallback(
    (messages: LocationChatEntry[], channel: "local" | "city" | "global") => {
      const currentPlayer = digest?.roster.find((r) => r.session_id === sessionId);
      const mentionNames = [
        currentPlayer?.player_name,
        currentPlayer?.display_name,
      ];
      const hits = messages.filter(
        (m) =>
          m.session_id !== sessionId &&
          messageMentionsAnyName(m.message, mentionNames),
      );
      if (hits.length === 0) return;
      const latest = hits[hits.length - 1];
      const speaker = latest.display_name || latest.session_id.slice(0, 12);
      pushToast(
        `Mentioned in ${channel} chat`,
        `${speaker} tagged you: ${latest.message}`,
        "info",
      );
    },
    [digest, pushToast, sessionId],
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearShardAuthState = useCallback((message: string) => {
    clearJwt();
    clearOnboardedSession();
    setPlayerInfoState(null);
    setObserverModeMessage(null);
    setAuthRecoveryMessage(message);
  }, []);

  const handleAuthFailure = useCallback((err: { status: number; code?: string }) => {
    if (err.status === 403 && err.code === "pass_expired") {
      setAuthRecoveryMessage(
        "Your visitor pass on this shard has expired. You can still observe, but action turns remain locked until the pass is renewed.",
      );
      return true;
    }
    if (err.status === 401 || err.status === 403) {
      clearShardAuthState(authRecoveryCopy(err.code));
      return true;
    }
    return false;
  }, [clearShardAuthState]);

  useEffect(() => {
    if (!hasMixedContentApiBase()) return;
    pushToast(
      "Shard URL was insecure on HTTPS",
      "The browser blocked an HTTP shard address. Falling back to the same-origin backend for now.",
      "info",
    );
  }, [pushToast]);

  const startResizing = useCallback(() => {
    setIsResizing(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = useCallback((e: MouseEvent) => {
    if (isResizing) {
      const newWidth = (e.clientX / window.innerWidth) * 100;
      if (newWidth > 20 && newWidth < 80) {
        setLeftWidth(newWidth);
      }
    }
  }, [isResizing]);

  useEffect(() => {
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [resize, stopResizing]);

  const refreshReadiness = useCallback(async () => {
    try {
      const r = await getSettingsReadiness();
      setSettingsReadiness(r);
      const observerCheck = r.checks.find((check) => check.code === "observer_mode");
      if (!observerCheck || observerCheck.ok) {
        setObserverModeMessage(null);
      }
    } catch (err) {
      pushToast("Readiness check failed", String(err));
    }
  }, [pushToast]);

  const refreshRestMetrics = useCallback(async () => {
    try {
      const payload = await getRestMetrics(true);
      setRestMetrics(payload);
    } catch {
      // silent: presence metrics are additive operator context
    }
  }, []);

  const refreshDigest = useCallback(async () => {
    try {
      const d = await getWorldDigest(sessionId, 20);
      digestBootFailureShownRef.current = false;
      setStartupRecoveryMessage(null);
      setDigest(d);

      if (d.world_id && d.world_id !== getOnboardedWorldId()) {
        clearOnboardedSession();
      }

      const SUMMARY_RE = /^Player action:\s*([\s\S]*?)\s*Result:\s*([\s\S]*)$/;

      if (d.timeline && d.player_location) {
        // When the player moves to a new location, reset the agent feed so
        // events from previous locations don't bleed into the current view.
        if (d.player_location !== playerLocationRef.current) {
          playerLocationRef.current = d.player_location;
          seenAgentTsRef.current = new Set();
          seenChatIdsRef.current = new Set();
          setAgentFeed([]);
          setChatMessages([]);
          // Do NOT reset hydratedRef here — that would replace locally-accumulated
          // turn history with the server's third-person event summaries mid-travel.
          // Hydration only needs to run once on initial page load.
        }

        if (!hydratedRef.current) {
          hydratedRef.current = true;
          const playerEvents = d.timeline
            .filter((e) => e.who === sessionId && e.summary && e.ts)
            .sort((a, b) => (a.ts ?? "").localeCompare(b.ts ?? ""));
          if (playerEvents.length > 0) {
            const hydratedTurns: Turn[] = playerEvents.map((e) => {
              const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
              return {
                id: makeId("turn"),
                ts: e.ts!,
                action: match ? match[1] : (e.summary ?? ""),
                ackLine: null,
                narrative: match ? match[2] : (e.summary ?? ""),
                location: e.destination ?? e.location ?? null,
              };
            });
            setTurns(hydratedTurns);
          }
          const agentEvents = d.timeline
            .filter((e) => e.who !== sessionId && e.summary && e.ts)
            .map((e) => {
              const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
              return {
                ts: e.ts!,
                displayName: e.display_name ?? (e.who ? e.who.slice(0, 12) : "?"),
                agentAction: match ? match[1] : null,
                narrative: match ? match[2] : (e.summary ?? null),
              };
            });
          agentEvents.forEach((item) => seenAgentTsRef.current.add(item.ts));
          if (agentEvents.length > 0) setAgentFeed(agentEvents.slice(-20));
        }

        const newItems = d.timeline
          .filter((e) => e.who !== sessionId && e.summary && e.ts && !seenAgentTsRef.current.has(e.ts))
          .map((e) => {
            const match = e.summary ? SUMMARY_RE.exec(e.summary) : null;
            return {
              ts: e.ts!,
              displayName: e.display_name ?? (e.who ? e.who.slice(0, 12) : "?"),
              agentAction: match ? match[1] : null,
              narrative: match ? match[2] : (e.summary ?? null),
            };
          });
        if (newItems.length > 0) {
          newItems.forEach((item) => seenAgentTsRef.current.add(item.ts));
          setAgentFeed((prev) => [...prev, ...newItems].slice(-20));
        }

        // Chat messages come from the digest directly
        if (d.location_chat) {
          const newChat = d.location_chat.filter((m) => !seenChatIdsRef.current.has(m.id));
          if (newChat.length > 0) {
            newChat.forEach((m) => seenChatIdsRef.current.add(m.id));
            setChatMessages((prev) => [...prev, ...newChat].slice(-50));
          }
        }
      }
    } catch (err) {
      const detail =
        err instanceof Error
          ? err.message
          : "Could not load world state from the selected shard.";
      setStartupRecoveryMessage(detail);
      if (!digestBootFailureShownRef.current) {
        digestBootFailureShownRef.current = true;
        pushToast(
          "Shard bootstrap failed",
          detail,
        );
      }
    }
  }, [pushToast, sessionId]);

  const refreshInbox = useCallback(async (sid: string) => {
    try {
      const [inbox, threads] = await Promise.all([
        getPlayerInbox(sid),
        getPlayerThreads(sid),
      ]);
      setPlayerInbox(inbox.letters);
      setPlayerThreads(threads.threads);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    if (playerThreads.length === 0) {
      setSelectedThreadKey(null);
      return;
    }
    setSelectedThreadKey((current) => {
      if (current && playerThreads.some((thread) => thread.thread_key === current)) {
        return current;
      }
      return playerThreads[0].thread_key;
    });
  }, [playerThreads]);

  const openPlayerThread = useCallback(async (thread: DMThread) => {
    setSelectedThreadKey(thread.thread_key);
    if (!sessionId || thread.unread_count <= 0) return;
    try {
      await markPlayerThreadRead(sessionId, thread.thread_key);
      await refreshInbox(sessionId);
    } catch {
      // silent
    }
  }, [refreshInbox, sessionId]);

  useEffect(() => {
    if (!apiBaseReady) return;
    void refreshReadiness();
    void refreshRestMetrics();
    void refreshDigest();
    void refreshInbox(sessionId);
  }, [apiBaseReady, refreshReadiness, refreshRestMetrics, refreshDigest, refreshInbox, sessionId]);

  const handleRuntimeInteractionError = useCallback((err: unknown, fallbackTitle: string) => {
    if (isApiRequestError(err)) {
      if (err.status === 402 && err.code === "observer_mode_required") {
        setObserverModeMessage(err.message);
        void refreshReadiness();
        return;
      }
      if (handleAuthFailure(err)) {
        return;
      }
    }
    pushToast(fallbackTitle, err instanceof Error ? err.message : String(err));
  }, [handleAuthFailure, pushToast, refreshReadiness]);

  // Rehydrate auth state from JWT on mount
  useEffect(() => {
    if (!apiBaseReady) return;
    if (!getJwt()) {
      if (getPlayerInfo()) {
        clearJwt();
        setPlayerInfoState(null);
      }
      return;
    }
    getAuthMe()
      .then((me) => {
        setJwt(me.token || getJwt()!);
        setAuthRecoveryMessage(null);
        const info: PlayerInfo = {
          player_id: me.player_id,
          username: me.username,
          display_name: me.display_name,
          pass_type: me.pass_type,
          pass_expires_at: me.pass_expires_at,
        };
        setPlayerInfo(info);
        setPlayerInfoState(info);
      })
      .catch((err) => {
        if (isApiRequestError(err)) {
          if (handleAuthFailure(err)) {
            return;
          }
          pushToast("Saved login refresh failed", err.message, "info");
          return;
        }
        pushToast(
          "Saved login refresh failed",
          err instanceof Error ? err.message : String(err),
          "info",
        );
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBaseReady, handleAuthFailure, pushToast]);

  useEffect(() => {
    if (!apiBaseReady) return;
    const interval = window.setInterval(() => {
      void refreshRestMetrics();
      void refreshDigest();
      void refreshInbox(sessionId);
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [apiBaseReady, refreshRestMetrics, refreshDigest, refreshInbox, sessionId]);

  useEffect(() => {
    narrativeEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, draftNarrative, agentFeed]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  useEffect(() => {
    cityEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [cityMessages]);

  useEffect(() => {
    globalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [globalMessages]);

  useEffect(() => {
    const known = knownLocalChatIdsRef.current;
    const incoming = chatMessages.filter((m) => !known.has(m.id) && m.session_id !== sessionId);
    chatMessages.forEach((m) => known.add(m.id));
    if (!unreadBootstrappedRef.current.local) {
      unreadBootstrappedRef.current.local = true;
      return;
    }
    notifyMention(incoming, "local");
    if (incoming.length > 0 && !(infoTab === "chats" && chatSubTab === "local")) {
      setChatUnread((prev) => ({ ...prev, local: true }));
    }
  }, [chatMessages, chatSubTab, infoTab, notifyMention, sessionId]);

  useEffect(() => {
    const known = knownCityChatIdsRef.current;
    const incoming = cityMessages.filter((m) => !known.has(m.id) && m.session_id !== sessionId);
    cityMessages.forEach((m) => known.add(m.id));
    if (!unreadBootstrappedRef.current.city) {
      unreadBootstrappedRef.current.city = true;
      return;
    }
    notifyMention(incoming, "city");
    if (incoming.length > 0 && !(infoTab === "chats" && chatSubTab === "city")) {
      setChatUnread((prev) => ({ ...prev, city: true }));
    }
  }, [cityMessages, chatSubTab, infoTab, notifyMention, sessionId]);

  useEffect(() => {
    const known = knownGlobalChatIdsRef.current;
    const incoming = globalMessages.filter((m) => !known.has(m.id) && m.session_id !== sessionId);
    globalMessages.forEach((m) => known.add(m.id));
    if (!unreadBootstrappedRef.current.global) {
      unreadBootstrappedRef.current.global = true;
      return;
    }
    notifyMention(incoming, "global");
    if (incoming.length > 0 && !(infoTab === "chats" && chatSubTab === "global")) {
      setChatUnread((prev) => ({ ...prev, global: true }));
    }
  }, [globalMessages, chatSubTab, infoTab, notifyMention, sessionId]);

  useEffect(() => {
    const known = knownInboxKeysRef.current;
    const incoming = playerInbox.filter((letter) => !known.has(letter.filename));
    playerInbox.forEach((letter) => known.add(letter.filename));
    if (!unreadBootstrappedRef.current.dms) {
      unreadBootstrappedRef.current.dms = true;
      return;
    }
    if (incoming.length > 0 && !(infoTab === "chats" && chatSubTab === "dms")) {
      setChatUnread((prev) => ({ ...prev, dms: true }));
    }
  }, [playerInbox, chatSubTab, infoTab]);

  useEffect(() => {
    if (infoTab !== "chats") return;
    setChatUnread((prev) => ({ ...prev, [chatSubTab]: false }));
  }, [chatSubTab, infoTab]);

  useEffect(() => {
    if (!apiBaseReady) return;
    if (!sessionId || infoTab !== "chats") return;
    let cancelled = false;
    async function poll() {
      if (cancelled) return;
      try {
        if (chatSubTab === "city" || chatSubTab === "global") {
          const loc = chatSubTab === "city" ? "__city__" : "__global__";
          const setFn = chatSubTab === "city" ? setCityMessages : setGlobalMessages;
          const data = await getLocationChat(loc);
          const msgs = (data.messages ?? []) as LocationChatEntry[];
          if (cancelled) return;
          setFn((prev) => {
            const byId = new Map(prev.map((m) => [m.id, m]));
            msgs.forEach((m) => byId.set(m.id, m));
            return [...byId.values()].slice(-100);
          });
        }
      } catch { /* ignore */ }
    }
    void poll();
    const interval = setInterval(() => void poll(), 4000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBaseReady, sessionId, infoTab, chatSubTab]);

  async function sendChat() {
    const msg = chatInput.trim();
    if (!msg || chatPending || !digest?.player_location) return;
    setChatPending(true);
    setChatInput("");
    const displayName = digest.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;
    try {
      const result = await postLocationChat(digest.player_location, sessionId, msg, displayName);
      const optimistic: LocationChatEntry = {
        id: result.id,
        session_id: sessionId,
        display_name: displayName ?? null,
        message: msg,
        ts: result.ts,
      };
      seenChatIdsRef.current.add(result.id);
      setChatMessages((prev) => [...prev, optimistic].slice(-50));
    } catch {
      // silent — message will reappear on next digest poll
    } finally {
      setChatPending(false);
    }
  }

  async function sendCityChat() {
    const msg = cityInput.trim();
    if (!msg || cityPending) return;
    setCityPending(true);
    setCityInput("");
    try {
      const result = await postLocationChat("__city__", sessionId, msg, playerName || undefined);
      const optimistic: LocationChatEntry = {
        id: result.id,
        session_id: sessionId,
        display_name: playerName || null,
        message: msg,
        ts: result.ts,
      };
      setCityMessages((prev) => {
        const byId = new Map(prev.map((m) => [m.id, m]));
        byId.set(optimistic.id, optimistic);
        return [...byId.values()];
      });
    } catch (err) {
      handleRuntimeInteractionError(err, "Send failed");
    } finally {
      setCityPending(false);
    }
  }

  async function sendGlobalChat() {
    const msg = globalInput.trim();
    if (!msg || globalPending) return;
    setGlobalPending(true);
    setGlobalInput("");
    try {
      const result = await postLocationChat("__global__", sessionId, msg, playerName || undefined);
      const optimistic: LocationChatEntry = {
        id: result.id,
        session_id: sessionId,
        display_name: playerName || null,
        message: msg,
        ts: result.ts,
      };
      setGlobalMessages((prev) => {
        const byId = new Map(prev.map((m) => [m.id, m]));
        byId.set(optimistic.id, optimistic);
        return [...byId.values()];
      });
    } catch (err) {
      handleRuntimeInteractionError(err, "Send failed");
    } finally {
      setGlobalPending(false);
    }
  }

  async function submitAction(text: string) {
    if (!text.trim() || pending) return;

    setPending(true);
    setDraftAckLine("");
    setDraftNarrative("");

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let capturedAck = "";

    try {
      const result = await streamAction(
        sessionId,
        text.trim(),
        undefined,
        (chunk) => setDraftNarrative((prev) => prev + chunk),
        ctrl.signal,
        (ack) => { capturedAck = ack; setDraftAckLine(ack); },
      );
      setTurns((prev) => [
        ...prev,
        {
          id: makeId("turn"),
          ts: new Date().toISOString(),
          action: text.trim(),
          ackLine: result.ack_line || capturedAck || null,
          narrative: result.narrative,
          location: (result.state_changes?.destination as string) ?? (result.state_changes?.location as string) ?? null,
        },
      ]);
      setDraftAckLine("");
      setDraftNarrative("");
      setObserverModeMessage(null);
      void refreshDigest();
    } catch (err: unknown) {
      if ((err as { name?: string })?.name !== "AbortError") {
        handleRuntimeInteractionError(err, "Action failed.");
      }
    } finally {
      setPending(false);
    }
  }

  function resetForFreshArrival() {
    abortRef.current?.abort();
    clearOnboardedSession();
    const next = replaceSessionId();
    setSessionId(next);
    setTurns([]);
    setDigest(null);
    setDraftAckLine("");
    setDraftNarrative("");
    setActionText("");
    setAgentFeed([]);
    setChatMessages([]);
    setCityMessages([]);
    setGlobalMessages([]);
    setPendingDest(null);
    setActiveRoute(null);
    setAuthRecoveryMessage(null);
    setStartupRecoveryMessage(null);
    setObserverModeMessage(null);
    seenAgentTsRef.current = new Set();
    seenChatIdsRef.current = new Set();
    hydratedRef.current = false;
    playerLocationRef.current = null;
    digestBootFailureShownRef.current = false;
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const text = actionText;
      setActionText("");
      void submitAction(text);
    }
  }

  function handleNewSession() {
    if (!window.confirm("Start a new session? You'll enter the world as a stranger — your current character will be left behind.")) return;
    resetForFreshArrival();
  }

  async function executeMapMove(destName: string, skipToDestination = false) {
    if (pending) return;
    setPending(true);
    setPendingDest(null);
    try {
      const result = await postMapMove(sessionId, destName, skipToDestination);
      const actionText = result.route_remaining.length > 0
        ? `En route to ${destName.replace(/_/g, " ")} — passing through ${result.to_location.replace(/_/g, " ")}`
        : `Arrive at ${result.to_location.replace(/_/g, " ")}`;
      setTurns((prev) => [
        ...prev,
        {
          id: makeId("turn"),
          ts: new Date().toISOString(),
          action: actionText,
          ackLine: null,
          narrative: result.narrative,
          location: result.to_location,
        },
      ]);
      if (result.route_remaining.length > 0) {
        setActiveRoute({ destination: destName, remaining: result.route_remaining });
      } else {
        setActiveRoute(null);
      }
      setMapRefreshSeq((prev) => prev + 1);
      setObserverModeMessage(null);
      void refreshDigest();
    } catch (err) {
      handleRuntimeInteractionError(err, "Move failed.");
      setActiveRoute(null);
    } finally {
      setPending(false);
    }
  }

  const [mapSearch, setMapSearch] = useState<string>("");
  const [mapFilter, setMapFilter] = useState<"all" | "occupied" | "quiet" | "landmarks">("all");
  const [mapViewport, setMapViewport] = useState<MapViewport | null>(null);
  const [mapQueryResult, setMapQueryResult] = useState<WorldMapQueryResponse | null>(null);
  const [mapPending, setMapPending] = useState(false);
  const mapRequestSeqRef = useRef(0);
  const [mapRefreshSeq, setMapRefreshSeq] = useState(0);

  function handleMapNodeClick(nodeName: string) {
    const allNodes = mapQueryResult?.nodes ?? digest?.location_graph?.nodes ?? [];
    const playerNode = allNodes.find((n) => n.is_player);
    const targetNode = allNodes.find((n) => n.name === nodeName);
    if (!targetNode) {
      return;
    }
    // If the player is at an unmapped location (landmark/orphan), stage for confirm
    // so they can cancel; server snap logic handles routing from there.
    if (!playerNode) {
      setPendingDest(nodeName);
      return;
    }
    if (playerNode.key === targetNode.key) return;
    // Normal case: stage as pending so user confirms
    setPendingDest(nodeName);
  }

  function confirmRouteMove() {
    if (pendingDest) {
      setActiveRoute(null);
      void executeMapMove(pendingDest);
    }
  }

  // BFS from player to pendingDest to show the route preview path
  const pendingPath = useMemo<string[]>(() => {
    if (!pendingDest) return [];
    const allNodes = mapQueryResult?.nodes ?? digest?.location_graph?.nodes ?? [];
    const allEdges = mapQueryResult?.edges ?? digest?.location_graph?.edges ?? [];
    const playerNode = allNodes.find((n) => n.is_player);
    const targetNode = allNodes.find((n) => n.name === pendingDest);
    if (!playerNode || !targetNode) return [];
    // Build adjacency by key (edges are bidirectional)
    const adj = new Map<string, string[]>();
    for (const e of allEdges) {
      if (!adj.has(e.from)) adj.set(e.from, []);
      if (!adj.has(e.to)) adj.set(e.to, []);
      adj.get(e.from)!.push(e.to);
      adj.get(e.to)!.push(e.from);
    }
    const keyToName = new Map(allNodes.map((n) => [n.key, n.name]));
    // BFS for shortest key-path
    const queue: string[][] = [[playerNode.key]];
    const visited = new Set<string>([playerNode.key]);
    while (queue.length > 0) {
      const path = queue.shift()!;
      const current = path[path.length - 1];
      if (current === targetNode.key) {
        return path.map((k) => keyToName.get(k) ?? k);
      }
      for (const neighbor of adj.get(current) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push([...path, neighbor]);
        }
      }
    }
    return [];
  }, [pendingDest, digest, mapQueryResult]);

  useEffect(() => {
    if (infoTab !== "map") return;
    if (!apiBaseReady) return;
    if (!mapViewport) return;

    const requestSeq = ++mapRequestSeqRef.current;
    const timeout = window.setTimeout(() => {
      setMapPending(true);
      void queryWorldMap({
        ...mapViewport,
        sessionId,
        query: mapSearch,
        occupiedOnly: mapFilter === "occupied",
        quietOnly: mapFilter === "quiet",
        includeLandmarks: mapFilter === "landmarks" || Boolean(mapSearch.trim()),
      })
        .then((result) => {
          if (requestSeq !== mapRequestSeqRef.current) return;
          setMapQueryResult(result);
        })
        .catch(() => {
          if (requestSeq !== mapRequestSeqRef.current) return;
          setMapQueryResult(null);
        })
        .finally(() => {
          if (requestSeq === mapRequestSeqRef.current) {
            setMapPending(false);
          }
        });
    }, mapSearch.trim() ? 250 : 100);

    return () => window.clearTimeout(timeout);
  }, [apiBaseReady, infoTab, mapFilter, mapRefreshSeq, mapSearch, mapViewport, sessionId]);

  const shortSession = sessionId.slice(-10);
  const playerName = digest?.roster.find((r) => r.session_id === sessionId)?.player_name ?? undefined;
  const showingEntryScreen = turns.length === 0 && !draftNarrative && !draftAckLine && getOnboardedSessionId() !== sessionId;
  const selectedShard = shards.find((shard) => shard.shard_url === selectedShardUrl) ?? null;
  const observerModeCheck = settingsReadiness?.checks.find((check) => check.code === "observer_mode") ?? null;
  const observerModeRequired = Boolean(observerModeMessage || (observerModeCheck && !observerModeCheck.ok));
  const observerModeDetail =
    observerModeMessage ||
    ((!observerModeCheck?.ok && observerModeCheck?.message) ? observerModeCheck.message : "");
  const actionComposerDisabled = pending || showingEntryScreen || !apiBaseReady || observerModeRequired;
  const actionPlaceholder = observerModeRequired
    ? "Observer mode: add your own narrative key in Settings to act."
    : "What do you do?";
  const currentCityLabel = (selectedShard?.city_id ?? (shards.length === 1 ? shards[0]?.city_id : null) ?? "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
  const currentLocationLabel = digest?.player_location?.replace(/_/g, " ") ?? "";
  const worldContextLabel = [currentCityLabel, currentLocationLabel || "choosing a place"]
    .filter(Boolean)
    .join(" · ");
  const nodes = digest?.location_graph?.nodes ?? [];
  const edges = digest?.location_graph?.edges ?? [];
  const chatsTabHasUnread = Object.values(chatUnread).some(Boolean);

  // The 'roster' from the backend is scoped specifically to the player's current location.
  // Therefore, the roster's length is precisely the number of people in the current scene.
  const sceneTotalCount = digest?.roster.length ?? 0;

  // To find the total world population, sum human players (location_population) and
  // agents (agent_count per node). Agents were split out to avoid double-counting on
  // the map, but both must be included in the world total.
  const worldTotalCount = (digest?.location_population
    ? Object.values(digest.location_population).reduce((sum, count) => sum + count, 0)
    : 0) + (digest?.location_graph?.nodes.reduce((sum, n) => sum + (n.agent_count ?? 0), 0) ?? 0);
  const worldPresenceCount = restMetrics?.counts.total ?? worldTotalCount;
  const restingPresenceCount = restMetrics?.counts.resting ?? 0;

  const mapNodes = useMemo(
    () => (mapQueryResult?.nodes ?? nodes).filter((n) => n.lat != null && n.lon != null),
    [mapQueryResult, nodes],
  );
  const mapEdges = useMemo(
    () => mapQueryResult?.edges ?? edges,
    [mapQueryResult, edges],
  );



  return (
    <div className="ww-shell">
      <header className="ww-topbar">
        <span className="ww-topbar-title">WorldWeaver</span>
        {worldContextLabel && (
          <span className="ww-world-context" title="Current world context">
            {worldContextLabel}
          </span>
        )}
        {shards.length > 0 && (
          <select
            className="ww-city-picker"
            value={selectedShardUrl}
            onChange={(e) => handleCitySwitch(e.target.value)}
            title="Switch city"
          >
            {shards.length > 1 && (
              <option value="" disabled>
                select city
              </option>
            )}
            {shards.map((s) => (
              <option key={s.shard_id} value={s.shard_url}>
                {s.city_id ?? s.shard_id}
              </option>
            ))}
          </select>
        )}
        <div className="ww-topbar-right">
          {digest && (
            <>
              <span className="ww-world-stat" title="People at your location">
                scene: {sceneTotalCount} here
              </span>
              <span className="ww-world-stat" title="People currently present across the shard">
                world: {worldPresenceCount} present
              </span>
              {restMetrics && (
                <span className="ww-world-stat" title="Residents currently resting across the shard">
                  resting: {restingPresenceCount}
                </span>
              )}
            </>
          )}
          <span className="ww-session-label" title={sessionId}>…{shortSession}</span>
          <button className="ww-icon-btn" onClick={handleNewSession} title="New session">↺</button>
          <button className="ww-icon-btn" onClick={() => setIsSettingsOpen(true)} title="Settings">⚙</button>

        </div>
      </header>

      <RuntimeDiagnosticsBanner readiness={settingsReadiness} />

      {activeRoute && (
        <div className="ww-route-banner">
          <span className="ww-route-banner-label">
            → {activeRoute.destination.replace(/_/g, " ")}
            <span className="ww-route-banner-hops"> · {activeRoute.remaining.length} stop{activeRoute.remaining.length !== 1 ? "s" : ""}</span>
          </span>
          <button
            className="ww-route-banner-btn ww-route-banner-btn--skip"
            onClick={() => void executeMapMove(activeRoute.destination, true)}
            disabled={pending}
            title="Move directly to destination, dropping traces through intermediate stops"
          >
            {pending ? <MagicFingerLoader size={18} /> : "Skip →"}
          </button>
          <button
            className="ww-route-banner-btn"
            onClick={() => void executeMapMove(activeRoute.destination)}
            disabled={pending}
            title="Stop and observe the next location on the way"
          >
            {pending ? <MagicFingerLoader size={18} /> : "Next hop →"}
          </button>
          <button
            className="ww-route-banner-cancel"
            onClick={() => setActiveRoute(null)}
            title="Cancel route"
          >✕</button>
        </div>
      )}

      <div className={`ww-body${isResizing ? " is-resizing" : ""}${isInfoPaneCollapsed ? " is-collapsed" : ""}`} style={{ display: 'flex', flexDirection: 'row', height: 'calc(100vh - 40px)', overflow: 'hidden' }}>
        <div className="ww-action-col" style={{
          width: isInfoPaneCollapsed ? 'calc(100% - 32px)' : `${leftWidth}%`,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          borderRight: isInfoPaneCollapsed ? 'none' : '1px solid var(--ww-border)',
          overflow: 'hidden'
        }}>
          {/* ── Left column: action / narrative ── */}
          <div className="ww-narrative-scroll" style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
            {turns.length === 0 && !draftNarrative && !draftAckLine && getOnboardedSessionId() !== sessionId && (
              <EntryScreen
                sessionId={sessionId}
                shardsLoaded={shardsLoaded}
                shards={shards}
                selectedShardUrl={selectedShardUrl}
                onSelectShard={(shardUrl) => {
                  setSelectedShardUrlState(shardUrl);
                  setSelectedShardUrl(shardUrl);
                  setApiBase(shardUrl);
                }}
                onEnter={(action) => {
                  setOnboardedSessionId(sessionId);
                  if (digest?.world_id) setOnboardedWorldId(digest.world_id);
                  void submitAction(action);
                }}
                onRuntimeError={handleRuntimeInteractionError}
              />
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
                    {item.data.ackLine && (
                      <div className="ww-turn-ack">{item.data.ackLine}</div>
                    )}
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
                )
              )}
            {(draftNarrative || pending) && (
              <div className="ww-turn ww-turn--draft">
                {draftNarrative
                  ? <div>{draftNarrative}</div>
                  : <span className="ww-typing"><MagicFingerLoader size={40} /></span>}
              </div>
            )}
            <div ref={narrativeEndRef} />
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
                    <button className="ww-recovery-strip-btn" onClick={resetForFreshArrival}>
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
                    <button
                      className="ww-recovery-strip-btn"
                      onClick={() => {
                        void refreshReadiness();
                        void refreshRestMetrics();
                        void refreshDigest();
                        void refreshInbox(sessionId);
                      }}
                    >
                      Retry sync
                    </button>
                    <button className="ww-recovery-strip-btn" onClick={resetForFreshArrival}>
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
                    <button className="ww-recovery-strip-btn" onClick={() => setIsSettingsOpen(true)}>
                      Open settings
                    </button>
                    <button className="ww-recovery-strip-btn" onClick={() => void refreshReadiness()}>
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
              onChange={(e) => setActionText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={actionComposerDisabled}
              autoFocus
            />
            <button
              className="ww-send-btn"
              onClick={() => { const t = actionText; setActionText(""); void submitAction(t); }}
              disabled={actionComposerDisabled || !actionText.trim()}
            >
              {pending ? <MagicFingerLoader size={20} /> : "→"}
            </button>
          </div>
        </div>

        {/* ── Adjustable Divider ── */}
        {!isInfoPaneCollapsed && (
          <div
            className="ww-divider"
            onMouseDown={startResizing}
            style={{
              width: '6px',
              cursor: 'col-resize',
              backgroundColor: isResizing ? 'var(--ww-accent)' : 'transparent',
              zIndex: 10,
              transition: 'background-color 0.2s'
            }}
          />
        )}

        {/* ── Right column: Info Pane (Tabs + Body) ── */}
        {isInfoPaneCollapsed ? (
          <div
            className="ww-expand-bar"
            onClick={() => setIsInfoPaneCollapsed(false)}
            title="Expand Info"
            style={{
              width: '32px',
              height: '100%',
              backgroundColor: 'var(--ww-bg-accent)',
              borderLeft: '1px solid var(--ww-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              writingMode: 'vertical-rl',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--ww-text)',
              transition: 'background-color 0.2s'
            }}
          >
            INFO TAB ◀
          </div>
        ) : (
          <div className="ww-info-pane" style={{ width: `${100 - leftWidth}%`, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
            <div className="ww-info-tabs" style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{ flex: 1, display: 'flex' }}>
                {(["map", "presence", "chats", "notes"] as const).map((tab) => (
                  <button
                    key={tab}
                    className={`ww-info-tab${infoTab === tab ? " ww-info-tab--active" : ""}`}
                    onClick={() => setInfoTab(tab as "map" | "presence" | "chats" | "notes")}
                  >
                    <span className="ww-tab-label">
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                      {tab === "chats" && chatsTabHasUnread && <span className="ww-tab-dot" aria-hidden="true" />}
                    </span>
                  </button>
                ))}
              </div>
              <button
                className="ww-collapse-btn"
                onClick={() => setIsInfoPaneCollapsed(true)}
                title="Collapse Info"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--ww-text)',
                  cursor: 'pointer',
                  padding: '0.5rem',
                  fontSize: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                ▶
              </button>
            </div>

            <div className="ww-info-body" style={{ flex: 1, overflowY: 'auto' }}>
              {infoTab === "chats" && (
                <div className="ww-chats-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  {/* Sub-tab bar */}
                  <div className="ww-chat-subtabs">
                    {(["dms", "local", "city", "global"] as const).map((sub) => (
                      <button
                        key={sub}
                        className={`ww-chat-subtab${chatSubTab === sub ? " ww-chat-subtab--active" : ""}`}
                        onClick={() => setChatSubTab(sub)}
                      >
                        <span className="ww-tab-label">
                          {sub === "dms" ? "DMs" : sub.charAt(0).toUpperCase() + sub.slice(1)}
                          {chatUnread[sub] && <span className="ww-tab-dot" aria-hidden="true" />}
                        </span>
                      </button>
                    ))}
                  </div>

                  {/* Local sub-tab */}
                  {chatSubTab === "local" && (
                    <div className="ww-here-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
                      {digest?.roster && digest.roster.length > 0 && (
                        <details className="ww-here-roster-collapsible" style={{ borderBottom: '1px solid var(--ww-border)' }}>
                          <summary style={{ padding: '0.5rem 1rem', cursor: 'pointer', fontWeight: 600, backgroundColor: 'var(--ww-bg-accent)', borderBottom: '1px solid var(--ww-border)' }}>
                            Inhabitants ({digest.active_sessions} active / {digest.roster.length} present)
                          </summary>
                          <div className="ww-here-roster" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', alignItems: 'center', maxHeight: '40vh', overflowY: 'auto' }}>
                            <ul className="ww-roster" style={{ width: '100%', listStyle: 'none', padding: 0 }}>
                              {digest.roster.map((r: DigestRosterEntry) => (
                                <li
                                  key={r.session_id}
                                  className={`ww-roster-entry${r.session_id === sessionId ? " ww-roster-entry--you" : ""}`}
                                  style={{ padding: '0.75rem', marginBottom: '0.5rem', backgroundColor: 'var(--ww-bg-accent, #1a1a1a)', borderRadius: '4px', border: '1px solid var(--ww-border)', width: '100%', textAlign: 'center' }}
                                >
                                  <div className="ww-roster-card-line">
                                    <span className="ww-roster-name" style={{ fontWeight: 600 }}>
                                      {r.display_name ?? r.session_id.slice(0, 12)}
                                      {r.session_id === sessionId && <span className="ww-roster-you"> (you)</span>}
                                    </span>
                                    <div className="ww-presence-chips">
                                      {r.status && (
                                        <span className={`ww-presence-pill ww-presence-pill--${r.status}`}>
                                          {r.status === "resting" ? "Resting" : r.status === "returning" ? "Returning" : "Active"}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </details>
                      )}
                      <div className="ww-here-chat" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <div className="ww-chat-messages">
                          {chatMessages.length === 0 && (
                            <div className="ww-chat-empty">No one is talking here yet.</div>
                          )}
                          {chatMessages.map((m) => (
                            <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                              <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                              <span className="ww-chat-text">{m.message}</span>
                            </div>
                          ))}
                          <div ref={chatEndRef} />
                        </div>
                        <div className="ww-chat-input-row">
                          <input
                            className="ww-chat-input"
                            type="text"
                            placeholder="Say aloud… Use @Name to tag someone."
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") void sendChat(); }}
                            disabled={chatPending || !digest?.player_location}
                          />
                          <button
                            className="ww-send-btn"
                            onClick={() => void sendChat()}
                            disabled={chatPending || !chatInput.trim() || !digest?.player_location}
                          >
                            {chatPending ? "…" : "→"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* City sub-tab */}
                  {chatSubTab === "city" && (
                    <div className="ww-here-chat" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                      <div className="ww-chat-messages">
                        {cityMessages.length === 0 && (
                          <div className="ww-chat-empty">Nothing said city-wide yet.</div>
                        )}
                        {cityMessages.map((m) => (
                          <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                            <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                            <span className="ww-chat-text">{m.message}</span>
                          </div>
                        ))}
                        <div ref={cityEndRef} />
                      </div>
                      <div className="ww-chat-input-row">
                        <input
                          className="ww-chat-input"
                          type="text"
                          placeholder="Broadcast to the city… Use @Name to tag someone."
                          value={cityInput}
                          onChange={(e) => setCityInput(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") void sendCityChat(); }}
                          disabled={cityPending}
                        />
                        <button
                          className="ww-send-btn"
                          onClick={() => void sendCityChat()}
                          disabled={cityPending || !cityInput.trim()}
                        >
                          {cityPending ? "…" : "→"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Global sub-tab */}
                  {chatSubTab === "global" && (
                    <div className="ww-here-chat" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                      <div className="ww-chat-messages">
                        {globalMessages.length === 0 && (
                          <div className="ww-chat-empty">Nothing said globally yet.</div>
                        )}
                        {globalMessages.map((m) => (
                          <div key={m.id} className={`ww-chat-msg${m.session_id === sessionId ? " ww-chat-msg--you" : ""}`}>
                            <span className="ww-chat-name">{m.display_name ?? m.session_id.slice(0, 12)}</span>
                            <span className="ww-chat-text">{m.message}</span>
                          </div>
                        ))}
                        <div ref={globalEndRef} />
                      </div>
                      <div className="ww-chat-input-row">
                        <input
                          className="ww-chat-input"
                          type="text"
                          placeholder="Broadcast globally… Use @Name to tag someone."
                          value={globalInput}
                          onChange={(e) => setGlobalInput(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") void sendGlobalChat(); }}
                          disabled={globalPending}
                        />
                        <button
                          className="ww-send-btn"
                          onClick={() => void sendGlobalChat()}
                          disabled={globalPending || !globalInput.trim()}
                        >
                          {globalPending ? "…" : "→"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* DMs sub-tab */}
                  {chatSubTab === "dms" && (
                    <div className="ww-info-inbox-tab">
                      <LetterCompose
                        defaultFromName={playerName}
                        sessionId={sessionId}
                        availableAgents={digest?.known_agents ?? []}
                        preferredAgent={selectedThreadKey ?? undefined}
                        onSent={() => void refreshInbox(sessionId)}
                      />
                      {playerThreads.length > 0 ? (
                        <div className="ww-inbox-list-section" style={{ marginTop: '1rem' }}>
                          <h4 className="ww-info-section-title">Your mail ({playerThreads.length} thread{playerThreads.length === 1 ? "" : "s"})</h4>
                          <div className="ww-thread-layout">
                            <ul className="ww-inbox ww-thread-list">
                              {playerThreads.map((thread) => (
                                <li key={thread.thread_key} className="ww-inbox-letter">
                                  <button
                                    type="button"
                                    className={`ww-thread-list-item${selectedThreadKey === thread.thread_key ? " active" : ""}`}
                                    onClick={() => void openPlayerThread(thread)}
                                  >
                                    <span className="ww-inbox-from">{thread.counterpart}</span>
                                    <span className="ww-inbox-thread-meta">
                                      {thread.unread_count > 0 ? `${thread.unread_count} unread` : `${thread.messages.length} messages`}
                                    </span>
                                  </button>
                                </li>
                              ))}
                            </ul>
                            <div className="ww-thread-pane">
                              {playerThreads
                                .filter((thread) => thread.thread_key === selectedThreadKey)
                                .map((thread) => (
                                  <div key={thread.thread_key} className="ww-thread-pane-inner">
                                    <div className="ww-thread-pane-header">
                                      <h5 className="ww-info-section-title">{thread.counterpart}</h5>
                                      <span className="ww-inbox-thread-meta">
                                        {thread.last_at ? new Date(thread.last_at).toLocaleString() : ""}
                                      </span>
                                    </div>
                                    <div className="ww-thread">
                                      {thread.messages.map((message) => (
                                        <div
                                          key={message.dm_id}
                                          className={`ww-thread-message ww-thread-message--${message.direction}`}
                                        >
                                          <div className="ww-thread-message-meta">
                                            <span>{message.direction === "outbound" ? "You" : thread.counterpart}</span>
                                            {message.sent_at && <span>{new Date(message.sent_at).toLocaleString()}</span>}
                                          </div>
                                          <div className="ww-inbox-body" style={{ marginTop: '0.35rem' }}>
                                            {message.body.replace(/^#[^\n]*\n/, "").trim()}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ))}
                            </div>
                          </div>
                        </div>
                      ) : playerInbox.length > 0 ? (
                        <div className="ww-inbox-list-section" style={{ marginTop: '1rem' }}>
                          <h4 className="ww-info-section-title">Your mail ({playerInbox.length})</h4>
                          <ul className="ww-inbox">
                            {playerInbox.map((letter) => (
                              <li key={letter.filename} className="ww-inbox-letter">
                                <details className="ww-inbox-details">
                                  <summary className="ww-inbox-summary" style={{ cursor: 'pointer', fontWeight: 600 }}>
                                    <span className="ww-inbox-from">
                                      {letter.filename.replace(/^from_/, "").replace(/_\d{8}-\d{6}\.md$/, "").replace(/_/g, " ")}
                                    </span>
                                  </summary>
                                  <div className="ww-inbox-body" style={{ marginTop: '0.5rem' }}>{letter.body.replace(/^#[^\n]*\n/, "").trim()}</div>
                                </details>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              )}

              {infoTab === "map" && (
                <div className="ww-info-map-tab" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div className="ww-map-tab-header">
                    <input
                      className="ww-map-search"
                      type="text"
                      placeholder="Search this area for places, tea, parks, vibes…"
                      value={mapSearch}
                      onChange={(e) => setMapSearch(e.target.value)}
                    />
                    <div className="ww-map-filter-chips">
                      {(["all", "occupied", "quiet", "landmarks"] as const).map((f) => (
                        <button
                          key={f}
                          className={`ww-map-filter-chip${mapFilter === f ? " active" : ""}`}
                          onClick={() => setMapFilter(f)}
                        >
                          {f === "all" ? "All" : f === "occupied" ? "Occupied" : f === "quiet" ? "Quiet" : "Landmarks"}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="ww-stranded-hint">
                    {mapPending
                      ? "Updating the graph for this map view…"
                      : mapSearch.trim()
                        ? `Showing matches and connected context for “${mapSearch.trim()}”.`
                        : "Pan and zoom the map to refresh what this area can reveal."}
                  </div>
                  {digest?.player_location && !mapNodes.some((n) => n.is_player) && (
                    <div className="ww-stranded-hint">
                      You are at <strong>{digest.player_location}</strong>. Click any neighborhood to travel there.
                    </div>
                  )}
                  {pendingDest && (
                    <div className="ww-move-preview" style={{ marginTop: '0.5rem' }}>
                      <span className="ww-move-preview-dest">→ {pendingDest.replace(/_/g, " ")}</span>
                      <button className="ww-move-confirm-btn" onClick={confirmRouteMove} disabled={pending}>Go</button>
                      <button className="ww-move-cancel-btn" onClick={() => setPendingDest(null)}>✕</button>
                    </div>
                  )}
                  <div className="ww-map-tab-body" style={{ flex: 1, position: 'relative', marginTop: '0.5rem' }}>
                    <LocationMap
                      nodes={mapNodes}
                      edges={mapEdges}
                      onNodeClick={!showingEntryScreen && !pending ? (name) => { handleMapNodeClick(name); } : undefined}
                      pendingDest={pendingDest}
                      pendingPath={pendingPath}
                      onViewportChange={setMapViewport}
                      searchQuery={mapSearch}
                    />
                  </div>
                </div>
              )}

              {infoTab === "presence" && (
                <PresencePanel
                  metrics={restMetrics}
                  sessionId={sessionId}
                  onRefresh={() => {
                    void refreshRestMetrics();
                  }}
                />
              )}

              {infoTab === "notes" && (
                <textarea
                  className="ww-notes-area"
                  placeholder="Your private notes…"
                  value={playerNotes}
                  onChange={(e) => {
                    setPlayerNotes(e.target.value);
                    localStorage.setItem("ww-player-notes", e.target.value);
                  }}
                />
              )}

            </div>
          </div>
        )}
      </div>

      <ErrorToastStack toasts={toasts} onDismiss={dismissToast} />

      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        sessionId={sessionId}
        onModelChanged={() => void refreshReadiness()}
        onNarrationAccessChanged={() => {
          setObserverModeMessage(null);
          void refreshReadiness();
        }}
      />

      {settingsReadiness && !settingsReadiness.ready && (
        <SetupModal
          missing={settingsReadiness.missing}
          onComplete={() => void refreshReadiness()}
        />
      )}

      {showOnboarding && (
        <OnboardingModal
          onDismiss={() => {
            setCompletedOnboarding(true);
            setShowOnboarding(false);
          }}
        />
      )}
    </div>
  );
}

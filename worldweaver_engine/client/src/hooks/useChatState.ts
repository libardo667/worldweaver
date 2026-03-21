import { useState } from "react";

import type { DMThread, InboxDM, LocationChatEntry } from "../api/wwClient";

export function useChatState() {
  const [playerInbox, setPlayerInbox] = useState<InboxDM[]>([]);
  const [playerThreads, setPlayerThreads] = useState<DMThread[]>([]);
  const [selectedThreadKey, setSelectedThreadKey] = useState<string | null>(null);
  const [agentFeed, setAgentFeed] = useState<Array<{ ts: string; displayName: string; agentAction: string | null; narrative: string | null }>>([]);
  const [chatMessages, setChatMessages] = useState<LocationChatEntry[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [chatPending, setChatPending] = useState(false);
  const [infoTab, setInfoTab] = useState<"map" | "presence" | "chats" | "notes" | "guild">("chats");
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
    () => localStorage.getItem("ww-player-notes") ?? "",
  );

  return {
    playerInbox,
    setPlayerInbox,
    playerThreads,
    setPlayerThreads,
    selectedThreadKey,
    setSelectedThreadKey,
    agentFeed,
    setAgentFeed,
    chatMessages,
    setChatMessages,
    chatInput,
    setChatInput,
    chatPending,
    setChatPending,
    infoTab,
    setInfoTab,
    chatSubTab,
    setChatSubTab,
    chatUnread,
    setChatUnread,
    cityMessages,
    setCityMessages,
    cityInput,
    setCityInput,
    cityPending,
    setCityPending,
    globalMessages,
    setGlobalMessages,
    globalInput,
    setGlobalInput,
    globalPending,
    setGlobalPending,
    playerNotes,
    setPlayerNotes,
  };
}

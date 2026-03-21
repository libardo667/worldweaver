import { useCallback, useState } from "react";

import {
  clearObserverState,
  getGuildAccessMode as loadGuildAccessMode,
  getObserverLocation,
  setGuildAccessMode as persistGuildAccessMode,
  setObserverLocation,
  type GuildAccessMode,
} from "../state/sessionStore";

export function useObserverMode() {
  const [guildAccessMode, setGuildAccessModeState] = useState<GuildAccessMode>(
    () => loadGuildAccessMode() ?? "participant",
  );
  const [observerLocation, setObserverLocationState] = useState<string>(() => getObserverLocation());
  const [entryIntent, setEntryIntent] = useState<"join" | null>(null);

  const setGuildAccessMode = useCallback((mode: GuildAccessMode) => {
    setGuildAccessModeState(mode);
    persistGuildAccessMode(mode);
  }, []);

  const setObserverLocationValue = useCallback((location: string) => {
    setObserverLocationState(location);
    setObserverLocation(location);
  }, []);

  const clearObserverShell = useCallback(() => {
    clearObserverState();
    setObserverLocationValue("");
    setEntryIntent(null);
  }, [setObserverLocationValue]);

  return {
    guildAccessMode,
    setGuildAccessMode,
    observerMode: guildAccessMode !== "participant",
    mentorBoardMode: guildAccessMode === "mentor_board",
    observerLocation,
    setObserverLocation: setObserverLocationValue,
    clearObserverShell,
    entryIntent,
    setEntryIntent,
  };
}

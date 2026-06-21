// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useCallback, useState } from "react";

import {
  clearObserverState,
  getParticipationMode as loadParticipationMode,
  getObserverLocation,
  setParticipationMode as persistParticipationMode,
  setObserverLocation,
  type ParticipationMode,
} from "../state/sessionStore";

export function useObserverMode() {
  const [participationMode, setParticipationModeState] = useState<ParticipationMode>(
    () => loadParticipationMode() ?? "participant",
  );
  const [observerLocation, setObserverLocationState] = useState<string>(() => getObserverLocation());
  const [entryIntent, setEntryIntent] = useState<"join" | null>(null);

  const setParticipationMode = useCallback((mode: ParticipationMode) => {
    setParticipationModeState(mode);
    persistParticipationMode(mode);
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
    participationMode,
    setParticipationMode,
    observerMode: participationMode !== "participant",
    observerLocation,
    setObserverLocation: setObserverLocationValue,
    clearObserverShell,
    entryIntent,
    setEntryIntent,
  };
}

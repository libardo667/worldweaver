import { useCallback, useMemo, useState } from "react";

import { getGuildBoard } from "../api/wwClient";
import { getJwt } from "../state/sessionStore";
import type { GuildBoardResponse } from "../types";

export function useGuildState() {
  const [guildBoard, setGuildBoard] = useState<GuildBoardResponse | null>(null);
  const [guildBoardError, setGuildBoardError] = useState<string | null>(null);
  const [guildBoardPending, setGuildBoardPending] = useState(false);

  const refreshGuildBoard = useCallback(async () => {
    if (!getJwt()) {
      setGuildBoard(null);
      setGuildBoardError(null);
      return;
    }
    try {
      const payload = await getGuildBoard();
      setGuildBoard(payload);
      setGuildBoardError(null);
    } catch (err) {
      setGuildBoardError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const canUseMentorBoard = useMemo(
    () =>
      Boolean(guildBoard?.me?.capabilities?.can_assign_quests) ||
      Boolean(guildBoard?.me?.capabilities?.can_manage_roles) ||
      Boolean(guildBoard?.me?.capabilities?.can_bootstrap_steward),
    [guildBoard],
  );

  return {
    guildBoard,
    setGuildBoard,
    guildBoardError,
    setGuildBoardError,
    guildBoardPending,
    setGuildBoardPending,
    refreshGuildBoard,
    canUseMentorBoard,
  };
}

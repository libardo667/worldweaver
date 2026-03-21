import { useCallback, useState } from "react";

import { getSessionGuildQuests } from "../api/wwClient";
import type { GuildQuestRecord } from "../types";

type UseQuestStateArgs = {
  observerMode: boolean;
  sessionId: string;
};

export function useQuestState({ observerMode, sessionId }: UseQuestStateArgs) {
  const [guildQuests, setGuildQuests] = useState<GuildQuestRecord[]>([]);
  const [guildQuestsError, setGuildQuestsError] = useState<string | null>(null);
  const [guildQuestsPending, setGuildQuestsPending] = useState(false);

  const refreshGuildQuests = useCallback(async () => {
    if (observerMode || !sessionId) {
      setGuildQuests([]);
      setGuildQuestsError(null);
      return;
    }
    setGuildQuestsPending(true);
    try {
      const payload = await getSessionGuildQuests(sessionId, { limit: 80 });
      setGuildQuests(payload.quests ?? []);
      setGuildQuestsError(null);
    } catch (err) {
      setGuildQuestsError(err instanceof Error ? err.message : String(err));
    } finally {
      setGuildQuestsPending(false);
    }
  }, [observerMode, sessionId]);

  return {
    guildQuests,
    setGuildQuests,
    guildQuestsError,
    setGuildQuestsError,
    guildQuestsPending,
    setGuildQuestsPending,
    refreshGuildQuests,
  };
}

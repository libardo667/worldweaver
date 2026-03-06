import { useMemo } from "react";

import type { ModeRouterPayload } from "../components/ModeRouter";
import {
  normalizeExploreModePayload,
  type ExploreModePayload,
} from "../components/exploreModePayload";

export type UseModeRouterPayloadArgs = {
  explore: ExploreModePayload;
  reflect: ModeRouterPayload["reflect"];
  create: ModeRouterPayload["create"];
  constellation: ModeRouterPayload["constellation"];
};

export function useModeRouterPayload({
  explore,
  reflect,
  create,
  constellation,
}: UseModeRouterPayloadArgs): ModeRouterPayload {
  return useMemo(
    () => ({
      explore: normalizeExploreModePayload(explore),
      reflect,
      create,
      constellation,
    }),
    [explore, reflect, create, constellation],
  );
}

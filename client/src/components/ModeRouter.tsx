import type { ClientMode } from "../app/appHelpers";
import { ExploreMode } from "./ExploreMode";
import {
  ConstellationView,
  type ConstellationViewProps,
} from "../views/ConstellationView";
import { CreateView, type CreateViewProps } from "../views/CreateView";
import { ReflectView, type ReflectViewProps } from "../views/ReflectView";
import type { ExploreModePayload } from "./exploreModePayload";

export type ModeRouterPayload = {
  explore: ExploreModePayload;
  reflect: ReflectViewProps;
  create: CreateViewProps;
  constellation: ConstellationViewProps;
};

type ModeRouterProps = {
  mode: ClientMode;
  payload: ModeRouterPayload;
};

export function ModeRouter({ mode, payload }: ModeRouterProps) {
  if (mode === "explore") {
    return <ExploreMode payload={payload.explore} />;
  }
  if (mode === "reflect") {
    return <ReflectView {...payload.reflect} />;
  }
  if (mode === "create") {
    return <CreateView {...payload.create} />;
  }
  return <ConstellationView {...payload.constellation} />;
}

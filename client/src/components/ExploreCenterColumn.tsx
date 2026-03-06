import type { ChangeItem } from "../types";
import {
  PlayerHintPanel,
  type PlayerHintPanelProps,
} from "./PlayerHintPanel";
import {
  SceneLanePanel,
  type SceneLanePanelProps,
} from "./SceneLanePanel";
import { WhatChangedStrip } from "./WhatChangedStrip";

type ExploreCenterColumnProps = {
  sceneLane: SceneLanePanelProps;
  playerHintLane: PlayerHintPanelProps;
  changes: ChangeItem[];
};

export function ExploreCenterColumn({
  sceneLane,
  playerHintLane,
  changes,
}: ExploreCenterColumnProps) {
  return (
    <section className="center-column">
      <SceneLanePanel {...sceneLane} />
      <PlayerHintPanel {...playerHintLane} />
      <WhatChangedStrip
        changes={changes}
        pending={sceneLane.anyPending}
        phase={sceneLane.turnPhase}
      />
    </section>
  );
}

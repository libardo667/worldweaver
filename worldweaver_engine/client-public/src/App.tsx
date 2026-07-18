// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { getShardExperience } from "./api/ww";
import type { ShardExperience } from "./api/types";
import { useGrounding } from "./hooks/useGrounding";

export function App() {
  const [experience, setExperience] = useState<ShardExperience | null>(null);
  const atmosphere = useGrounding();

  useEffect(() => {
    getShardExperience().then(setExperience).catch(() => setExperience(null));
  }, []);

  return (
    <div className="app-shell">
      <div style={{ padding: "2rem", fontFamily: "var(--font-display)" }}>
        <h1>{experience?.entry_disclosure?.title ?? "WorldWeaver"}</h1>
        <p>{atmosphere.grounding?.datetime_str} — {atmosphere.grounding?.weather_description}</p>
        <p>phase: {atmosphere.phase}{atmosphere.hazy ? ", hazy" : ""}</p>
      </div>
    </div>
  );
}

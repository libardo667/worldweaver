// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useState } from "react";
import { getGrounding } from "../api/ww";
import type { Grounding } from "../api/types";
import { usePoll } from "./usePoll";

export type SkyPhase = "morning" | "afternoon" | "evening" | "night";

export type Atmosphere = {
  grounding: Grounding | null;
  phase: SkyPhase;
  /** True when the weather reads foggy/cloudy/rainy enough to haze the map. */
  hazy: boolean;
};

function phaseOf(grounding: Grounding | null): SkyPhase {
  const raw = String(grounding?.time_of_day ?? "").toLowerCase();
  if (raw === "morning" || raw === "afternoon" || raw === "evening" || raw === "night") return raw;
  return "afternoon";
}

function hazeOf(grounding: Grounding | null): boolean {
  const weather = `${grounding?.weather ?? ""} ${grounding?.weather_description ?? ""}`.toLowerCase();
  return /fog|mist|overcast|cloud|drizzle|rain/.test(weather);
}

/** Real-world time and weather for the shard's city, refreshed every 5 minutes. */
export function useGrounding(): Atmosphere {
  const [grounding, setGrounding] = useState<Grounding | null>(null);

  usePoll(async () => {
    try {
      setGrounding(await getGrounding());
    } catch {
      // Grounding is ambience: keep the last reading (or none) on failure.
    }
  }, 5 * 60_000);

  return { grounding, phase: phaseOf(grounding), hazy: hazeOf(grounding) };
}

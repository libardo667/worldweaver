// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

// Participant identity, persisted per browser. Spectating needs none of this.

import { currentShardBase, currentShardScope } from "../api/base";

const JWT_KEY = "ww.public.jwt";
const PLAYER_KEY = "ww.public.player";
const SESSION_KEY = "ww.public.session_id";
const PLACE_KEY = "ww.public.place";
const DEPARTURE_KEY = "ww.public.pending_departure";

function localKey(key: string): string {
  return `${key}.${currentShardScope().replace(/^\//, "")}`;
}

function getLocalValue(key: string): string | null {
  const scoped = localStorage.getItem(localKey(key));
  if (scoped) return scoped;
  // Carry the pre-prefix session into the configured default shard once.
  if (!currentShardBase()) {
    const legacy = localStorage.getItem(key);
    if (legacy) {
      localStorage.setItem(localKey(key), legacy);
      return legacy;
    }
  }
  return null;
}

export type PlayerIdentity = {
  actor_id: string;
  player_id: string;
  username: string;
  email: string;
  display_name: string;
};

export type PendingDeparture = {
  travel_id: string;
  destination_client_url: string;
};

export function getJwt(): string | null {
  return localStorage.getItem(JWT_KEY);
}

export function setJwt(token: string): void {
  localStorage.setItem(JWT_KEY, token);
}

export function getPlayer(): PlayerIdentity | null {
  try {
    const raw = localStorage.getItem(PLAYER_KEY);
    return raw ? (JSON.parse(raw) as PlayerIdentity) : null;
  } catch {
    return null;
  }
}

export function setPlayer(player: PlayerIdentity): void {
  localStorage.setItem(PLAYER_KEY, JSON.stringify(player));
}

export function getSessionId(): string | null {
  return getLocalValue(SESSION_KEY);
}

export function mintSessionId(): string {
  const id = `ww-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  setSessionId(id);
  return id;
}

export function setSessionId(sessionId: string): void {
  localStorage.setItem(localKey(SESSION_KEY), sessionId);
}

export function getStandingPlace(): string | null {
  return getLocalValue(PLACE_KEY);
}

export function setStandingPlace(place: string): void {
  localStorage.setItem(localKey(PLACE_KEY), place);
}

export function clearLocalIncarnation(): void {
  localStorage.removeItem(localKey(SESSION_KEY));
  localStorage.removeItem(localKey(PLACE_KEY));
}

export function getPendingDeparture(): PendingDeparture | null {
  try {
    const raw = localStorage.getItem(localKey(DEPARTURE_KEY));
    return raw ? (JSON.parse(raw) as PendingDeparture) : null;
  } catch {
    return null;
  }
}

export function setPendingDeparture(pending: PendingDeparture): void {
  localStorage.setItem(localKey(DEPARTURE_KEY), JSON.stringify(pending));
}

export function clearPendingDeparture(): void {
  localStorage.removeItem(localKey(DEPARTURE_KEY));
}

export function clearParticipant(): void {
  localStorage.removeItem(JWT_KEY);
  localStorage.removeItem(PLAYER_KEY);
  clearLocalIncarnation();
  clearPendingDeparture();
  if (!currentShardBase()) {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(PLACE_KEY);
  }
}

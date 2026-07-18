// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

// Participant identity, persisted per browser. Spectating needs none of this.

const JWT_KEY = "ww.public.jwt";
const PLAYER_KEY = "ww.public.player";
const SESSION_KEY = "ww.public.session_id";
const PLACE_KEY = "ww.public.place";

export type PlayerIdentity = {
  actor_id: string;
  player_id: string;
  username: string;
  display_name: string;
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
  return localStorage.getItem(SESSION_KEY);
}

export function mintSessionId(): string {
  const id = `ww-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  localStorage.setItem(SESSION_KEY, id);
  return id;
}

export function getStandingPlace(): string | null {
  return localStorage.getItem(PLACE_KEY);
}

export function setStandingPlace(place: string): void {
  localStorage.setItem(PLACE_KEY, place);
}

export function clearParticipant(): void {
  localStorage.removeItem(JWT_KEY);
  localStorage.removeItem(PLAYER_KEY);
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(PLACE_KEY);
}

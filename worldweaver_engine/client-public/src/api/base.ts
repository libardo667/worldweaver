// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

/**
 * One public client can serve several local or reverse-proxied shards. A URL
 * such as /ww-sfo/place/embarcadero keeps all of that city's API traffic under
 * /ww-sfo/api while the unprefixed root still uses the selected default shard.
 */
export function currentShardBase(pathname = window.location.pathname): string {
  const match = pathname.match(/^\/(ww-[a-z0-9-]+)(?:\/|$)/i);
  return match ? `/${match[1]}` : "";
}

export function localShardPath(path: string): string {
  if (!path.startsWith("/api") && path !== "/health") return path;
  return `${currentShardBase()}${path}`;
}

export function currentShardScope(): string {
  const base = currentShardBase();
  const runtimeDefault = window.__WORLDWEAVER_RUNTIME__?.defaultShardPrefix;
  const configuredDefault = String(
    runtimeDefault ?? import.meta.env.VITE_DEFAULT_SHARD_PREFIX ?? "",
  ).trim();
  return base || configuredDefault || "/default";
}

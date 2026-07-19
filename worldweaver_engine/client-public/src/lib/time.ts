// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

/** "3m ago" / "2h ago" / "just now" for chat timestamps. */
export function timeAgo(ts: string | null): string {
  if (!ts) return "";
  const then = Date.parse(ts.endsWith("Z") || ts.includes("+") ? ts : `${ts}Z`);
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

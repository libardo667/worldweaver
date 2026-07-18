// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef } from "react";

/**
 * Run `fn` immediately and then every `intervalMs`, pausing while the tab is
 * hidden (and catching up on return). `fn` is kept in a ref so callers can
 * pass fresh closures without resetting the interval. Pass a null interval to
 * disable the poll entirely.
 */
export function usePoll(fn: () => void | Promise<void>, intervalMs: number | null): void {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (intervalMs === null) return;
    let cancelled = false;

    const tick = () => {
      if (cancelled || document.hidden) return;
      void fnRef.current();
    };

    tick();
    const interval = setInterval(tick, intervalMs);
    const onVisible = () => {
      if (!document.hidden) tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs]);
}

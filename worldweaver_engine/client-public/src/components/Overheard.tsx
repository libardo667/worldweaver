// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useRef, useState } from "react";
import { getLocationChat } from "../api/ww";
import type { ChatMessage } from "../api/types";
import { usePoll } from "../hooks/usePoll";
import { timeAgo } from "../lib/time";

/**
 * The read-only stream of what's being said at this place. Sessionless: the
 * engine sends display names and words only, no speaker ids.
 */
export function Overheard({ location }: { location: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  usePoll(async () => {
    try {
      const result = await getLocationChat(location, undefined, 30);
      setMessages(result.messages ?? []);
    } catch {
      // Keep what we heard last.
    } finally {
      setLoaded(true);
    }
  }, 5_000);

  useEffect(() => {
    setMessages([]);
    setLoaded(false);
  }, [location]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (!loaded && messages.length === 0) return null;

  return (
    <section className="place-section">
      <h3 className="place-section-title">Overheard</h3>
      {messages.length === 0 ? (
        <p className="place-empty">Quiet at the moment. Quiet does not mean empty.</p>
      ) : (
        <div className="overheard-scroll" ref={scrollRef}>
          {messages.map((m) => (
            <div key={m.id} className="overheard-line">
              <span className="overheard-speaker">{m.display_name || "someone"}</span>
              <span className="overheard-text">{m.message}</span>
              <span className="overheard-when">{timeAgo(m.ts)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

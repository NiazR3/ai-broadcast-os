import { useEffect, useRef, useState } from "react";
import type { BroadcastEvent } from "../lib/api";

const WS_BASE = import.meta.env.VITE_WS_BASE || "ws://localhost:8100";

export function useWebSocket() {
  const [events, setEvents] = useState<BroadcastEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/broadcast/ws`);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      try {
        const event: BroadcastEvent = JSON.parse(msg.data);
        setEvents((prev) => [event, ...prev].slice(0, 100)); // keep last 100
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      // Auto-reconnect after 3s
      setTimeout(() => {
        setEvents((prev) => [...prev]);
      }, 3000);
    };

    return () => ws.close();
  }, []);

  return { events, lastEvent: events[0] ?? null };
}

import { useEffect, useRef, useState } from "react";
import type { BroadcastEvent } from "../lib/api";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "";
const RECONNECT_DELAY = 3000;

interface UseWebSocketReturn {
  events: BroadcastEvent[];
  lastEvent: BroadcastEvent | null;
}

export function useWebSocket(): UseWebSocketReturn {
  const [events, setEvents] = useState<BroadcastEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;

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
        wsRef.current = null;
        if (!cancelled) {
          timerRef.current = setTimeout(connect, RECONNECT_DELAY);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return { events, lastEvent: events[0] ?? null };
}

/**
 * Authenticated WebSocket hook with exponential-backoff reconnect.
 * The access token is sent in the URL query string at upgrade time.
 */
import { useEffect, useRef } from "react";

import { useAuthStore } from "@/store/auth-store";
import type { WSEvent } from "@/types";

interface UseWebSocketOptions {
  url: string;
  onMessage: (event: WSEvent) => void;
  enabled?: boolean;
}

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL ??
  (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
    /^http/,
    "ws"
  );

export function useWebSocket({ url, onMessage, enabled = true }: UseWebSocketOptions) {
  const onMessageRef = useRef(onMessage);
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const closedByCallerRef = useRef(false);

  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled) return;
    closedByCallerRef.current = false;

    const connect = () => {
      const token = useAuthStore.getState().accessToken;
      const fullUrl = `${WS_BASE_URL}${url}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
      const ws = new WebSocket(fullUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25_000);
      };

      ws.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data) as WSEvent;
          onMessageRef.current(parsed);
        } catch {
          // ignore malformed
        }
      };

      ws.onclose = () => {
        if (heartbeatRef.current) clearInterval(heartbeatRef.current);
        if (closedByCallerRef.current) return;
        const attempt = reconnectAttemptsRef.current++;
        const delay = Math.min(30_000, 500 * 2 ** attempt);
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      closedByCallerRef.current = true;
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      wsRef.current?.close();
    };
  }, [url, enabled]);

  const sendMessage = (msg: object): void => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  };

  return { sendMessage };
}

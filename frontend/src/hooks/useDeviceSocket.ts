import { useEffect, useRef, useCallback } from "react";

type MessageHandler = (event: Record<string, unknown>) => void;

const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const MAX_RETRIES = 10;
const BASE_DELAY_MS = 1000;

/**
 * Connects to ws://.../devices/ws/{deviceId} and calls onMessage for each event.
 * Reconnects automatically with exponential backoff if the connection drops.
 */
export function useDeviceSocket(deviceId: number | null, onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!deviceId) return;

    const ws = new WebSocket(`${WS_BASE}/devices/ws/${deviceId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      retryRef.current = 0; // reset backoff on successful connection
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessageRef.current(data);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (retryRef.current >= MAX_RETRIES) return;
      const delay = BASE_DELAY_MS * 2 ** retryRef.current;
      retryRef.current += 1;
      timeoutRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [deviceId]);

  useEffect(() => {
    connect();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      wsRef.current?.close();
    };
  }, [connect]);
}

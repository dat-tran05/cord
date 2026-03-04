"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/events";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const OFFLINE_GRACE_MS = 3000; // Don't flash "Offline" for brief disconnects (e.g. reload)

interface WSEvent {
  event: string;
  [key: string]: any;
}

export function useWebSocket() {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const offlineTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        // Cancel pending offline transition
        if (offlineTimerRef.current) {
          clearTimeout(offlineTimerRef.current);
          offlineTimerRef.current = null;
        }
        setConnected(true);
      };

      ws.onclose = () => {
        // Delay showing "Offline" so brief reconnects don't flicker
        if (!offlineTimerRef.current) {
          offlineTimerRef.current = setTimeout(() => {
            offlineTimerRef.current = null;
            setConnected(false);
          }, OFFLINE_GRACE_MS);
        }
        if (unmountedRef.current) return;
        const delay = Math.min(RECONNECT_BASE_MS * 2 ** retryRef.current, RECONNECT_MAX_MS);
        retryRef.current++;
        timerRef.current = setTimeout(connect, delay);
      };

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data) as WSEvent;
        setEvents((prev) => [...prev.slice(-100), data]);
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (offlineTimerRef.current) clearTimeout(offlineTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}

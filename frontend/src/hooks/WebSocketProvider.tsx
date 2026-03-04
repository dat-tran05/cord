"use client";
import { createContext, useContext } from "react";
import { useWebSocket as useWebSocketHook } from "./useWebSocket";

type WebSocketState = ReturnType<typeof useWebSocketHook>;

const WebSocketContext = createContext<WebSocketState | null>(null);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const ws = useWebSocketHook();
  return (
    <WebSocketContext.Provider value={ws}>{children}</WebSocketContext.Provider>
  );
}

export function useWS(): WebSocketState {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error("useWS must be used within WebSocketProvider");
  return ctx;
}

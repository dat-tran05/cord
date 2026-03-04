"use client";
import { WebSocketProvider } from "@/hooks/WebSocketProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

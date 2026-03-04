"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Mic, MicOff, PhoneOff, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useVoiceChat } from "@/hooks/useVoiceChat";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface VoiceChatProps {
  callId: string;
  targetProfile: Record<string, unknown>;
  onEnd?: () => void;
}

export function VoiceChat({ callId, targetProfile, onEnd }: VoiceChatProps) {
  const router = useRouter();
  const {
    connected,
    error,
    transcript,
    micActive,
    toggleMic,
    sendText,
    start,
    stop,
  } = useVoiceChat(callId);

  const [input, setInput] = useState("");
  const [ended, setEnded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);
  const endedRef = useRef(false);

  useEffect(() => {
    if (connected && !startedRef.current) {
      startedRef.current = true;
      start(targetProfile);
    }
  }, [connected, start, targetProfile]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleSend = () => {
    if (!input.trim() || ended) return;
    sendText(input.trim());
    setInput("");
  };

  const endCall = async () => {
    if (endedRef.current) return;
    endedRef.current = true;
    stop(); // sends "stop" over WS to halt audio
    setEnded(true);
    try {
      await api.calls.end(callId); // awaits DB write + enqueues analysis
    } catch {
      // WS finally block may have already ended the call — that's fine
    }
  };

  const handleEnd = async () => {
    await endCall();
    onEnd?.();
    router.push(`/calls/${callId}`);
  };

  const handleBackArrow = async () => {
    await endCall();
    router.push("/calls");
  };

  useEffect(() => {
    return () => {
      // Component unmounting — end the call if still active
      if (!endedRef.current) {
        stop();
        // Fire-and-forget since we're unmounting
        api.calls.end(callId).catch(() => {});
      }
    };
  }, [callId, stop]);

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border/60 bg-background/80 backdrop-blur-lg px-4 h-14">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon-sm" onClick={handleBackArrow}>
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-sm font-semibold">Voice Call</h1>
          <span
            className={cn(
              "size-2 rounded-full",
              connected ? "bg-green-500 animate-pulse" : "bg-red-500"
            )}
            title={connected ? "Connected" : "Disconnected"}
          />
        </div>
        {!ended && (
          <Button variant="destructive" size="sm" onClick={handleEnd}>
            <PhoneOff className="size-3.5" />
            End Call
          </Button>
        )}
      </header>

      {/* Error banner */}
      {error && (
        <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {transcript.length === 0 && !ended && (
            <p className="text-center text-sm text-muted-foreground pt-12">
              {connected
                ? "Waiting for conversation to begin..."
                : "Connecting to voice service..."}
            </p>
          )}
          {transcript.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                msg.role === "agent" ? "justify-start" : "justify-end"
              )}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === "agent"
                    ? "bg-card text-card-foreground border border-border/50"
                    : "bg-primary text-primary-foreground"
                )}
              >
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Controls */}
      {!ended && (
        <div className="border-t border-border/60 bg-background/80 backdrop-blur-lg p-4">
          <div className="mx-auto flex max-w-2xl items-center gap-2">
            {/* Mic toggle */}
            <Button
              variant={micActive ? "destructive" : "outline"}
              size="icon"
              onClick={toggleMic}
              className={cn(
                "shrink-0 transition-shadow",
                micActive && "shadow-[0_0_16px_rgba(239,68,68,0.3)]"
              )}
              title={micActive ? "Mute microphone" : "Unmute microphone"}
            >
              {micActive ? (
                <Mic className="size-4" />
              ) : (
                <MicOff className="size-4" />
              )}
            </Button>

            {/* Text input */}
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type a message..."
              className="flex-1"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim()}
              size="icon"
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

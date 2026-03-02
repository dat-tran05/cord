"use client";
import { useEffect, useRef, useState } from "react";
import { useVoiceChat } from "@/hooks/useVoiceChat";

const STAGE_COLORS: Record<string, string> = {
  pre_call: "bg-zinc-700",
  intro: "bg-blue-900 text-blue-300",
  pitch: "bg-purple-900 text-purple-300",
  objection: "bg-orange-900 text-orange-300",
  close: "bg-green-900 text-green-300",
  logistics: "bg-cyan-900 text-cyan-300",
  wrap_up: "bg-zinc-600",
};

interface VoiceChatProps {
  callId: string;
  targetProfile: Record<string, unknown>;
  onEnd?: () => void;
}

export function VoiceChat({ callId, targetProfile, onEnd }: VoiceChatProps) {
  const {
    connected,
    error,
    transcript,
    stage,
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

  // Send start message once connected
  useEffect(() => {
    if (connected && !startedRef.current) {
      startedRef.current = true;
      start(targetProfile);
    }
  }, [connected, start, targetProfile]);

  // Auto-scroll transcript
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const handleSend = () => {
    if (!input.trim() || ended) return;
    sendText(input.trim());
    setInput("");
  };

  const handleEnd = () => {
    stop();
    setEnded(true);
    onEnd?.();
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a
            href="/"
            className="text-zinc-400 hover:text-zinc-200 text-sm"
          >
            &larr; Back
          </a>
          <h1 className="font-semibold">Call {callId}</h1>
          <span
            className={`text-xs px-2 py-0.5 rounded ${STAGE_COLORS[stage] || "bg-zinc-700"}`}
          >
            {stage}
          </span>
          {/* Connection indicator */}
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              connected ? "bg-green-500" : "bg-red-500"
            }`}
            title={connected ? "Connected" : "Disconnected"}
          />
        </div>
        {!ended && (
          <button
            onClick={handleEnd}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            End Call
          </button>
        )}
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/50 border-b border-red-800 px-4 py-2 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 && !ended && (
          <p className="text-zinc-500 text-sm text-center mt-8">
            {connected
              ? "Waiting for conversation to begin..."
              : "Connecting..."}
          </p>
        )}
        {transcript.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "agent" ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-md px-4 py-2 rounded-2xl text-sm ${
                msg.role === "agent"
                  ? "bg-zinc-800 text-zinc-100"
                  : "bg-blue-600 text-white"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!ended && (
        <div className="border-t border-zinc-800 p-4">
          <div className="flex gap-2 max-w-4xl mx-auto">
            {/* Mic toggle */}
            <button
              onClick={toggleMic}
              className={`p-2 rounded-xl border transition ${
                micActive
                  ? "bg-red-600/20 border-red-500 text-red-400 shadow-[0_0_12px_rgba(239,68,68,0.4)]"
                  : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500"
              }`}
              title={micActive ? "Mute microphone" : "Unmute microphone"}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {micActive ? (
                  <>
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" x2="12" y1="19" y2="22" />
                  </>
                ) : (
                  <>
                    <line x1="2" x2="22" y1="2" y2="22" />
                    <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
                    <path d="M5 10v2a7 7 0 0 0 12 0" />
                    <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
                    <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
                    <line x1="12" x2="12" y1="19" y2="22" />
                  </>
                )}
              </svg>
            </button>

            {/* Text input */}
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type a message..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-xl text-sm font-medium hover:bg-zinc-200 transition disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

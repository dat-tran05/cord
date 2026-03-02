"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, type CallDetail } from "@/lib/api";
import { VoiceChat } from "@/components/VoiceChat";

const STAGE_COLORS: Record<string, string> = {
  pre_call: "bg-zinc-700",
  intro: "bg-blue-900 text-blue-300",
  pitch: "bg-purple-900 text-purple-300",
  objection: "bg-orange-900 text-orange-300",
  close: "bg-green-900 text-green-300",
  logistics: "bg-cyan-900 text-cyan-300",
  wrap_up: "bg-zinc-600",
};

function TextCallView({ call, id }: { call: CallDetail; id: string }) {
  const [localCall, setLocalCall] = useState(call);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLocalCall(call);
  }, [call]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [localCall.transcript]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    const message = input;
    setInput("");

    setLocalCall((prev) => ({
      ...prev,
      transcript: [...prev.transcript, { role: "student", content: message }],
    }));

    try {
      const result = await api.calls.sendText(id, message);
      setLocalCall((prev) => ({
        ...prev,
        stage: result.stage,
        transcript: [
          ...prev.transcript,
          { role: "agent", content: result.response },
        ],
      }));
    } catch {
      setLocalCall((prev) => ({
        ...prev,
        transcript: [
          ...prev.transcript,
          { role: "agent", content: "[Error: failed to get response]" },
        ],
      }));
    } finally {
      setSending(false);
    }
  };

  const endCall = async () => {
    await api.calls.end(id);
    setLocalCall((prev) => ({ ...prev, is_active: false }));
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      <header className="border-b border-zinc-800 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/" className="text-zinc-400 hover:text-zinc-200 text-sm">
            &larr; Back
          </a>
          <h1 className="font-semibold">Call {localCall.call_id}</h1>
          <span
            className={`text-xs px-2 py-0.5 rounded ${STAGE_COLORS[localCall.stage] || "bg-zinc-700"}`}
          >
            {localCall.stage}
          </span>
        </div>
        {localCall.is_active && (
          <button
            onClick={endCall}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            End Call
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {localCall.transcript.map((msg, i) => (
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
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {localCall.is_active && (
        <div className="border-t border-zinc-800 p-4">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Type as the student..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-xl text-sm font-medium hover:bg-zinc-200 transition disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    // Check URL param first, then fetch call data
    const urlMode = searchParams.get("mode");
    if (urlMode) {
      setMode(urlMode);
    }
    api.calls
      .get(id)
      .then((data) => {
        setCall(data);
        // If mode not set by URL param, infer from call data
        if (!urlMode) {
          setMode((data as CallDetail & { mode?: string }).mode || "text");
        }
      })
      .catch(() => {});
  }, [id, searchParams]);

  if (!call || !mode) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
        Loading...
      </div>
    );
  }

  if (mode === "browser") {
    return <VoiceChat callId={id} targetProfile={{}} />;
  }

  return <TextCallView call={call} id={id} />;
}

"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, PhoneOff, Send } from "lucide-react";
import Link from "next/link";
import { api, type CallDetail } from "@/lib/api";
import { VoiceChat } from "@/components/VoiceChat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STAGE_STYLES: Record<string, string> = {
  pre_call: "bg-muted text-muted-foreground",
  intro: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  pitch: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  objection: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  close: "bg-green-500/15 text-green-400 border-green-500/20",
  logistics: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
  wrap_up: "bg-muted text-muted-foreground",
};

function StageBadge({ stage }: { stage: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("capitalize", STAGE_STYLES[stage] || "")}
    >
      {stage.replace("_", " ")}
    </Badge>
  );
}

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
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border/60 bg-background/80 backdrop-blur-lg px-4 h-14">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="icon-sm">
              <ArrowLeft className="size-4" />
            </Button>
          </Link>
          <h1 className="text-sm font-semibold">Call</h1>
          <StageBadge stage={localCall.stage} />
        </div>
        <div className="flex items-center gap-2">
          {localCall.is_active ? (
            <Button variant="destructive" size="sm" onClick={endCall}>
              <PhoneOff className="size-3.5" />
              End Call
            </Button>
          ) : (
            <Link href={`/calls/${id}/analysis`}>
              <Button variant="outline" size="sm">
                View Analysis
              </Button>
            </Link>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {localCall.transcript.length === 0 && (
            <p className="text-center text-sm text-muted-foreground pt-12">
              Start the conversation by typing below.
            </p>
          )}
          {localCall.transcript.map((msg, i) => (
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
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      {localCall.is_active && (
        <div className="border-t border-border/60 bg-background/80 backdrop-blur-lg p-4">
          <div className="mx-auto flex max-w-2xl gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Type as the student..."
              className="flex-1"
              disabled={sending}
            />
            <Button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
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

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const urlMode = searchParams.get("mode");
    if (urlMode) {
      setMode(urlMode);
    }
    api.calls
      .get(id)
      .then((data) => {
        setCall(data);
        if (!urlMode) {
          setMode(
            (data as CallDetail & { mode?: string }).mode || "text"
          );
        }
      })
      .catch(() => {});
  }, [id, searchParams]);

  if (!call || !mode) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading call...</p>
        </div>
      </div>
    );
  }

  if (mode === "browser") {
    return <VoiceChat callId={id} targetProfile={{}} />;
  }

  return <TextCallView call={call} id={id} />;
}

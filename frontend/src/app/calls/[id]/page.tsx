"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, PhoneOff } from "lucide-react";
import Link from "next/link";
import { api, type CallDetail } from "@/lib/api";
import { VoiceChat } from "@/components/VoiceChat";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function CallTranscriptView({ call, id }: { call: CallDetail; id: string }) {
  const [localCall, setLocalCall] = useState(call);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLocalCall(call);
  }, [call]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [localCall.transcript]);

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
          {localCall.is_active && (
            <Badge variant="outline" className="bg-green-500/15 text-green-400 border-green-500/20">
              Live
            </Badge>
          )}
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
              Waiting for conversation to start...
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

  return <CallTranscriptView call={call} id={id} />;
}

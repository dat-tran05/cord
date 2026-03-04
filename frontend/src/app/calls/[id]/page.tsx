"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, BarChart3 } from "lucide-react";
import Link from "next/link";
import { api, type CallDetail } from "@/lib/api";
import { VoiceChat } from "@/components/VoiceChat";
import { AnalyticsSheet } from "@/components/AnalyticsSheet";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function TranscriptView({ call }: { call: CallDetail }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call.transcript]);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Sub-header */}
      <div className="border-b border-border/60 bg-background">
        <div className="mx-auto flex h-12 max-w-6xl items-center gap-3 px-6">
          <Link href="/calls">
            <Button variant="ghost" size="icon-sm">
              <ArrowLeft className="size-4" />
            </Button>
          </Link>
          <h1 className="text-sm font-semibold">{call.target_name}</h1>
          {call.is_active ? (
            <Badge
              variant="outline"
              className="bg-green-500/15 text-green-400 border-green-500/20"
            >
              Active
            </Badge>
          ) : (
            <Badge variant="secondary">Ended</Badge>
          )}
          <div className="ml-auto">
            {!call.is_active && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSheetOpen(true)}
              >
                <BarChart3 className="size-3.5" />
                Analytics
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Transcript */}
      <div className="mx-auto max-w-2xl px-4 py-6">
        <div className="space-y-4">
          {call.transcript.length === 0 ? (
            <div className="flex flex-col items-center gap-2 pt-16">
              <p className="text-sm text-muted-foreground">
                No conversation was recorded for this call.
              </p>
              {!call.is_active && (
                <p className="text-xs text-muted-foreground/60">
                  The call may have ended before any audio was exchanged.
                </p>
              )}
            </div>
          ) : (
            call.transcript.map((msg, i) => (
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
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <AnalyticsSheet
        callId={call.call_id}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  );
}

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = useState<CallDetail | null>(null);

  useEffect(() => {
    if (!id) return;
    api.calls
      .get(id)
      .then(setCall)
      .catch(() => {});
  }, [id]);

  if (!call) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading call...</p>
        </div>
      </div>
    );
  }

  // Active browser call: show VoiceChat
  if (call.is_active && call.mode === "browser") {
    return <VoiceChat callId={id} targetProfile={{}} />;
  }

  // Everything else: transcript view with analytics
  return <TranscriptView call={call} />;
}

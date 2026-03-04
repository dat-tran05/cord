"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MessageSquare, Mic, PhoneCall } from "lucide-react";
import { api, type Call } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;

  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function CallsPage() {
  const router = useRouter();
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.calls
      .list()
      .then(setCalls)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="mx-auto max-w-6xl space-y-6 p-6">
        <div className="flex items-center gap-2">
          <PhoneCall className="size-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Calls</h2>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : calls.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16">
              <PhoneCall className="mb-3 size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No calls yet</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="divide-y divide-border p-0">
              {calls.map((call) => (
                <button
                  key={call.call_id}
                  onClick={() => router.push(`/calls/${call.call_id}`)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
                >
                  {/* Mode icon */}
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    {call.mode === "browser" ? (
                      <Mic className="size-3.5 text-muted-foreground" />
                    ) : (
                      <MessageSquare className="size-3.5 text-muted-foreground" />
                    )}
                  </div>

                  {/* Target name */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {call.target_name}
                    </p>
                  </div>

                  {/* Analysis status badge */}
                  {call.analysis_status === "analyzing" && (
                    <Badge
                      variant="secondary"
                      className="shrink-0 flex items-center gap-1 text-[10px]"
                    >
                      <Loader2 className="size-3 animate-spin" />
                      Processing
                    </Badge>
                  )}
                  {call.analysis_status === "analyzed" && (
                    <Badge
                      variant="outline"
                      className="shrink-0 text-[10px] bg-green-500/15 text-green-400 border-green-500/20"
                    >
                      Analyzed
                    </Badge>
                  )}
                  {call.analysis_status === "failed" && (
                    <Badge
                      variant="destructive"
                      className="shrink-0 text-[10px]"
                    >
                      Failed
                    </Badge>
                  )}

                  {/* Status badge */}
                  {call.status === "active" ? (
                    <Badge
                      variant="outline"
                      className="shrink-0 bg-green-500/15 text-green-400 border-green-500/20"
                    >
                      Active
                    </Badge>
                  ) : (
                    <Badge
                      variant="secondary"
                      className="shrink-0"
                    >
                      Ended
                    </Badge>
                  )}

                  {/* Relative time */}
                  {call.created_at && (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(call.created_at)}
                    </span>
                  )}
                </button>
              ))}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

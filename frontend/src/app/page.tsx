"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Radio } from "lucide-react";
import { api, type Call, type Target } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { CallCard } from "@/components/CallCard";
import { NewCallDialog } from "@/components/NewCallDialog";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Dashboard() {
  const router = useRouter();
  const [targets, setTargets] = useState<Target[]>([]);
  const [activeCalls, setActiveCalls] = useState<Call[]>([]);
  const [showNewCall, setShowNewCall] = useState(false);
  const { events, connected } = useWebSocket();

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleNewCall = async (targetId: string, mode: string) => {
    const call = await api.calls.create({ target_id: targetId, mode });
    setActiveCalls((prev) => [...prev, call]);
    setShowNewCall(false);
    if (mode === "browser") {
      router.push(`/calls/${call.call_id}?mode=browser`);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar
        trailing={
          <>
            <Badge variant={connected ? "default" : "destructive"} className="gap-1.5">
              <span
                className={`size-1.5 rounded-full ${
                  connected ? "bg-green-400 animate-pulse" : "bg-red-400"
                }`}
              />
              {connected ? "Live" : "Offline"}
            </Badge>
            <Button size="sm" onClick={() => setShowNewCall(true)}>
              <Plus className="size-4" />
              New Call
            </Button>
          </>
        }
      />

      <main className="mx-auto max-w-6xl space-y-8 p-6">
        {/* Active Calls */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-lg font-semibold">Active Calls</h2>
            {activeCalls.length > 0 && (
              <Badge variant="secondary">{activeCalls.length}</Badge>
            )}
          </div>
          {activeCalls.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                  <Phone className="size-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                  No active calls. Start one to begin a conversation.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => setShowNewCall(true)}
                >
                  <Plus className="size-4" />
                  Start a Call
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {activeCalls.map((call) => (
                <CallCard key={call.call_id} call={call} />
              ))}
            </div>
          )}
        </section>

        {/* Events */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <Radio className="size-4 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Event Stream</h2>
          </div>
          <Card>
            <CardContent className="max-h-72 overflow-y-auto p-0">
              <div className="divide-y divide-border font-mono text-xs">
                {events.length === 0 ? (
                  <p className="px-4 py-8 text-center text-muted-foreground font-sans text-sm">
                    Waiting for events...
                  </p>
                ) : (
                  events.map((e, i) => (
                    <div
                      key={i}
                      className="flex gap-3 px-4 py-2 hover:bg-muted/50 transition-colors"
                    >
                      <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
                        {e.event}
                      </Badge>
                      <span className="truncate text-muted-foreground">
                        {JSON.stringify(e, null, 0)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      </main>

      {showNewCall && (
        <NewCallDialog
          targets={targets}
          onStart={handleNewCall}
          onClose={() => setShowNewCall(false)}
        />
      )}
    </div>
  );
}

function Phone({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}

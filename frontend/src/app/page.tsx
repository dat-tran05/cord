"use client";
import { Radio } from "lucide-react";
import { useWS } from "@/hooks/WebSocketProvider";
import { Navbar } from "@/components/Navbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export default function Dashboard() {
  const { events } = useWS();

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="mx-auto max-w-6xl space-y-8 p-6">
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
    </div>
  );
}

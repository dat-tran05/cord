"use client";
import { useEffect, useState } from "react";
import { api, type Call, type Target } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { CallCard } from "@/components/CallCard";
import { NewCallDialog } from "@/components/NewCallDialog";

export default function Dashboard() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [activeCalls, setActiveCalls] = useState<Call[]>([]);
  const [showNewCall, setShowNewCall] = useState(false);
  const { events, connected } = useWebSocket();

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleNewCall = async (targetId: string) => {
    const call = await api.calls.create({ target_id: targetId, mode: "text" });
    setActiveCalls((prev) => [...prev, call]);
    setShowNewCall(false);
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CORD</h1>
            <p className="text-zinc-400 text-sm">Voice Persuasion Agent</p>
          </div>
          <div className="flex items-center gap-4">
            <span className={`text-xs px-2 py-1 rounded ${connected ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
              {connected ? "Connected" : "Disconnected"}
            </span>
            <button
              onClick={() => setShowNewCall(true)}
              className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition"
            >
              + New Call
            </button>
          </div>
        </header>

        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4">Active Calls</h2>
          {activeCalls.length === 0 ? (
            <p className="text-zinc-500 text-sm">No active calls. Start one above.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {activeCalls.map((call) => (
                <CallCard key={call.call_id} call={call} />
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-4">Recent Events</h2>
          <div className="bg-zinc-900 rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-xs">
            {events.length === 0 ? (
              <p className="text-zinc-500">Waiting for events...</p>
            ) : (
              events.map((e, i) => (
                <div key={i} className="py-1 border-b border-zinc-800">
                  <span className="text-zinc-500">{e.event}</span>{" "}
                  <span className="text-zinc-300">{JSON.stringify(e, null, 0)}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {showNewCall && (
        <NewCallDialog
          targets={targets}
          onStart={handleNewCall}
          onClose={() => setShowNewCall(false)}
        />
      )}
    </main>
  );
}

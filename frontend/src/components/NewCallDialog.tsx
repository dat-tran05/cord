"use client";
import { useState } from "react";
import type { Target } from "@/lib/api";

interface Props {
  targets: Target[];
  onStart: (targetId: string) => void;
  onClose: () => void;
}

export function NewCallDialog({ targets, onStart, onClose }: Props) {
  const [selectedId, setSelectedId] = useState("");

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Start New Call</h2>
        {targets.length === 0 ? (
          <p className="text-zinc-400 text-sm mb-4">No targets yet. Add one on the Targets page first.</p>
        ) : (
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-2 text-sm mb-4"
          >
            <option value="">Select a target...</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.school} {t.major}
              </option>
            ))}
          </select>
        )}
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">
            Cancel
          </button>
          <button
            onClick={() => selectedId && onStart(selectedId)}
            disabled={!selectedId}
            className="bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition disabled:opacity-40"
          >
            Start Call
          </button>
        </div>
      </div>
    </div>
  );
}

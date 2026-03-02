"use client";
import Link from "next/link";
import type { Call } from "@/lib/api";

export function CallCard({ call }: { call: Call }) {
  return (
    <Link href={`/calls/${call.call_id}`}>
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-600 transition cursor-pointer">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium">{call.target_name}</h3>
          <span className="text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">
            {call.status}
          </span>
        </div>
        <p className="text-zinc-400 text-sm">Mode: {call.mode}</p>
        <p className="text-zinc-500 text-xs font-mono">{call.call_id}</p>
      </div>
    </Link>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Analysis } from "@/lib/api";

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      api.calls
        .getAnalysis(id)
        .then(setAnalysis)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, [id]);

  if (loading) return <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">Analyzing...</div>;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <a href={`/calls/${id}`} className="text-zinc-400 hover:text-zinc-200 text-sm">&larr; Back to call</a>
          <h1 className="text-2xl font-bold">Call Analysis</h1>
        </div>

        {analysis ? (
          <div className="space-y-6">
            {/* Score */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-center">
                <p className="text-zinc-400 text-sm">Effectiveness</p>
                <p className="text-4xl font-bold">{analysis.effectiveness_score}/10</p>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 text-center">
                <p className="text-zinc-400 text-sm">Objection Handling</p>
                <p className="text-4xl font-bold">{analysis.objection_handling_quality}/10</p>
              </div>
            </div>

            {/* Outcome */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Outcome</h2>
              <span className={`px-3 py-1 rounded text-sm ${analysis.outcome === "sold" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
                {analysis.outcome}
              </span>
            </div>

            {/* Sentiment Arc */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Sentiment Arc</h2>
              <p className="text-zinc-400 text-sm">{analysis.sentiment_arc}</p>
            </div>

            {/* Tactics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <h2 className="font-medium mb-2 text-green-400">Worked</h2>
                <ul className="text-sm text-zinc-300 space-y-1">
                  {analysis.tactics_that_worked.map((t, i) => <li key={i}>+ {t}</li>)}
                </ul>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <h2 className="font-medium mb-2 text-red-400">Didn't Work</h2>
                <ul className="text-sm text-zinc-300 space-y-1">
                  {analysis.tactics_that_failed.map((t, i) => <li key={i}>- {t}</li>)}
                </ul>
              </div>
            </div>

            {/* Suggestions */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="font-medium mb-2">Improvement Suggestions</h2>
              <ul className="text-sm text-zinc-300 space-y-2">
                {analysis.improvement_suggestions.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-zinc-500">{i + 1}.</span> {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : error ? (
          <div className="bg-red-950 border border-red-800 rounded-lg p-8 text-center">
            <p className="text-red-300">{error}</p>
            <p className="text-zinc-500 text-sm mt-2">Make sure the call has ended and has a transcript.</p>
          </div>
        ) : (
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 text-center">
            <p className="text-zinc-400">Analysis not yet available. End the call first, then request analysis.</p>
          </div>
        )}
      </div>
    </main>
  );
}

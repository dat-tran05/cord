"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Lightbulb,
  Target,
} from "lucide-react";
import Link from "next/link";
import { api, type Analysis } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Navbar } from "@/components/Navbar";

function ScoreRing({
  score,
  label,
}: {
  score: number;
  label: string;
}) {
  const pct = (score / 10) * 100;
  const color =
    score >= 7 ? "text-green-400" : score >= 4 ? "text-yellow-400" : "text-red-400";
  const strokeColor =
    score >= 7
      ? "stroke-green-400"
      : score >= 4
        ? "stroke-yellow-400"
        : "stroke-red-400";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative size-28">
        <svg className="size-28 -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            strokeWidth="6"
            className="stroke-muted"
          />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${pct * 2.64} 264`}
            className={strokeColor}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-2xl font-bold ${color}`}>{score}</span>
          <span className="text-xs text-muted-foreground">/10</span>
        </div>
      </div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}

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

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Analyzing call...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="mx-auto max-w-4xl space-y-6 p-6">
        <div className="flex items-center gap-3">
          <Link href={`/calls/${id}`}>
            <Button variant="ghost" size="icon-sm">
              <ArrowLeft className="size-4" />
            </Button>
          </Link>
          <h1 className="text-xl font-bold">Call Analysis</h1>
        </div>

        {analysis ? (
          <div className="space-y-6">
            {/* Scores */}
            <Card>
              <CardContent className="flex items-center justify-center gap-12 py-8">
                <ScoreRing
                  score={analysis.effectiveness_score}
                  label="Effectiveness"
                />
                <ScoreRing
                  score={analysis.objection_handling_quality}
                  label="Objection Handling"
                />
              </CardContent>
            </Card>

            {/* Outcome */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Target className="size-4" />
                  Outcome
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Badge
                  variant={analysis.outcome === "sold" ? "default" : "destructive"}
                  className="text-sm"
                >
                  {analysis.outcome === "sold" ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : (
                    <XCircle className="size-3.5" />
                  )}
                  {analysis.outcome}
                </Badge>
              </CardContent>
            </Card>

            {/* Sentiment */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <TrendingUp className="size-4" />
                  Sentiment Arc
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {analysis.sentiment_arc}
                </p>
              </CardContent>
            </Card>

            {/* Tactics */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-green-400">
                    <CheckCircle2 className="size-4" />
                    What Worked
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {analysis.tactics_that_worked.map((t, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-muted-foreground"
                      >
                        <span className="mt-1 size-1.5 shrink-0 rounded-full bg-green-500" />
                        {t}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-red-400">
                    <XCircle className="size-4" />
                    {"Didn't Work"}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {analysis.tactics_that_failed.map((t, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-muted-foreground"
                      >
                        <span className="mt-1 size-1.5 shrink-0 rounded-full bg-red-500" />
                        {t}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </div>

            {/* Suggestions */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Lightbulb className="size-4" />
                  Improvement Suggestions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-3">
                  {analysis.improvement_suggestions.map((s, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                        {i + 1}
                      </span>
                      <span className="text-muted-foreground leading-relaxed pt-0.5">
                        {s}
                      </span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          </div>
        ) : error ? (
          <Card className="border-destructive/30">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <XCircle className="mb-3 size-8 text-destructive" />
              <p className="font-medium text-destructive">{error}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Make sure the call has ended and has a transcript.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-muted-foreground">
                Analysis not yet available. End the call first, then request
                analysis.
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

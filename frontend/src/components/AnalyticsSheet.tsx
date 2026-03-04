"use client";
import { useEffect, useState } from "react";
import {
  CheckCircle2,
  XCircle,
  TrendingUp,
  Lightbulb,
  Target,
  Loader2,
} from "lucide-react";
import { api, type Analysis } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";

function ScoreRing({ score, label }: { score: number; label: string }) {
  const pct = (score / 10) * 100;
  const color =
    score >= 7
      ? "text-green-400"
      : score >= 4
        ? "text-yellow-400"
        : "text-red-400";
  const strokeColor =
    score >= 7
      ? "stroke-green-400"
      : score >= 4
        ? "stroke-yellow-400"
        : "stroke-red-400";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative size-24">
        <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
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
          <span className={`text-xl font-bold ${color}`}>{score}</span>
          <span className="text-xs text-muted-foreground">/10</span>
        </div>
      </div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}

interface AnalyticsSheetProps {
  callId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AnalyticsSheet({
  callId,
  open,
  onOpenChange,
}: AnalyticsSheetProps) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!open) {
      // Reset state when closed
      setAnalysis(null);
      setStatus(null);
      setLoading(true);
      return;
    }

    let interval: ReturnType<typeof setInterval> | null = null;

    const fetchAnalysis = () => {
      api.calls
        .getAnalysis(callId)
        .then((data) => {
          if ("status" in data && !("effectiveness_score" in data)) {
            // Status-only response
            setStatus(data.status);
            setAnalysis(null);

            // Auto-poll if analyzing
            if (data.status === "analyzing" && !interval) {
              interval = setInterval(fetchAnalysis, 3000);
            }
          } else {
            // Full analysis data
            setAnalysis(data as Analysis);
            setStatus(null);
            if (interval) {
              clearInterval(interval);
              interval = null;
            }
          }
        })
        .catch(() => {
          setStatus("failed");
        })
        .finally(() => {
          setLoading(false);
        });
    };

    fetchAnalysis();

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [open, callId]);

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="mb-3 size-6 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading analysis...</p>
        </div>
      );
    }

    if (status === "analyzing") {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="mb-3 size-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">
            Analysis in progress...
          </p>
        </div>
      );
    }

    if (status === "failed") {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <XCircle className="mb-3 size-8 text-destructive" />
          <p className="text-sm font-medium text-destructive">
            Analysis failed
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Something went wrong during analysis.
          </p>
        </div>
      );
    }

    if (status === "pending") {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <p className="text-sm text-muted-foreground">
            Analysis not started
          </p>
        </div>
      );
    }

    if (!analysis) {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <p className="text-sm text-muted-foreground">
            No analysis available.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6 overflow-y-auto">
        {/* Scores */}
        <div className="flex items-center justify-center gap-8">
          <ScoreRing
            score={analysis.effectiveness_score}
            label="Effectiveness"
          />
          <ScoreRing
            score={analysis.objection_handling_quality}
            label="Objection Handling"
          />
        </div>

        {/* Outcome */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Target className="size-4" />
            Outcome
          </div>
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
        </div>

        {/* What Worked / Didn't Work */}
        <div className="grid gap-4 grid-cols-1">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-green-400">
              <CheckCircle2 className="size-4" />
              What Worked
            </div>
            <ul className="space-y-1.5">
              {analysis.tactics_that_worked.map((t, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-muted-foreground"
                >
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-green-500" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-red-400">
              <XCircle className="size-4" />
              {"Didn't Work"}
            </div>
            <ul className="space-y-1.5">
              {analysis.tactics_that_failed.map((t, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-muted-foreground"
                >
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-red-500" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Sentiment Arc */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <TrendingUp className="size-4" />
            Sentiment Arc
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {analysis.sentiment_arc}
          </p>
        </div>

        {/* Improvement Suggestions */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Lightbulb className="size-4" />
            Improvement Suggestions
          </div>
          <ol className="space-y-2">
            {analysis.improvement_suggestions.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium">
                  {i + 1}
                </span>
                <span className="text-muted-foreground leading-relaxed pt-0.5">
                  {s}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Call Analytics</SheetTitle>
          <SheetDescription>
            Post-call AI analysis and performance metrics
          </SheetDescription>
        </SheetHeader>
        {renderContent()}
      </SheetContent>
    </Sheet>
  );
}

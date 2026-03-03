"use client";
import { useState } from "react";
import { MessageSquare, Mic, X } from "lucide-react";
import type { Target } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Props {
  targets: Target[];
  onStart: (targetId: string, mode: string) => void;
  onClose: () => void;
}

export function NewCallDialog({ targets, onStart, onClose }: Props) {
  const [selectedId, setSelectedId] = useState("");
  const [mode, setMode] = useState<"text" | "browser">("text");

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Start New Call</DialogTitle>
          <DialogDescription>
            Select a target and choose your conversation mode.
          </DialogDescription>
        </DialogHeader>

        {targets.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center">
            <p className="text-sm text-muted-foreground">
              No targets yet. Add one on the{" "}
              <a href="/targets" className="text-primary underline underline-offset-4">
                Targets page
              </a>{" "}
              first.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Target selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Target
              </label>
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                <option value="">Select a target...</option>
                {targets.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} — {t.school} {t.major}
                  </option>
                ))}
              </select>
            </div>

            {/* Mode selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Mode
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setMode("text")}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border p-4 transition-all",
                    mode === "text"
                      ? "border-primary bg-primary/5 text-foreground shadow-sm"
                      : "border-border text-muted-foreground hover:border-border/80 hover:bg-muted/50"
                  )}
                >
                  <MessageSquare
                    className={cn(
                      "size-5",
                      mode === "text" ? "text-primary" : ""
                    )}
                  />
                  <span className="text-sm font-medium">Text</span>
                  <span className="text-[11px] text-muted-foreground">
                    Type as the student
                  </span>
                </button>
                <button
                  onClick={() => setMode("browser")}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-lg border p-4 transition-all",
                    mode === "browser"
                      ? "border-primary bg-primary/5 text-foreground shadow-sm"
                      : "border-border text-muted-foreground hover:border-border/80 hover:bg-muted/50"
                  )}
                >
                  <Mic
                    className={cn(
                      "size-5",
                      mode === "browser" ? "text-primary" : ""
                    )}
                  />
                  <span className="text-sm font-medium">Voice</span>
                  <span className="text-[11px] text-muted-foreground">
                    Speak with the agent
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => selectedId && onStart(selectedId, mode)}
            disabled={!selectedId}
          >
            Start Call
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

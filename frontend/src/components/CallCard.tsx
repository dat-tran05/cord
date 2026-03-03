"use client";
import Link from "next/link";
import { PhoneCall, MessageSquare, Mic } from "lucide-react";
import type { Call } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export function CallCard({ call }: { call: Call }) {
  return (
    <Link href={`/calls/${call.call_id}`}>
      <Card className="transition-all hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 cursor-pointer">
        <CardContent className="flex items-center gap-4 py-4">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            {call.mode === "browser" ? (
              <Mic className="size-4" />
            ) : (
              <MessageSquare className="size-4" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold truncate">{call.target_name}</h3>
              <Badge variant="outline" className="shrink-0 text-[10px] capitalize">
                {call.mode === "browser" ? "Voice" : call.mode}
              </Badge>
            </div>
            <p className="text-xs font-mono text-muted-foreground truncate">
              {call.call_id}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs text-green-500 font-medium">Live</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

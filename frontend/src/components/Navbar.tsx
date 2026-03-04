"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Phone, PhoneCall, Users, LayoutDashboard, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWS } from "@/hooks/WebSocketProvider";
import { api, type Target } from "@/lib/api";
import { NewCallDialog } from "@/components/NewCallDialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/targets", label: "Targets", icon: Users },
  { href: "/calls", label: "Calls", icon: PhoneCall },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { connected } = useWS();
  const [showNewCall, setShowNewCall] = useState(false);
  const [targets, setTargets] = useState<Target[]>([]);

  const openNewCall = () => {
    api.targets.list().then(setTargets).catch(console.error);
    setShowNewCall(true);
  };

  const handleNewCall = async (targetId: string, mode: string) => {
    const call = await api.calls.create({ target_id: targetId, mode });
    setShowNewCall(false);
    if (mode === "browser") {
      router.push(`/calls/${call.call_id}?mode=browser`);
    } else {
      router.push(`/calls/${call.call_id}`);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-lg">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6">
          <Link href="/" className="flex items-center gap-2 mr-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Phone className="size-4" />
            </div>
            <span className="text-lg font-bold tracking-tight">CORD</span>
          </Link>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <Icon className="size-4" />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <Badge variant={connected ? "default" : "destructive"} className="gap-1.5">
              <span
                className={`size-1.5 rounded-full ${
                  connected ? "bg-green-400 animate-pulse" : "bg-red-400"
                }`}
              />
              {connected ? "Live" : "Offline"}
            </Badge>
            <Button size="sm" onClick={openNewCall}>
              <Plus className="size-4" />
              New Call
            </Button>
          </div>
        </div>
      </header>

      {showNewCall && (
        <NewCallDialog
          targets={targets}
          onStart={handleNewCall}
          onClose={() => setShowNewCall(false)}
        />
      )}
    </>
  );
}

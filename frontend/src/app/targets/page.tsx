"use client";
import { useEffect, useState } from "react";
import { UserPlus, GraduationCap, BookOpen, Sparkles } from "lucide-react";
import { api, type Target } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

export default function TargetsPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [form, setForm] = useState({
    name: "",
    school: "MIT",
    major: "",
    interests: "",
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!form.name.trim() || creating) return;
    setCreating(true);
    try {
      const target = await api.targets.create({
        name: form.name,
        school: form.school,
        major: form.major,
        year: "",
        interests: form.interests
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        clubs: [],
        bio: "",
      });
      setTargets((prev) => [...prev, target]);
      setForm({ name: "", school: "MIT", major: "", interests: "" });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="mx-auto max-w-4xl space-y-8 p-6">
        {/* Add Target Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserPlus className="size-5" />
              Add Target
            </CardTitle>
            <CardDescription>
              Create a new target profile to start a persuasion call.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Name
                </label>
                <Input
                  placeholder="e.g. Alex Chen"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  School
                </label>
                <Input
                  placeholder="MIT"
                  value={form.school}
                  onChange={(e) => setForm({ ...form, school: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Major
                </label>
                <Input
                  placeholder="e.g. Computer Science"
                  value={form.major}
                  onChange={(e) => setForm({ ...form, major: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Interests
                </label>
                <Input
                  placeholder="robotics, coffee, AI (comma-separated)"
                  value={form.interests}
                  onChange={(e) =>
                    setForm({ ...form, interests: e.target.value })
                  }
                />
              </div>
            </div>
            <Button
              onClick={handleCreate}
              disabled={!form.name.trim() || creating}
              className="w-full sm:w-auto"
            >
              <UserPlus className="size-4" />
              {creating ? "Adding..." : "Add Target"}
            </Button>
          </CardContent>
        </Card>

        {/* Target List */}
        <section>
          <div className="mb-4 flex items-center gap-2">
            <h2 className="text-lg font-semibold">Targets</h2>
            {targets.length > 0 && (
              <Badge variant="secondary">{targets.length}</Badge>
            )}
          </div>

          {targets.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                  <Users className="size-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                  No targets yet. Add one above to get started.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-3">
              {targets.map((t) => (
                <Card
                  key={t.id}
                  className="transition-colors hover:border-border/80"
                >
                  <CardContent className="flex items-start justify-between py-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{t.name}</h3>
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {t.id.slice(0, 8)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        {t.school && (
                          <span className="flex items-center gap-1">
                            <GraduationCap className="size-3.5" />
                            {t.school}
                          </span>
                        )}
                        {t.major && (
                          <span className="flex items-center gap-1">
                            <BookOpen className="size-3.5" />
                            {t.major}
                          </span>
                        )}
                      </div>
                      {t.interests.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {t.interests.map((interest) => (
                            <Badge
                              key={interest}
                              variant="secondary"
                              className="text-[11px]"
                            >
                              <Sparkles className="size-3" />
                              {interest}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Users({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

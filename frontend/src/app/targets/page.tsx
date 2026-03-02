"use client";
import { useEffect, useState } from "react";
import { api, type Target } from "@/lib/api";

export default function TargetsPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [form, setForm] = useState({ name: "", school: "MIT", major: "", interests: "" });

  useEffect(() => {
    api.targets.list().then(setTargets).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!form.name) return;
    const target = await api.targets.create({
      name: form.name,
      school: form.school,
      major: form.major,
      year: "",
      interests: form.interests.split(",").map((s) => s.trim()).filter(Boolean),
      clubs: [],
      bio: "",
    });
    setTargets((prev) => [...prev, target]);
    setForm({ name: "", school: "MIT", major: "", interests: "" });
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <a href="/" className="text-zinc-400 hover:text-zinc-200 text-sm">&larr; Back</a>
          <h1 className="text-2xl font-bold">Targets</h1>
        </div>

        {/* Add target form */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-8">
          <h2 className="font-medium mb-3">Add Target</h2>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="School" value={form.school} onChange={(e) => setForm({ ...form, school: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Major" value={form.major} onChange={(e) => setForm({ ...form, major: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
            <input placeholder="Interests (comma-separated)" value={form.interests} onChange={(e) => setForm({ ...form, interests: e.target.value })} className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm" />
          </div>
          <button onClick={handleCreate} className="mt-3 bg-zinc-100 text-zinc-900 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-200 transition">Add Target</button>
        </div>

        {/* Target list */}
        <div className="space-y-3">
          {targets.map((t) => (
            <div key={t.id} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{t.name}</h3>
                <span className="text-xs text-zinc-500 font-mono">{t.id}</span>
              </div>
              <p className="text-sm text-zinc-400">{t.school} — {t.major}</p>
              {t.interests.length > 0 && (
                <div className="flex gap-1 mt-2">
                  {t.interests.map((i) => (
                    <span key={i} className="text-xs bg-zinc-800 px-2 py-0.5 rounded">{i}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface Target {
  id: string;
  name: string;
  school: string;
  major: string;
  year: string;
  interests: string[];
  clubs: string[];
  bio: string;
  enrichment_status: "pending" | "enriching" | "enriched" | "failed";
  enriched_profile: {
    talking_points?: string[];
    rapport_hooks?: string[];
    personalized_pitch_angles?: string[];
    anticipated_objections?: string[];
    [key: string]: unknown;
  } | null;
}

export interface Call {
  call_id: string;
  target_id: string;
  target_name: string;
  status: string;
  mode: string;
}

export interface CallDetail {
  call_id: string;
  is_active: boolean;
  transcript: { role: string; content: string }[];
}

export const api = {
  targets: {
    list: () => fetchApi<Target[]>("/api/targets"),
    create: (data: Omit<Target, "id" | "enrichment_status" | "enriched_profile">) =>
      fetchApi<Target>("/api/targets", { method: "POST", body: JSON.stringify(data) }),
  },
  calls: {
    create: (data: { target_id: string; mode: string }) =>
      fetchApi<Call>("/api/calls", { method: "POST", body: JSON.stringify(data) }),
    get: (callId: string) => fetchApi<CallDetail>(`/api/calls/${callId}`),
    end: (callId: string) =>
      fetchApi<{ status: string; transcript: any[] }>(`/api/calls/${callId}/end`, { method: "POST" }),
    getAnalysis: (callId: string) =>
      fetchApi<Analysis>(`/api/calls/${callId}/analysis`),
  },
};

export interface Analysis {
  effectiveness_score: number;
  tactics_used: string[];
  tactics_that_worked: string[];
  tactics_that_failed: string[];
  objections_encountered: string[];
  objection_handling_quality: number;
  key_moments: { timestamp_approx: string; description: string; impact: string }[];
  sentiment_arc: string;
  improvement_suggestions: string[];
  outcome: string;
}

// frontend/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";
const KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export type Finding = {
  title: string; severity: string; endpoint: string; evidence: string;
  poc?: string; remediation?: string; attack_method?: string; persona?: string;
};
export type Profile = Record<string, any>;
export type Scan = {
  scan_id: string; status: string;
  target?: { ip: string; port: number; endpoint: string; url: string };
  profile?: Profile | null; scenario?: string | null; engine?: string | null;
  report_url?: string | null; findings?: Finding[]; error?: string | null;
};

function headers() {
  return { "Content-Type": "application/json", "x-api-key": KEY };
}

export async function submitScan(input: {
  ip: string; port: number; endpoint: string;
}): Promise<{ scan_id: string }> {
  const res = await fetch(`${BASE}/scan`, {
    method: "POST", headers: headers(),
    body: JSON.stringify({ ...input, authorized: true }),
  });
  if (!res.ok) throw new Error((await res.json()).error || `HTTP ${res.status}`);
  return res.json();
}

export async function getScan(id: string): Promise<Scan> {
  const res = await fetch(`${BASE}/scan/${id}`, { headers: headers() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// frontend/components/FindingsList.tsx
import { Finding } from "@/lib/api";

const COLORS: Record<string, string> = {
  critical: "#dc2626", high: "#ea580c", medium: "#d97706",
  low: "#2563eb", info: "#64748b",
};

export default function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings?.length) return <p style={{ color: "#475569" }}>No findings yet.</p>;
  return (
    <div className="card">
      <h3>Findings ({findings.length})</h3>
      {findings.map((f, i) => (
        <div key={i} style={{ borderTop: "1px solid #16203a", padding: "10px 0" }}>
          <div>
            <span className="sev" style={{ background: COLORS[f.severity] || "#64748b" }}>
              {f.severity}
            </span>{" "}
            <b>{f.title}</b>
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12 }}>
            {f.attack_method} · {f.endpoint}
          </div>
          {f.evidence && <pre style={{ fontSize: 12 }}>{f.evidence}</pre>}
          {f.remediation && <div style={{ fontSize: 12 }}>Fix: {f.remediation}</div>}
        </div>
      ))}
    </div>
  );
}

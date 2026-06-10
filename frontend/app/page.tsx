// frontend/app/page.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { submitScan, getScan, Scan } from "@/lib/api";
import ScanForm from "@/components/ScanForm";
import ProfileCard from "@/components/ProfileCard";
import ScenarioView from "@/components/ScenarioView";
import FindingsList from "@/components/FindingsList";

const TERMINAL = ["DONE", "FAILED", "REJECTED"];

export default function Home() {
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<any>(null);

  useEffect(() => () => clearInterval(timer.current), []);

  async function launch(input: { ip: string; port: number; endpoint: string; agents: number }) {
    setError(null); setScan(null); setBusy(true);
    try {
      const { scan_id } = await submitScan(input);
      timer.current = setInterval(async () => {
        try {
          const s = await getScan(scan_id);
          setScan(s);
          if (TERMINAL.includes(s.status)) { clearInterval(timer.current); setBusy(false); }
        } catch (e: any) { /* keep polling; transient */ }
      }, 2000);
    } catch (e: any) { setError(e.message); setBusy(false); }
  }

  return (
    <div className="container">
      <h1>🛡️ Tier2 — AI Pentest Scenario & Execution</h1>
      <p style={{ color: "#64748b" }}>
        Enter an <b>authorized</b> target. The backend generates a random attacker
        profile, an Opus pentest scenario, then executes it.
      </p>
      <ScanForm onSubmit={launch} busy={busy} />
      {error && <div className="err">⚠ {error}</div>}
      {scan && (
        <>
          <div className="card">
            <b>Status:</b> {scan.status}
            {scan.engine ? ` · engine: ${scan.engine}` : ""}
            {scan.report_url ? ` · report: ${scan.report_url}` : ""}
            {scan.error ? ` · error: ${scan.error}` : ""}
          </div>
          {scan.agents && scan.agents.length > 0 ? (
            <div className="card">
              <h3>Attacker swarm ({scan.agents.length})</h3>
              {scan.agents.map((a) => (
                <div key={a.index} style={{ borderTop: "1px solid #16203a", paddingTop: 10, marginTop: 10 }}>
                  {a.profile ? <ProfileCard p={a.profile} /> : null}
                  {a.error ? <div className="err">agent #{a.index} failed: {a.error}</div> : null}
                  {a.scenario ? (
                    <details>
                      <summary style={{ cursor: "pointer", color: "#94a3b8", fontSize: 12 }}>
                        Scenario — agent #{a.index} {a.engine ? `(${a.engine})` : ""}
                      </summary>
                      <ScenarioView md={a.scenario} engine={a.engine} />
                    </details>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <>
              {scan.profile && <ProfileCard p={scan.profile} />}
              {scan.scenario && <ScenarioView md={scan.scenario} engine={scan.engine} />}
            </>
          )}
          <FindingsList findings={scan.findings || []} />
        </>
      )}
    </div>
  );
}

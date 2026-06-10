// frontend/components/ScanForm.tsx
"use client";
import { useEffect, useState } from "react";
import { getScope } from "@/lib/api";

const selectStyle: React.CSSProperties = {
  width: "100%", padding: 10, border: "1px solid #1e293b",
  borderRadius: 9, background: "#05070f", color: "#e2e8f0",
};

export default function ScanForm({ onSubmit, busy }: {
  onSubmit: (v: { ip: string; port: number; endpoint: string }) => void;
  busy: boolean;
}) {
  const [ip, setIp] = useState("");
  const [port, setPort] = useState(8080);
  const [endpoint, setEndpoint] = useState("/login");
  const [authorized, setAuthorized] = useState(false);
  const [targets, setTargets] = useState<string[]>([]);
  const [selected, setSelected] = useState(""); // "" = custom / manual
  const [scopeError, setScopeError] = useState<string | null>(null);

  // host:port -> fill ip+port; bare host -> ip + default port 80
  function applyTarget(t: string) {
    if (t.includes("/")) return; // CIDR — not directly selectable
    const i = t.lastIndexOf(":");
    if (i > -1) {
      setIp(t.slice(0, i));
      setPort(parseInt(t.slice(i + 1), 10) || 80);
    } else {
      setIp(t);
      setPort(80);
    }
  }

  useEffect(() => {
    getScope()
      .then((r) => {
        const t = r.targets || [];
        setTargets(t);
        const first = t.find((x) => !x.includes("/"));
        if (first) { setSelected(first); applyTarget(first); }
      })
      .catch((e) => setScopeError(String(e.message || e)));
  }, []);

  return (
    <div className="card">
      <label>Permitted target {targets.length ? `(${targets.length})` : ""}</label>
      <select style={selectStyle} value={selected}
              onChange={(e) => { setSelected(e.target.value); if (e.target.value) applyTarget(e.target.value); }}>
        <option value="">✎ Custom (manual entry)</option>
        {targets.map((t) => (
          <option key={t} value={t} disabled={t.includes("/")}>
            {t}{t.includes("/") ? "  (CIDR — enter manually)" : ""}
          </option>
        ))}
      </select>
      {scopeError && (
        <div style={{ color: "#94a3b8", fontSize: 11, marginTop: 4 }}>
          Couldn’t load allowlist ({scopeError}). Enter the target manually.
        </div>
      )}

      <div className="row" style={{ marginTop: 12 }}>
        <div>
          <label>Target IP / host</label>
          <input type="text" value={ip} onChange={(e) => setIp(e.target.value)}
                 placeholder="54.84.126.64" />
        </div>
        <div>
          <label>Port</label>
          <input type="number" value={port}
                 onChange={(e) => setPort(parseInt(e.target.value || "0", 10))} />
        </div>
      </div>
      <label>Endpoint</label>
      <input type="text" value={endpoint}
             onChange={(e) => setEndpoint(e.target.value)} placeholder="/login" />
      <label style={{ marginTop: 14 }}>
        <input type="checkbox" checked={authorized}
               onChange={(e) => setAuthorized(e.target.checked)} />{" "}
        I confirm I am authorized to test this target.
      </label>
      <button className="primary" disabled={!authorized || !ip || busy}
              onClick={() => onSubmit({ ip, port, endpoint })}>
        {busy ? "Running…" : "Launch scan"}
      </button>
    </div>
  );
}

// frontend/components/ScanForm.tsx
"use client";
import { useState } from "react";

export default function ScanForm({ onSubmit, busy }: {
  onSubmit: (v: { ip: string; port: number; endpoint: string }) => void;
  busy: boolean;
}) {
  const [ip, setIp] = useState("");
  const [port, setPort] = useState(8080);
  const [endpoint, setEndpoint] = useState("/login");
  const [authorized, setAuthorized] = useState(false);

  return (
    <div className="card">
      <div className="row">
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

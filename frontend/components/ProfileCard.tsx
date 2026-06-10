// frontend/components/ProfileCard.tsx
import { Profile } from "@/lib/api";

export default function ProfileCard({ p }: { p: Profile }) {
  if (!p) return null;
  return (
    <div className="card">
      <h3>{p.emoji} Attacker profile — {p.alias}</h3>
      <p><b>{p.archetype}</b> · {p.skill_level}</p>
      <p style={{ color: "#94a3b8" }}>{p.style}</p>
      <ul>
        <li>Motivation: {p.motivation}</li>
        <li>Origin / crew: {p.origin} · {p.crew_size}</li>
        <li>Stealth / aggressiveness: {p.stealth} / {p.aggressiveness}</li>
        <li>TTPs: {(p.preferred_ttps || []).join(", ")}</li>
        <li>Toolset: {(p.toolset || []).join(", ")}</li>
        <li>MITRE: {(p.mitre_tactics || []).join(", ")}</li>
      </ul>
    </div>
  );
}

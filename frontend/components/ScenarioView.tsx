// frontend/components/ScenarioView.tsx
export default function ScenarioView({ md, engine }: { md: string; engine?: string | null }) {
  if (!md) return null;
  return (
    <div className="card">
      <h3>Generated scenario {engine ? `(engine: ${engine})` : ""}</h3>
      <pre>{md}</pre>
    </div>
  );
}

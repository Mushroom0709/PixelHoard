import { useApiHealth } from "../hooks/useApiHealth";

export default function Health() {
  const { health, version, loading, error, latencyMs } = useApiHealth();

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-8">
        API 健康详情
      </h1>

      {loading && <div className="text-slate-500">checking…</div>}
      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-700">
          ✗ {error}
        </div>
      )}

      {health && (
        <div className="space-y-4">
          <Card title="GET /api/health">
            <KV k="ok" v={String(health.ok)} />
            <KV k="service" v={health.service} />
            <KV k="version" v={health.version} />
          </Card>

          <Card title="GET /api/version">
            <KV k="ok" v={String(version?.ok)} />
            <KV k="phase" v={version?.phase ?? "—"} />
            <KV k="milestone" v={version?.milestone ?? "—"} />
          </Card>

          {latencyMs !== null && (
            <div className="text-sm text-slate-500">
              往返延迟: <span className="font-mono">{latencyMs}ms</span>
            </div>
          )}
        </div>
      )}
    </main>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
      <div className="text-sm uppercase tracking-wider text-slate-500 mb-3">
        {title}
      </div>
      <div className="space-y-1 font-mono text-sm">{children}</div>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-slate-500 w-24 shrink-0">{k}:</span>
      <span>{v}</span>
    </div>
  );
}
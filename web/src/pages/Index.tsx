import { useEffect, useState } from "react";

interface HealthResp {
  ok: boolean;
  service: string;
  version: string;
}

export default function Index() {
  const [health, setHealth] = useState<HealthResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-brand-600">
        PixelHoard
      </h1>
      <p className="mt-4 text-slate-600 dark:text-slate-400 text-lg">
        基于 OBS 的照片视频分享系统
      </p>

      <div className="mt-12 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="text-sm uppercase tracking-wider text-slate-500 mb-3">
          API 健康
        </div>
        {err && <div className="text-rose-600">✗ {err}</div>}
        {health && (
          <div className="space-y-1 font-mono text-sm">
            <div>
              <span className="text-slate-500">status:</span>{" "}
              <span className="text-emerald-600">{health.ok ? "✓ ok" : "✗"}</span>
            </div>
            <div>
              <span className="text-slate-500">service:</span> {health.service}
            </div>
            <div>
              <span className="text-slate-500">version:</span> {health.version}
            </div>
          </div>
        )}
        {!health && !err && <div className="text-slate-500">checking…</div>}
      </div>

      <footer className="mt-16 text-xs text-slate-400">
        v0.0.1 · ticket #1 · skeleton
      </footer>
    </main>
  );
}
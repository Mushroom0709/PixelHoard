import { Link, useLocation } from "react-router-dom";
import { useApiHealth } from "../hooks/useApiHealth";

export default function Index() {
  const { health, version, loading, error, latencyMs } = useApiHealth();
  const loc = useLocation();

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-brand-600">
        PixelHoard
      </h1>
      <p className="mt-4 text-slate-600 dark:text-slate-400 text-lg">
        基于 OBS 的照片视频分享系统
      </p>

      {/* 联调状态卡 — ticket #2 */}
      <div className="mt-12 w-full max-w-md rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="text-sm uppercase tracking-wider text-slate-500 mb-3">
          FastAPI ↔ Vite 联调
        </div>

        {error && (
          <div className="text-rose-600 font-mono text-sm">✗ {error}</div>
        )}

        {loading && !error && (
          <div className="text-slate-500 text-sm">checking…</div>
        )}

        {health && (
          <div className="space-y-1 font-mono text-sm">
            <div>
              <span className="text-slate-500">GET /api/health:</span>{" "}
              <span className="text-emerald-600">
                {health.ok ? "✓ 200" : "✗"}
              </span>{" "}
              <span className="text-slate-400">{health.service}</span>
            </div>
            <div>
              <span className="text-slate-500">GET /api/version:</span>{" "}
              <span className="text-emerald-600">
                {version?.ok ? "✓ 200" : "✗"}
              </span>{" "}
              <span className="text-slate-400">v{health.version}</span>
            </div>
            {version?.phase && (
              <div>
                <span className="text-slate-500">phase:</span> {version.phase}
              </div>
            )}
            {version?.milestone && (
              <div>
                <span className="text-slate-500">milestone:</span>{" "}
                {version.milestone}
              </div>
            )}
            {latencyMs !== null && (
              <div className="text-xs text-slate-400 pt-2">
                往返延迟 {latencyMs}ms
              </div>
            )}
          </div>
        )}
      </div>

      {/* 路由导航 */}
      <nav className="mt-10 flex gap-6 text-sm">
        <Link
          to="/"
          className={
            loc.pathname === "/" ? "text-brand-600 font-medium" : "text-slate-500 hover:text-slate-700"
          }
        >
          首页
        </Link>
        <Link
          to="/health"
          className={
            loc.pathname === "/health" ? "text-brand-600 font-medium" : "text-slate-500 hover:text-slate-700"
          }
        >
          健康详情
        </Link>
      </nav>

      <footer className="mt-16 text-xs text-slate-400">
        v0.0.1 · ticket #2 · hello linkage
      </footer>
    </main>
  );
}
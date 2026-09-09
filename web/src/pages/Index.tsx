import { Link, useNavigate } from "react-router-dom";
import { useApiHealth } from "../hooks/useApiHealth";
import { useAuth } from "../auth";

export default function Index() {
  const { health, version, loading, error, latencyMs } = useApiHealth();
  const auth = useAuth();
  const nav = useNavigate();

  const adminBadge =
    health && version ? "ok" : loading ? "checking" : "fail";

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
          系统状态
        </div>

        {error && <div className="text-rose-600 font-mono text-sm">✗ {error}</div>}

        {loading && !error && (
          <div className="text-slate-500 text-sm">checking…</div>
        )}

        {health && (
          <div className="space-y-1 font-mono text-sm">
            <div>
              <span className="text-slate-500">API:</span>{" "}
              <span className="text-emerald-600">
                {health.ok ? "✓" : "✗"} {health.service}
              </span>
            </div>
            <div>
              <span className="text-slate-500">版本:</span> v{health.version}
            </div>
            {version?.phase && (
              <div>
                <span className="text-slate-500">阶段:</span> {version.phase}
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

      {/* 导航 */}
      <nav className="mt-10 flex gap-6 text-sm">
        {auth.accessToken ? (
          <>
            <Link
              to="/shares"
              className="text-brand-600 hover:underline font-medium"
            >
              我的分享
            </Link>
            <button
              onClick={() => {
                auth.logout();
                nav("/login");
              }}
              className="text-slate-500 hover:text-rose-600"
            >
              登出
            </button>
          </>
        ) : (
          <>
            <Link
              to="/login"
              className="text-brand-600 hover:underline font-medium"
            >
              登录
            </Link>
            <Link
              to="/register"
              className="text-slate-500 hover:text-slate-700"
            >
              注册
            </Link>
          </>
        )}
        <Link
          to="/health"
          className="text-slate-500 hover:text-slate-700"
        >
          健康详情
        </Link>
      </nav>

      <footer className="mt-16 text-xs text-slate-400">
        v0.0.1 · status: {adminBadge}
      </footer>
    </main>
  );
}
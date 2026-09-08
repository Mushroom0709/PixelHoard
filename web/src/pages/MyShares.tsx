import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Share {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  created_at: string;
}

export default function MyShares() {
  const [shares, setShares] = useState<Share[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("ph_access");
    if (!token) {
      setError("未登录");
      setLoading(false);
      return;
    }
    fetch("/api/shares/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          if (r.status === 401) {
            setError("未登录或 token 过期");
            return;
          }
          setError(`错误 ${r.status}`);
          return;
        }
        const list = await r.json();
        setShares(list);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
        ← 首页
      </Link>

      <div className="mt-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold">我的分享</h1>
        <button
          disabled
          className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm opacity-50 cursor-not-allowed"
        >
          + 新建分享(后续)
        </button>
      </div>

      {loading && <div className="mt-12 text-slate-500">loading…</div>}

      {error && (
        <div className="mt-12 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-700">
          {error}
        </div>
      )}

      {!loading && !error && shares.length === 0 && (
        <div className="mt-12 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center">
          <div className="text-slate-500">📂</div>
          <div className="mt-2 text-slate-600 dark:text-slate-400">
            还没有分享
          </div>
          <div className="text-xs text-slate-400 mt-1">点击右上角"新建分享"</div>
        </div>
      )}

      {!loading && shares.length > 0 && (
        <ul className="mt-8 space-y-3">
          {shares.map((s) => (
            <li key={s.id}>
              <Link
                to={`/s/${s.slug}`}
                className="block rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 hover:border-brand-500 transition"
              >
                <div className="font-medium">{s.title}</div>
                {s.description && (
                  <div className="mt-1 text-sm text-slate-500 line-clamp-1">
                    {s.description}
                  </div>
                )}
                <div className="mt-2 text-xs text-slate-400 font-mono">
                  /s/{s.slug} ·{" "}
                  {new Date(s.created_at).toLocaleDateString("zh-CN")}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
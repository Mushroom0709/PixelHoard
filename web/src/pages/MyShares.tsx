import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

interface Share {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  created_at: string;
  role?: string | null;
}

export default function MyShares() {
  const { accessToken, logout } = useAuth();
  const nav = useNavigate();
  const [shares, setShares] = useState<Share[]>([]);
  const [granted, setGranted] = useState<Share[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  useEffect(() => {
    if (!accessToken) {
      nav("/login");
      return;
    }
    fetch("/api/shares/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then(async (r) => {
        if (r.status === 401) {
          logout();
          nav("/login");
          return;
        }
        if (!r.ok) {
          setError(`错误 ${r.status}`);
          return;
        }
        const data = await r.json();
        setShares(data);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));

    // 共享给我的(viewer/editor)
    fetch("/api/shares/granted", {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setGranted)
      .catch(() => setGranted([]));
  }, [accessToken, nav, logout]);

  async function createShare(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    const r = await fetch("/api/shares", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ title: newTitle.trim() }),
    });
    if (!r.ok) {
      alert(`创建失败: ${r.status}`);
      return;
    }
    const data = await r.json();
    setNewTitle("");
    setCreating(false);
    nav(`/s/${data.slug}`);
  }

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
          ← 首页
        </Link>
        <button
          onClick={() => {
            logout();
            nav("/");
          }}
          className="text-sm text-slate-500 hover:text-rose-600"
        >
          登出
        </button>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold">我的分享</h1>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
        >
          + 新建分享
        </button>
      </div>

      {creating && (
        <form
          onSubmit={createShare}
          className="mt-4 flex gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4"
        >
          <input
            type="text"
            required
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="分享标题"
            className="flex-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
          >
            创建
          </button>
          <button
            type="button"
            onClick={() => setCreating(false)}
            className="px-3 py-2 text-slate-500 text-sm hover:text-slate-700"
          >
            取消
          </button>
        </form>
      )}

      {loading && <div className="mt-12 text-slate-500">loading…</div>}

      {error && (
        <div className="mt-12 rounded-lg border border-rose-300 bg-rose-50 p-4 text-rose-700">
          {error}
        </div>
      )}

      {!loading && !error && shares.length === 0 && granted.length === 0 && (
        <div className="mt-12 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center">
          <div className="text-slate-500">📂</div>
          <div className="mt-2 text-slate-600 dark:text-slate-400">还没有分享</div>
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

      {!loading && granted.length > 0 && (
        <>
          <h2 className="mt-10 text-lg font-medium">共享给我的({granted.length})</h2>
          <ul className="mt-3 space-y-3">
            {granted.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/s/${s.slug}`}
                  className="block rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 hover:border-brand-500 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{s.title}</span>
                    <span
                      className={
                        s.role === "editor"
                          ? "px-2 py-0.5 rounded text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300"
                          : "px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
                      }
                    >
                      {s.role === "editor" ? "可编辑" : "只读"}
                    </span>
                  </div>
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
        </>
      )}
    </main>
  );
}
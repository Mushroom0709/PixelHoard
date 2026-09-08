import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

interface Share {
  id: number;
  owner_id: number;
  slug: string;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export default function ShareDetail() {
  const { slug } = useParams<{ slug: string }>();
  const [share, setShare] = useState<Share | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) return;
    const token = localStorage.getItem("ph_access");
    fetch(`/api/shares/${slug}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (r) => {
        if (r.status === 401) {
          setError("未登录");
          return;
        }
        if (r.status === 403) {
          setError("无权访问此分享");
          return;
        }
        if (r.status === 404) {
          setError("分享不存在");
          return;
        }
        if (!r.ok) {
          setError(`错误: ${r.status}`);
          return;
        }
        const data = await r.json();
        setShare(data);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-slate-500">loading…</div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-6 gap-4">
        <div className="text-rose-600 text-lg">{error}</div>
        <Link to="/" className="text-brand-600 hover:underline">
          ← 回到首页
        </Link>
      </main>
    );
  }

  if (!share) return null;

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
        ← 我的分享
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-slate-900 dark:text-slate-100">
        {share.title}
      </h1>
      <div className="mt-2 text-sm text-slate-500 font-mono">
        slug: /s/{share.slug}
      </div>

      {share.description && (
        <p className="mt-4 text-slate-700 dark:text-slate-300">{share.description}</p>
      )}

      <div className="mt-8 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center">
        <div className="text-slate-500">📁</div>
        <div className="mt-2 text-slate-600 dark:text-slate-400">暂无文件</div>
        <div className="text-xs text-slate-400 mt-1">
          (上传功能在后续 ticket #14+ 启用)
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button
          disabled
          className="px-4 py-2 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
        >
          管理 token(后续)
        </button>
        <button
          disabled
          className="px-4 py-2 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
        >
          授权用户(后续)
        </button>
      </div>

      <footer className="mt-12 text-xs text-slate-400">
        创建于 {new Date(share.created_at).toLocaleString("zh-CN")}
      </footer>
    </main>
  );
}
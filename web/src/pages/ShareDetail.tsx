import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { sha256Hex } from "../utils/sha256";

interface Share {
  id: number;
  owner_id: number;
  slug: string;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  role: string | null;
}

interface FileItem {
  id: number;
  original_filename: string;
  size_bytes: number;
  mime_type: string;
  status: string;
  failure_reason: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  codec: string | null;
  moov_at_head: boolean | null;
  has_exif: boolean | null;
  created_at: string;
}

interface ShareToken {
  id: number;
  token_code: string;
  permission: string;
  label: string | null;
  public_note: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function statusBadge(status: string): string {
  if (status === "processing") return "⏳ 处理中";
  if (status === "failed") return "✗ 失败";
  if (status === "ready") return "✓ 就绪";
  return status;
}

interface PartUpload {
  part_number: number;
  etag: string;
  size: number;
}

export default function ShareDetail() {
  const slug = useParams<{ slug: string }>().slug;
  const nav = useNavigate();
  const auth = useAuth();
  const token = auth.accessToken;

  const [share, setShare] = useState<Share | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [tokens, setTokens] = useState<ShareToken[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const isOwner = share?.role === null;

  // 加载 share
  useEffect(() => {
    if (!slug) return;
    fetch(`/api/shares/${slug}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (r) => {
        if (r.status === 401) return setError("未登录");
        if (r.status === 403) return setError("无权访问");
        if (r.status === 404) return setError("分享不存在");
        if (!r.ok) return setError(`错误 ${r.status}`);
        setShare(await r.json());
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [slug, token]);

  // 加载文件列表(轮询 3s)
  useEffect(() => {
    if (!slug || !share) return;
    const tick = () => {
      fetch(`/api/shares/${slug}/files`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => (r.ok ? r.json() : { files: [] }))
        .then((d) => setFiles(d.files || []))
        .catch(() => setFiles([]));
    };
    tick();
    const interval = setInterval(tick, 3000);
    return () => clearInterval(interval);
  }, [slug, share, token]);

  // 加载 token(仅 owner)
  useEffect(() => {
    if (!slug || !share || !token) return;
    fetch(`/api/shares/${slug}/tokens`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setTokens(d || []))
      .catch(() => setTokens([]));
  }, [slug, share, token]);

  async function createToken(permission: "read" | "readwrite") {
    if (!token || !share) return;
    const label = window.prompt("给这个 token 起个名字(自己看):", "") || "";
    const publicNote = window.prompt("游客可见的留言(可空):", "") || "";
    const r = await fetch(`/api/shares/${slug}/tokens`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ permission, label, public_note: publicNote }),
    });
    if (!r.ok) {
      window.alert(`创建失败: ${r.status}`);
      return;
    }
    const data: ShareToken = await r.json();
    setTokens((t) => [data, ...t]);
    // unused vars fallback
    void publicNote;
    void label;
    const url = `${window.location.origin}/s/${slug}/${data.token_code}`;
    try {
      await navigator.clipboard.writeText(url);
      window.alert(`已复制链接到剪贴板:\n${url}`);
    } catch {
      window.alert(`token 码: ${data.token_code}\n完整 URL: ${url}`);
    }
  }

  async function revokeToken(id: number) {
    if (!token || !share) return;
    if (!window.confirm("确认撤销此 token?")) return;
    const r = await fetch(`/api/shares/${slug}/tokens/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.status === 204) {
      setTokens((t) =>
        t.map((tk) => (tk.id === id ? { ...tk, revoked_at: new Date().toISOString() } : tk))
      );
    } else {
      window.alert(`撤销失败: ${r.status}`);
    }
  }

  async function deleteShare() {
    if (!token || !share) return;
    if (!window.confirm(`确认删除整个 share "${share.title}"?此操作不可逆!`)) return;
    const r = await fetch(`/api/shares/${slug}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.status === 204) {
      nav("/shares");
    } else {
      window.alert(`删除失败: ${r.status}`);
    }
  }

  // 批量上传 — 并发 3 个(避免 OBS API 限流),显示进度
  const [uploads, setUploads] = useState<Map<string, {name: string; progress: number; status: "pending"|"uploading"|"done"|"error"; error?: string}>>(new Map());

  async function uploadFiles(fileList: FileList | File[] | null) {
    if (!fileList || fileList.length === 0 || !share) return;
    const files = Array.from(fileList);
    // 初始化进度 entries
    setUploads((prev) => {
      const next = new Map(prev);
      files.forEach((f) => {
        if (!next.has(f.name + f.size)) {
          next.set(f.name + f.size, { name: f.name, progress: 0, status: "pending" });
        }
      });
      return next;
    });

    // 并发 3 个
    const CONCURRENCY = 3;
    let cursor = 0;
    const errors: string[] = [];
    const worker = async () => {
      while (cursor < files.length) {
        const f = files[cursor++];
        const key = f.name + f.size;
        try {
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 5, status: "uploading" }));
          await uploadOne(f, (p) => {
            setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: p, status: "uploading" }));
          });
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 100, status: "done" }));
        } catch (e) {
          const msg = e instanceof Error ? e.message : "unknown";
          console.error(e);
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 0, status: "error", error: msg }));
          errors.push(`${f.name}: ${msg}`);
        }
      }
    };
    const workers = Array(Math.min(CONCURRENCY, files.length)).fill(0).map(() => worker());
    await Promise.all(workers);

    if (errors.length > 0) {
      window.alert(`${errors.length}/${files.length} 个文件上传失败:\n\n${errors.slice(0, 3).join("\n")}${errors.length > 3 ? `\n... 还有 ${errors.length - 3} 个` : ""}`);
    }
    // 3 秒后清理完成的项
    setTimeout(() => {
      setUploads((prev) => {
        const next = new Map();
        prev.forEach((v, k) => {
          if (v.status === "uploading" || v.status === "pending") next.set(k, v);
        });
        return next;
      });
    }, 3000);
  }

  async function uploadOne(file: File, onProgress?: (pct: number) => void): Promise<void> {
    onProgress?.(5);
    // 1. init
    const initRes = await fetch(`/api/shares/${slug}/upload-init`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        filename: file.name,
        size: file.size,
        mime_type: file.type || "application/octet-stream",
        sha256: await sha256Hex(file),
      }),
    });
    if (!initRes.ok) throw new Error(`init ${initRes.status}`);
    const initData = await initRes.json();

    // 2. 分片上传
    const partSize = initData.part_size || 5 * 1024 * 1024;
    const urls: string[] = initData.part_urls;
    const parts: PartUpload[] = [];

    for (let i = 0; i < urls.length; i++) {
      const start = i * partSize;
      const end = Math.min(start + partSize, file.size);
      const blob = file.slice(start, end);
      const putRes = await fetch(urls[i], { method: "PUT", body: blob });
      if (!putRes.ok) throw new Error(`part ${i + 1} put ${putRes.status}`);
      const etag = putRes.headers.get("ETag")?.replace(/"/g, "") || "";
      parts.push({ part_number: i + 1, etag, size: end - start });
      // 进度:5% init + 80% 分片 + 15% complete
      const uploadPct = 5 + Math.round((i + 1) / urls.length * 80);
      onProgress?.(uploadPct);
    }

    // 3. complete
    onProgress?.(90);
    const completeRes = await fetch(`/api/shares/${slug}/upload-complete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ upload_id: initData.upload_id, parts }),
    });
    if (!completeRes.ok) throw new Error(`complete ${completeRes.status}`);
  }

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
    <main className="min-h-screen px-6 py-12 max-w-4xl mx-auto">
      <Link to="/shares" className="text-sm text-slate-500 hover:text-slate-700">
        ← 我的分享
      </Link>

      <div className="mt-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">
            {share.title}
          </h1>
          <div className="mt-2 text-sm text-slate-500 font-mono flex items-center gap-2">
            <span>/s/{share.slug}</span>
            {share.role && (
              <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                角色: {share.role}
              </span>
            )}
          </div>
          {share.description && (
            <p className="mt-3 text-slate-700 dark:text-slate-300">{share.description}</p>
          )}
        </div>
      </div>

      {/* 文件区 */}
      <section className="mt-8">
        <h2 className="text-lg font-medium mb-3">文件({files.length})</h2>
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
          {files.length === 0 ? (
            <div className="p-8 text-center text-slate-500">暂无文件</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">文件名</th>
                  <th className="px-4 py-2 text-right">大小</th>
                  <th className="px-4 py-2 text-center">状态</th>
                  <th className="px-4 py-2 text-left">元数据</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.id} className="border-t border-slate-200 dark:border-slate-800">
                    <td className="px-4 py-2 truncate max-w-xs">{f.original_filename}</td>
                    <td className="px-4 py-2 text-right font-mono text-xs">
                      {formatSize(f.size_bytes)}
                    </td>
                    <td className="px-4 py-2 text-center text-xs">
                      {statusBadge(f.status)}
                      {f.moov_at_head === false && (
                        <div className="text-amber-600 text-xs mt-0.5">仅顺序播放</div>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {f.width && f.height && (
                        <span>
                          {f.width}×{f.height}
                        </span>
                      )}
                      {f.duration_seconds !== null && (
                        <span className="ml-2">{formatDuration(f.duration_seconds)}</span>
                      )}
                      {f.codec && (
                        <span className="ml-2 font-mono">{f.codec}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* owner 控制区 */}
      {isOwner && (
        <>
          {/* 上传 */}
          <section className="mt-8">
            <h2 className="text-lg font-medium mb-3">上传文件</h2>
            <label
              className="block rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 p-8 text-center cursor-pointer hover:border-brand-500 transition"
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                const files = Array.from(e.dataTransfer.files);
                if (files.length > 0) uploadFiles(files);
              }}
            >
              <div className="text-slate-500">📤 点击或拖入文件(支持批量多选)</div>
              <div className="text-xs text-slate-400 mt-1">
                直传 OBS · 浏览器分片 · 大文件支持 · 3 个并发
              </div>
              <input
                type="file"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) uploadFiles(e.target.files);
                  e.target.value = "";  // 允许重复选同一文件
                }}
              />
            </label>

            {/* 批量上传进度 */}
            {uploads.size > 0 && (
              <ul className="mt-3 space-y-1.5">
                {Array.from(uploads.entries()).map(([key, u]) => (
                  <li
                    key={key}
                    className="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-2.5 text-sm"
                  >
                    <div className="flex-1 truncate">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">{u.name}</span>
                        {u.status === "done" && <span className="text-emerald-600 text-xs">✓ 完成</span>}
                        {u.status === "error" && <span className="text-rose-600 text-xs">✗ {u.error}</span>}
                        {u.status === "uploading" && <span className="text-slate-500 text-xs">{u.progress}%</span>}
                        {u.status === "pending" && <span className="text-slate-400 text-xs">等待</span>}
                      </div>
                      {u.status === "uploading" && (
                        <div className="mt-1 h-1 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-brand-500 transition-all"
                            style={{ width: `${u.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Token 管理 */}
          <section className="mt-8">
            <h2 className="text-lg font-medium mb-3">访问 Token({tokens.length})</h2>
            <div className="flex gap-2 mb-3">
              <button
                onClick={() => createToken("read")}
                className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
              >
                + 只读 token
              </button>
              <button
                onClick={() => createToken("readwrite")}
                className="px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm hover:bg-amber-600"
              >
                + 读写 token
              </button>
            </div>
            {tokens.length > 0 && (
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800 text-slate-500 text-xs uppercase">
                    <tr>
                      <th className="px-4 py-2 text-left">名称</th>
                      <th className="px-4 py-2 text-left">码</th>
                      <th className="px-4 py-2 text-center">权限</th>
                      <th className="px-4 py-2 text-center">状态</th>
                      <th className="px-4 py-2 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tokens.map((t) => (
                      <tr
                        key={t.id}
                        className="border-t border-slate-200 dark:border-slate-800"
                      >
                        <td className="px-4 py-2">{t.label || "(未命名)"}</td>
                        <td className="px-4 py-2 font-mono text-xs">{t.token_code}</td>
                        <td className="px-4 py-2 text-center text-xs">
                          <span
                            className={
                              t.permission === "readwrite"
                                ? "px-2 py-0.5 rounded bg-amber-100 text-amber-800"
                                : "px-2 py-0.5 rounded bg-slate-100 text-slate-700"
                            }
                          >
                            {t.permission}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-center text-xs">
                          {t.revoked_at ? (
                            <span className="text-rose-600">已撤销</span>
                          ) : (
                            <span className="text-emerald-600">有效</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {!t.revoked_at && (
                            <button
                              onClick={() => revokeToken(t.id)}
                              className="text-rose-600 hover:underline text-xs"
                            >
                              撤销
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* 删除 */}
          <section className="mt-8">
            <button
              onClick={deleteShare}
              className="px-4 py-2 rounded-lg border border-rose-300 text-rose-600 text-sm hover:bg-rose-50"
            >
              删除整个 share(危险)
            </button>
          </section>
        </>
      )}
    </main>
  );
}

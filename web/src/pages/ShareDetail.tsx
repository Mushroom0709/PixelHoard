import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "../auth";
import { sha256Hex } from "../utils/sha256";

/* ── 类型 ─────────────────────────────────────────────── */
interface ShareMeta {
  id: number;
  owner_id: number;
  slug: string;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  role: string | null; // member: null=owner / editor / viewer;guest 无
  permission?: string; // guest 专用: read / readwrite
  token_public_note?: string | null;
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

interface PartUpload {
  part_number: number;
  etag: string;
  size: number;
}

/* ── 工具 ─────────────────────────────────────────────── */
const NATIVE_IMG = new Set(["jpg", "jpeg", "png", "webp", "gif", "avif"]);
const HEIC_RAW = new Set(["heic", "heif", "arw", "cr2", "cr3", "nef", "dng", "rw2", "orf", "raf"]);
const VIDEO = new Set(["mp4", "mov", "webm", "mkv", "m4v", "avi", "hevc", "ts"]);

function suffixOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}
const isNativeImage = (f: FileItem) => NATIVE_IMG.has(suffixOf(f.original_filename));
const isHeicRaw = (f: FileItem) => HEIC_RAW.has(suffixOf(f.original_filename));
const isVideo = (f: FileItem) => VIDEO.has(suffixOf(f.original_filename));
const isMedia = (f: FileItem) => isNativeImage(f) || isHeicRaw(f) || isVideo(f);
/** 预览应请求的 kind */
function previewKind(f: FileItem): string {
  if (isVideo(f)) return "raw";
  if (isHeicRaw(f)) return "display";
  return "raw";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
function formatDuration(seconds: number | null): string {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
function fileIcon(f: FileItem): string {
  if (isVideo(f)) return "🎬";
  if (isHeicRaw(f)) return "📷";
  if (isNativeImage(f)) return "🖼️";
  return "📄";
}

/* ── 主组件 ───────────────────────────────────────────── */
export default function ShareDetail() {
  const { slug = "", tokenCode } = useParams<{ slug: string; tokenCode?: string }>();
  const auth = useAuth();
  const memberToken = auth.accessToken;
  const guestToken = tokenCode || null;
  const isGuest = !!guestToken;

  const [share, setShare] = useState<ShareMeta | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [tokens, setTokens] = useState<ShareToken[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<FileItem | null>(null);

  const isOwner = !isGuest && share?.role === null;
  const canWrite = isGuest
    ? share?.permission === "readwrite"
    : !isGuest && share?.role !== "viewer";

  /* 鉴权头(成员用) */
  const authHeaders = (json = false): Record<string, string> => {
    const h: Record<string, string> = {};
    if (memberToken) h["Authorization"] = `Bearer ${memberToken}`;
    if (json) h["Content-Type"] = "application/json";
    return h;
  };
  const guestQuery = (extra = ""): string =>
    isGuest ? `?token=${encodeURIComponent(guestToken || "")}${extra}` : extra;
  const urlWithMode = (path: string, query = ""): string =>
    isGuest ? `${path}${guestQuery(query)}` : `${path}${query}`;

  /* 加载 share */
  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    const p = isGuest
      ? fetch(`/api/guest/share/${slug}?token=${encodeURIComponent(guestToken || "")}`)
      : fetch(`/api/shares/${slug}`, { headers: authHeaders() });
    p.then(async (r) => {
      if (r.status === 401) throw isGuest ? new Error("链接无效或已过期") : new Error("请先登录");
      if (r.status === 403) throw new Error("无权访问该分享");
      if (r.status === 404) throw new Error("分享不存在");
      if (!r.ok) throw new Error(`错误 ${r.status}`);
      const d = await r.json();
      if (isGuest) {
        const g: ShareMeta = { ...d.share, role: "guest", permission: d.permission, token_public_note: d.token_public_note };
        setShare(g);
      } else {
        setShare(d as ShareMeta);
      }
    })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, tokenCode, memberToken]);

  /* 加载文件列表(轮询 3s — 反映 worker 处理进度) */
  useEffect(() => {
    if (!slug || !share) return;
    const tick = () => {
      const p = isGuest
        ? fetch(`/api/guest/share/${slug}/files?token=${encodeURIComponent(guestToken || "")}`)
        : fetch(`/api/shares/${slug}/files`, { headers: authHeaders() });
      p.then((r) => (r.ok ? r.json() : { files: [] }))
        .then((d) => setFiles(d.files || []))
        .catch(() => setFiles([]));
    };
    tick();
    const interval = setInterval(tick, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, share, tokenCode, memberToken]);

  /* 加载 token(仅 owner) */
  useEffect(() => {
    if (!slug || !share || isGuest || !memberToken) return;
    fetch(`/api/shares/${slug}/tokens`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setTokens(d || []))
      .catch(() => setTokens([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, share, memberToken]);

  /* 文件访问 URL(单次获取) */
  const getFileUrl = useCallback(
    async (f: FileItem, kind: string, download = false): Promise<string> => {
      const dl = download ? 1 : 0;
      // 注意:query 必须以 ? 开头(& 只在拼接多个参数时用)!
      const path = isGuest
        ? `/api/guest/files/${f.id}/url?share=${encodeURIComponent(slug)}&kind=${kind}&download=${dl}`
        : `/api/shares/${slug}/files/${f.id}/url?kind=${kind}&download=${dl}`;
      const r = await fetch(urlWithMode(path), { headers: authHeaders() });
      if (!r.ok) throw new Error(`url ${r.status}`);
      const d = await r.json();
      return d.url as string;
    },
    [isGuest, slug, memberToken]
  );

  /* 下载(新窗口导航 — OBS 返回 attachment) */
  const downloadFile = useCallback(
    async (f: FileItem) => {
      try {
        const url = await getFileUrl(f, "raw", true);
        window.open(url, "_blank");
      } catch (e) {
        window.alert(`获取下载链接失败: ${e instanceof Error ? e.message : e}`);
      }
    },
    [getFileUrl]
  );

  /* 删除文件 */
  const deleteFile = useCallback(
    async (f: FileItem) => {
      if (!window.confirm(`确认删除文件 "${f.original_filename}"?不可恢复!`)) return;
      const path = isGuest
        ? `/api/guest/files/${f.id}?share=${encodeURIComponent(slug)}&token=${encodeURIComponent(guestToken || "")}`
        : `/api/shares/${slug}/files/${f.id}`;
      const r = await fetch(path, { method: "DELETE", headers: authHeaders() });
      if (r.status === 204 || r.ok) {
        setFiles((fs) => fs.filter((x) => x.id !== f.id));
        setPreview((p) => (p && p.id === f.id ? null : p));
      } else {
        window.alert(`删除失败: ${r.status}`);
      }
    },
    [isGuest, slug, guestToken]
  );

  /* Token 管理(owner) */
  async function createToken(permission: "read" | "readwrite") {
    if (!memberToken || !share) return;
    const label = window.prompt("给这个 token 起个名字(仅自己可见):", "") || "";
    const publicNote = window.prompt("游客可见留言(可空):", "") || "";
    const r = await fetch(`/api/shares/${slug}/tokens`, {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({ permission, label, public_note: publicNote }),
    });
    if (!r.ok) {
      window.alert(`创建失败: ${r.status}`);
      return;
    }
    const data: ShareToken = await r.json();
    setTokens((t) => [data, ...t]);
    const url = `${window.location.origin}/s/${slug}/${data.token_code}`;
    try {
      await navigator.clipboard.writeText(url);
      window.alert(`已复制分享链接:\n${url}`);
    } catch {
      window.alert(`分享链接:\n${url}`);
    }
  }

  async function revokeToken(id: number) {
    if (!memberToken || !share) return;
    if (!window.confirm("确认撤销此 token?已分享的链接将立即失效!")) return;
    const r = await fetch(`/api/shares/${slug}/tokens/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
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
    if (!memberToken || !share) return;
    if (!window.confirm(`确认删除整个 share "${share.title}"?所有文件将从 OBS 永久删除!`)) return;
    const r = await fetch(`/api/shares/${slug}`, { method: "DELETE", headers: authHeaders() });
    if (r.status === 204) {
      window.location.href = "/shares";
    } else {
      window.alert(`删除失败: ${r.status}`);
    }
  }

  /* 批量上传 — 并发 3,进度展示 */
  const [uploads, setUploads] = useState<
    Map<string, { name: string; progress: number; status: "pending" | "uploading" | "done" | "error"; error?: string }>
  >(new Map());

  async function uploadOne(file: File, onProgress?: (pct: number) => void): Promise<void> {
    onProgress?.(5);
    const suffix = suffixOf(file.name);
    // 1. init(游客 readwrite:token 走 query;后端 get_current_user 无 header 返 None)
    const initRes = await fetch(urlWithMode(`/api/shares/${slug}/upload-init`), {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({
        filename: file.name,
        size: file.size,
        mime_type: file.type || "application/octet-stream",
        sha256: await sha256Hex(file),
      }),
    });
    if (!initRes.ok) throw new Error(`init ${initRes.status}${suffix ? "" : ""}`);
    const initData = await initRes.json();

    // 2. 分片上传
    const partSize = initData.part_size || 5 * 1024 * 1024;
    const urls: string[] = initData.part_urls;
    const parts: PartUpload[] = [];
    for (let i = 0; i < urls.length; i++) {
      const start = i * partSize;
      const end = Math.min(start + partSize, file.size);
      const blob = file.slice(start, end);
      // Content-Type 必须与后端签名 headers 一致,否则 OBS SignatureDoesNotMatch
      const putRes = await fetch(urls[i], {
        method: "PUT",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: blob,
      });
      if (!putRes.ok) throw new Error(`part ${i + 1} put ${putRes.status}`);
      const etag = putRes.headers.get("ETag")?.replace(/"/g, "") || "";
      parts.push({ part_number: i + 1, etag, size: end - start });
      onProgress?.(5 + Math.round(((i + 1) / urls.length) * 80));
    }

    // 3. complete
    onProgress?.(90);
    const completeRes = await fetch(urlWithMode(`/api/shares/${slug}/upload-complete`), {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({ upload_id: initData.upload_id, parts }),
    });
    if (!completeRes.ok) throw new Error(`complete ${completeRes.status}`);
    onProgress?.(100);
  }

  async function uploadFiles(fileList: FileList | File[] | null) {
    if (!fileList || fileList.length === 0 || !share) return;
    const chosen = Array.from(fileList);
    setUploads((prev) => {
      const next = new Map(prev);
      chosen.forEach((f) => {
        if (!next.has(f.name + f.size)) next.set(f.name + f.size, { name: f.name, progress: 0, status: "pending" });
      });
      return next;
    });

    const CONCURRENCY = 3;
    let cursor = 0;
    const errors: string[] = [];
    const worker = async () => {
      while (cursor < chosen.length) {
        const f = chosen[cursor++];
        const key = f.name + f.size;
        try {
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 5, status: "uploading" }));
          await uploadOne(f, (p) =>
            setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: p, status: "uploading" }))
          );
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 100, status: "done" }));
        } catch (e) {
          const msg = e instanceof Error ? e.message : "unknown";
          console.error(e);
          setUploads((prev) => new Map(prev).set(key, { name: f.name, progress: 0, status: "error", error: msg }));
          errors.push(`${f.name}: ${msg}`);
        }
      }
    };
    const workers = Array(Math.min(CONCURRENCY, chosen.length))
      .fill(0)
      .map(() => worker());
    await Promise.all(workers);

    if (errors.length > 0) {
      window.alert(
        `${errors.length}/${chosen.length} 个文件上传失败:\n\n${errors.slice(0, 3).join("\n")}${errors.length > 3 ? `\n... 还有 ${errors.length - 3} 个` : ""}`
      );
    }
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

  /* ── 渲染 ── */
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
        <Link to={isGuest ? "/" : "/shares"} className="text-brand-600 hover:underline">
          ← 返回
        </Link>
      </main>
    );
  }
  if (!share) return null;

  const roleBadge = () => {
    if (isGuest)
      return (
        <span className="px-2 py-0.5 rounded text-xs bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300">
          🎟️ 游客 · {share.permission === "readwrite" ? "读写" : "只读"}
        </span>
      );
    if (share.role === null)
      return (
        <span className="px-2 py-0.5 rounded text-xs bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
          所有者
        </span>
      );
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
        角色: {share.role === "editor" ? "可编辑" : "只读"}
      </span>
    );
  };

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8 sm:py-12 max-w-6xl mx-auto">
      <Link
        to={isGuest ? "/" : "/shares"}
        className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
      >
        ← {isGuest ? "回到首页" : "我的分享"}
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 break-words">
            {share.title}
          </h1>
          <div className="mt-2 text-sm text-slate-500 font-mono flex flex-wrap items-center gap-2">
            <span>/s/{share.slug}</span>
            {roleBadge()}
          </div>
          {share.token_public_note && !isOwner && (
            <p className="mt-2 text-sm text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-900/20 rounded-lg px-3 py-2">
              💬 {share.token_public_note}
            </p>
          )}
          {share.description && (
            <p className="mt-3 text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{share.description}</p>
          )}
        </div>
        {!isGuest && !memberToken && (
          <Link
            to="/login"
            className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
          >
            登录查看
          </Link>
        )}
      </div>

      {/* 文件网格 */}
      <section className="mt-8">
        <h2 className="text-lg font-medium mb-3">
          文件({files.length})
          {files.some((f) => f.status === "processing") && (
            <span className="ml-2 text-xs text-slate-400 font-normal">处理中自动刷新…</span>
          )}
        </h2>
        {files.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-10 text-center text-slate-500">
            暂无文件
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {files.map((f) => (
              <FileCard
                key={f.id}
                f={f}
                canDelete={!!canWrite}
                onOpen={() => setPreview(f)}
                onDownload={() => downloadFile(f)}
                onDelete={() => deleteFile(f)}
                getThumbUrl={(kind) => getFileUrl(f, kind)}
              />
            ))}
          </div>
        )}
      </section>

      {/* 上传区(canWrite) */}
      {canWrite && (
        <section className="mt-10">
          <h2 className="text-lg font-medium mb-3">上传文件</h2>
          <label
            className="block rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 p-8 text-center cursor-pointer hover:border-brand-500 transition"
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const fs = Array.from(e.dataTransfer.files);
              if (fs.length > 0) uploadFiles(fs);
            }}
          >
            <div className="text-slate-500">📤 点击或拖入文件(支持批量多选)</div>
            <div className="text-xs text-slate-400 mt-1">
              直传 OBS · 分片上传 · 支持图片/视频/任意文件 · 3 个并发
            </div>
            <input
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files) uploadFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>

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
                        <div className="h-full bg-brand-500 transition-all" style={{ width: `${u.progress}%` }} />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Token 管理(仅 owner) */}
      {isOwner && (
        <section className="mt-10">
          <h2 className="text-lg font-medium mb-3">分享链接与访问码({tokens.length})</h2>
          <div className="flex flex-wrap gap-2 mb-3">
            <button
              onClick={() => createToken("read")}
              className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
            >
              + 生成只读链接
            </button>
            <button
              onClick={() => createToken("readwrite")}
              className="px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm hover:bg-amber-600"
            >
              + 生成读写链接
            </button>
          </div>
          {tokens.length > 0 && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead className="bg-slate-50 dark:bg-slate-800 text-slate-500 text-xs uppercase">
                  <tr>
                    <th className="px-4 py-2 text-left">名称</th>
                    <th className="px-4 py-2 text-left">链接</th>
                    <th className="px-4 py-2 text-center">权限</th>
                    <th className="px-4 py-2 text-center">状态</th>
                    <th className="px-4 py-2 text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tokens.map((t) => {
                    const link = `${window.location.origin}/s/${slug}/${t.token_code}`;
                    return (
                      <tr key={t.id} className="border-t border-slate-200 dark:border-slate-800">
                        <td className="px-4 py-2 max-w-[120px] truncate">{t.label || "(未命名)"}</td>
                        <td className="px-4 py-2">
                          <button
                            onClick={() => {
                              navigator.clipboard
                                .writeText(link)
                                .then(() => window.alert("链接已复制:\n" + link))
                                .catch(() => window.prompt("复制此链接:", link));
                            }}
                            className="text-brand-600 hover:underline font-mono text-xs"
                            title="点击复制"
                          >
                            /s/{slug}/{t.token_code} ⧉
                          </button>
                        </td>
                        <td className="px-4 py-2 text-center text-xs">
                          <span
                            className={
                              t.permission === "readwrite"
                                ? "px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300"
                                : "px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                            }
                          >
                            {t.permission === "readwrite" ? "读写" : "只读"}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-center text-xs">
                          {t.revoked_at ? (
                            <span className="text-rose-600">已撤销</span>
                          ) : (
                            <span className="text-emerald-600">有效</span>
                          )}
                          {t.expires_at && !t.revoked_at && (
                            <span className="ml-1 text-slate-400">
                              {new Date(t.expires_at).toLocaleDateString()} 到期
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {!t.revoked_at && (
                            <button onClick={() => revokeToken(t.id)} className="text-rose-600 hover:underline text-xs">
                              撤销
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* 危险区(owner) */}
      {isOwner && (
        <section className="mt-10">
          <button
            onClick={deleteShare}
            className="px-4 py-2 rounded-lg border border-rose-300 dark:border-rose-800 text-rose-600 dark:text-rose-400 text-sm hover:bg-rose-50 dark:hover:bg-rose-950/30"
          >
            删除整个 share(危险,不可逆)
          </button>
        </section>
      )}

      {/* 预览 modal */}
      {preview && (
        <PreviewModal
          f={preview}
          canDelete={!!canWrite}
          onClose={() => setPreview(null)}
          onDownload={() => downloadFile(preview)}
          onDelete={() => deleteFile(preview)}
          getUrl={(kind, download) => getFileUrl(preview, kind, download)}
        />
      )}
    </main>
  );
}

/* ── 文件卡片(缩略图懒加载) ──────────────────────────── */
function FileCard(props: {
  f: FileItem;
  canDelete: boolean;
  onOpen: () => void;
  onDownload: () => void;
  onDelete: () => void;
  getThumbUrl: (kind: string) => Promise<string>;
}) {
  const { f } = props;
  const [thumb, setThumb] = useState<string | null>(null);
  const ready = f.status === "ready";

  // ready 且有衍生能力(媒体)→ 请求 thumb
  useEffect(() => {
    let alive = true;
    if (ready && isMedia(f)) {
      props
        .getThumbUrl("thumb")
        .then((u) => {
          if (alive) setThumb(u);
        })
        .catch(() => {
          if (alive) setThumb(null);
        });
    }
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.id, ready, f.status]);

  return (
    <div
      className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden hover:shadow-md transition cursor-pointer"
      onClick={props.onOpen}
    >
      <div className="aspect-square bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden relative">
        {thumb ? (
          <img src={thumb} alt={f.original_filename} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <span className="text-4xl">{fileIcon(f)}</span>
        )}
        {f.status === "processing" && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center text-white text-xs backdrop-blur-[1px]">
            ⏳ 处理中
          </div>
        )}
        {f.status === "failed" && (
          <div className="absolute inset-0 bg-rose-900/60 flex items-center justify-center text-white text-xs px-2 text-center">
            ✗ 处理失败
          </div>
        )}
        {/* 悬停操作 */}
        <div className="absolute inset-x-0 bottom-0 flex justify-end gap-1 p-1.5 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition">
          <button
            className="px-2 py-1 rounded bg-white/90 text-slate-800 text-xs"
            onClick={(e) => {
              e.stopPropagation();
              props.onDownload();
            }}
          >
            ⬇
          </button>
          {props.canDelete && (
            <button
              className="px-2 py-1 rounded bg-rose-500/90 text-white text-xs"
              onClick={(e) => {
                e.stopPropagation();
                props.onDelete();
              }}
            >
              🗑
            </button>
          )}
        </div>
      </div>
      <div className="p-2">
        <div className="text-xs font-medium truncate" title={f.original_filename}>
          {f.original_filename}
        </div>
        <div className="mt-0.5 text-[11px] text-slate-400 flex justify-between">
          <span>{formatSize(f.size_bytes)}</span>
          <span>
            {f.width && f.height ? `${f.width}×${f.height}` : ""}
            {isVideo(f) && formatDuration(f.duration_seconds) ? ` · ${formatDuration(f.duration_seconds)}` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── 预览 modal ───────────────────────────────────────── */
function PreviewModal(props: {
  f: FileItem;
  canDelete: boolean;
  onClose: () => void;
  onDownload: () => void;
  onDelete: () => void;
  getUrl: (kind: string, download: boolean) => Promise<string>;
}) {
  const { f } = props;
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setUrl(null);
    setErr(null);
    const kind = previewKind(f);
    props
      .getUrl(kind, false)
      .then((u) => {
        if (alive) setUrl(u);
      })
      .catch((e) => {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.id]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      onClick={props.onClose}
    >
      <div
        className="bg-slate-900 rounded-2xl overflow-hidden max-w-5xl w-full flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 顶栏 */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800/80">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-slate-400">{fileIcon(f)}</span>
            <span className="text-sm text-slate-100 truncate">{f.original_filename}</span>
            <span className="text-xs text-slate-400 shrink-0">
              {formatSize(f.size_bytes)}
              {f.width && f.height ? ` · ${f.width}×${f.height}` : ""}
              {isVideo(f) && formatDuration(f.duration_seconds) ? ` · ${formatDuration(f.duration_seconds)}` : ""}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={props.onDownload}
              className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-sm hover:bg-brand-600"
            >
              ⬇ 下载原文件
            </button>
            {props.canDelete && (
              <button
                onClick={props.onDelete}
                className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-sm hover:bg-rose-500"
              >
                🗑 删除
              </button>
            )}
            <button
              onClick={props.onClose}
              className="px-2.5 py-1.5 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600"
            >
              ✕
            </button>
          </div>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-auto flex items-center justify-center bg-black/40 p-4 min-h-[200px]">
          {err ? (
            <div className="text-rose-400 text-sm text-center">
              {err}
              <div className="mt-2 text-slate-400 text-xs">文件可能还在处理中,稍后重试</div>
            </div>
          ) : !url ? (
            <div className="text-slate-400">加载中…</div>
          ) : isVideo(f) ? (
            <video src={url} controls autoPlay className="max-w-full max-h-[70vh] rounded-lg" playsInline />
          ) : isNativeImage(f) || isHeicRaw(f) ? (
            <img src={url} alt={f.original_filename} className="max-w-full max-h-[70vh] object-contain" />
          ) : (
            <div className="text-slate-300 text-sm">
              该类型暂不支持在线预览,请点击右上角"下载原文件"。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

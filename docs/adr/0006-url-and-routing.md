# ADR-0006:URL 形式与前端路由

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D11, D58-D60

---

## Context

D11 留了开口:URL 形式选 `?t={token}` 或 `/{token}` 路径形式。
两个都很常见,需要拍板。

## Decision

### 选 **`/s/{slug}/{token}`** 路径形式

理由:

| 维度 | `?t=xxx` | `/s/{slug}/{token}`(选)|
|---|---|---|
| 微信/短信分享 | ❌ `?` 易被识别为追踪 | ✅ 干净的"链接"|
| 浏览器粘贴 | 一般 | ✅ 一眼能读 |
| SEO | 一般 | ✅ 更结构化 |
| 用户记忆 | 一般 | ✅ "直接打开"感 |
| 实现 | 单 query 解析 | 路径解析 |
| 兼容性 | 一般 | ✅ 浏览器直开,不丢 token |

具体规则:

| 角色 | URL |
|---|---|
| 游客访问 | `https://{host}/s/{slug}/{token}` |
| 登录用户访问(自己有 share)| `https://{host}/s/{slug}`(自动 owner 权限)|
| 登录用户访问(被授权)| `https://{host}/s/{slug}`(自动 user_grant 角色)|
| 登录用户访问(无权限)| `https://{host}/s/{slug}` → 403 |
| 管理员 | `https://{host}/admin/shares/{id}`(独立后台)|

### Slug 规则(D58-D60)

- 默认系统生成:8 位 base62,例如 `kX9pTqLm`
- 用户改名:`^[a-z0-9-]{3,32}$`,大小写不敏感,全局唯一
- 冲突 409

### 前端路由结构

```ts
// React Router v6 配置
const routes = [
  { path: "/", element: <Home /> },                  // 登录用户首页
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  { path: "/shares", element: <MyShares /> },        // 我的分享列表
  { path: "/shares/new", element: <CreateShare /> },
  { path: "/s/:slug", element: <ShareView /> },      // 登录用户视角
  { path: "/s/:slug/:token", element: <ShareView /> }, // 游客视角
  { path: "/admin/*", element: <Admin />, role: "admin" },
  { path: "*", element: <NotFound /> },
];
```

## Consequences

### Positive

- 路径形式分享体验好
- 同一组件 `ShareView` 处理两种访问(登录 / 游客),代码复用

### Negative

- 游客访问 `/s/{slug}/{token}` 时,如果 share 设置了公开 + 需 token,URL 直接暴露 token → 与 D6/D10 设计一致
- Slug 改名后老 URL 失效,需 301 重定向(简单实现)

### 风险

- 搜索引擎可能索引 `/s/{slug}/xxx` 链接 → 需要 `robots.txt` 禁止 + `<meta name="robots" content="noindex">`

## 重定向处理

```nginx
# nginx 配置 / 后端中间件
location /s/ {
    # 老 slug → 新 slug 301
    try_files $uri @rewrite_old_slug;
}
```
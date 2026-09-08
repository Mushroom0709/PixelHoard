# ADR-0001:技术栈与权限模型

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D3, D8-D18, D27-D32, D50-D54

---

## Context

需要确定 PixelHoard 的技术栈和权限模型。

技术栈候选 5 种:Next.js 全栈 / FastAPI+React / Django+React / Go+React / Rust+React。

权限模型需要厘清:三种角色(管理员/用户/游客)+ token 维度的 read/readwrite + 用户授权维度的 viewer/editor。

## Decision

### 技术栈(D27-D32)

| 层 | 选型 |
|---|---|
| 后端 | **FastAPI**(Python 3.11+) |
| 前端 | **React + Vite + TypeScript + Tailwind v4** |
| DB | **PostgreSQL** + **Redis** |
| 对象存储 | **华为云 OBS**(`obs-mushroom` 桶,work path `PixelHoard/`) |
| 视频处理 | **FFprobe**(仅探测) |
| 图片处理 | **Pillow** + **rawpy** + **dcraw**(ARW 解码)|
| 上传 | **浏览器直传 OBS + Multipart 分片** |
| 认证 | **邮箱 + 密码 + JWT** |
| 部署 | **Docker + Compose,目标 ECS xj-ai-service(27.18.114.8)** |

### 权限模型(D3, D8-D18, D50-D54)

1. **三个角色**: admin / user / guest
2. **两个授权维度**:
   - **Token 维度**:read / readwrite,绑定游客
   - **UserGrant 维度**:viewer / editor,绑定登录用户
3. **Owner 维度**: 创建者,完全权限
4. **Admin 维度**: 可看全部,但仍受 ACL 校验
5. **游客无状态**: token 是唯一凭证,服务端不持久化游客信息(D12-D14)

## Consequences

### Positive

- FastAPI 异步原生 + OBS Python SDK 文档齐,复用 ImageHub 经验
- React + Vite + Tailwind v4 与用户偏好一致
- 多层权限模型清晰,可独立演进
- 游客无状态 = GDPR 友好 + 实现简单

### Negative

- 不做 HLS / ABR,大视频在弱网下体验受限(D37 v2 再说)
- token 权限 + user 授权两个维度并存,学习曲线略陡(但用同一个角色矩阵表对齐)

### Neutral

- 依赖 PGSQL + Redis 双组件,部署稍复杂(Compose 一键拉起)

## 参考实现

```python
# 角色判定核心逻辑(伪代码)
def resolve_role(user: User | None, token: Token | None, share: Share) -> Role:
    if user and user.is_admin: return Role.ADMIN
    if user and user.id == share.owner_id: return Role.OWNER
    if user:
        ug = UserGrant.query(share.id, user.id)
        if ug: return Role.EDITOR if ug.role == "editor" else Role.VIEWER
    if token and token.share_id == share.id and not token.is_expired() and not token.is_revoked():
        return Role.EDITOR if token.permission == "readwrite" else Role.VIEWER
    raise PermissionDenied
```
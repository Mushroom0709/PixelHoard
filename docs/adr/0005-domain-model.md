# ADR-0005:Domain Model — 数据库 schema

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D1-D83 全部

---

## Context

本 ADR 把所有决策落到 PostgreSQL 表结构。

## Decision

### 实体关系图

```
users ──┬── owns ─→ shares ──┬── has → tokens
        │                    ├── contains → files
        │                    └── granted to → users (via user_grants)
        │
        └── writes → audit_logs

admins (is_admin=true 的 users 通过 flag 字段标记)
```

### 表结构

```sql
-- 用户
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,            -- bcrypt
    display_name TEXT,
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    INDEX idx_users_email (email)
);

-- 分享
CREATE TABLE shares (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT NOT NULL UNIQUE,              -- 8 位 base62 默认,可改
    title TEXT NOT NULL,
    description TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false, -- D23 软标记 30 天后清
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    INDEX idx_shares_slug (slug),
    INDEX idx_shares_owner (owner_id),
    INDEX idx_shares_deleted (is_deleted, deleted_at)
);

-- 分享的访问 token(短码)
CREATE TABLE share_tokens (
    id BIGSERIAL PRIMARY KEY,
    share_id BIGINT NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    token_code TEXT NOT NULL UNIQUE,        -- 8 位 base62
    permission TEXT NOT NULL CHECK (permission IN ('read', 'readwrite')),
    label TEXT,                              -- D55 owner 私有
    public_note TEXT,                        -- D55 游客可见
    expires_at TIMESTAMPTZ,                  -- D20 可选
    revoked_at TIMESTAMPTZ,                  -- D19 可选
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    INDEX idx_tokens_code (token_code),
    INDEX idx_tokens_share (share_id),
    INDEX idx_tokens_active (share_id, revoked_at, expires_at)
);

-- 登录用户授权关系
CREATE TABLE user_grants (
    id BIGSERIAL PRIMARY KEY,
    share_id BIGINT NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
    granted_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (share_id, user_id),
    INDEX idx_grants_user (user_id),
    INDEX idx_grants_share (share_id)
);

-- 文件
CREATE TABLE files (
    id BIGSERIAL PRIMARY KEY,
    share_id BIGINT NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    uploaded_by BIGINT REFERENCES users(id),  -- 游客上传时为 NULL
    uploaded_via_token BIGINT REFERENCES share_tokens(id), -- 游客场景
    original_filename TEXT NOT NULL,
    obs_key TEXT NOT NULL,                   -- shares/{share_id}/raw/...
    size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    suffix TEXT NOT NULL,                    -- 小写,无点
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    failure_reason TEXT,
    
    -- 衍生档 OBS keys(可选,status='ready' 时必有 thumb/preview)
    thumb_key TEXT,
    preview_key TEXT,
    display_key TEXT,                        -- 兜底档
    
    -- 探测结果
    width INTEGER,
    height INTEGER,
    duration_seconds REAL,                   -- 视频用
    codec TEXT,                              -- 视频用
    moov_at_head BOOLEAN,                    -- 视频用
    has_exif BOOLEAN,                        -- 图片用
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    INDEX idx_files_share (share_id, created_at DESC),
    INDEX idx_files_status (status),
    INDEX idx_files_sha256 (sha256)          -- 去重可选
);

-- 审计日志
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    share_id BIGINT REFERENCES shares(id),
    token_id BIGINT REFERENCES share_tokens(id),
    file_id BIGINT REFERENCES files(id),
    action TEXT NOT NULL,                    -- 'login', 'create_share', etc.
    target_type TEXT,                        -- 'share' | 'token' | 'file' | ...
    target_id BIGINT,
    ip INET,
    user_agent TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    INDEX idx_audit_occurred (occurred_at),
    INDEX idx_audit_user (user_id, occurred_at),
    INDEX idx_audit_share (share_id, occurred_at)
);

-- Quota 配置(admin 后台可配,v1 暂不限)
CREATE TABLE quota_configs (
    id BIGSERIAL PRIMARY KEY,
    scope TEXT NOT NULL,                     -- 'user' | 'share' | 'global'
    scope_id BIGINT,                         -- user_id / share_id; global 时 NULL
    max_shares INTEGER,
    max_files_per_share INTEGER,
    max_file_size_bytes BIGINT,
    max_total_bytes BIGINT,
    updated_by BIGINT REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Consequences

### Positive

- 所有决策(D1-D83)有具体落点
- 主外键 + 索引齐全,查询性能有保障
- 30 天审计 cron 只需 `DELETE FROM audit_logs WHERE occurred_at < NOW() - INTERVAL '30 days'`

### Negative

- `display_key` 字段在原图能播时为空,需前端判断
- 软删 share 30 天后清,需要 cron 任务
- 文件去重目前仅 `sha256` 索引(不做内容寻址),真实去重逻辑在 v2 再说

### 风险

- 大表性能:`files` 表可能爆炸,需要定期归档(`status='deleted' AND deleted_at < NOW() - INTERVAL '30 days'` 删除)

## 后续

- ADR-0006:URL 形式(`/s/{slug}?t={token}` vs `/s/{slug}/{token}`)
- ADR-0007:OBS prefix 详细设计(已部分在 ADR-0004 描述)
- ADR-0008:部署拓扑(api / web / worker 三件套)
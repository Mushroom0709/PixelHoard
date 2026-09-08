# ADR-0007:部署拓扑(Docker Compose on ECS)

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D80-D83

---

## Context

部署目标 ECS xj-ai-service(27.18.114.8, SSH 10332, root/kU2hVZdxaT4GBW8b)。
业务端口范围 10333-10400。容器化:Docker + Docker Compose。

## Decision

### 容器拓扑

```
┌─────────────────────────────────────────────────────┐
│ ECS xj-ai-service (27.18.114.8)                     │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │ postgres │ │  redis   │ │   api    │ │  web  │ │
│  │ :10333   │ │ :10334   │ │ :10335   │ │ :10336│ │
│  └──────────┘ └──────────┘ └──────────┘ └───────┘ │
│                                     ┌──────────┐   │
│                                     │  worker  │   │
│                                     │ (后台)   │   │
│                                     └──────────┘   │
│                                                     │
│  外部 OBS: obs-mushroom / PixelHoard/               │
└─────────────────────────────────────────────────────┘
```

### 端口分配(D81)

| 服务 | 容器内 | 宿主机 |
|---|---|---|
| postgres | 5432 | **10333** |
| redis | 6379 | **10334** |
| api(FastAPI) | 8000 | **10335** |
| web(nginx + Vite dist) | 80 | **10336** |
| worker | (无外部) | (无) |

### docker-compose.yml 草图

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: pixelhoard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: pixelhoard
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "10333:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "10334:6379"

  api:
    build: ./api
    environment:
      DATABASE_URL: postgresql://pixelhoard:${DB_PASSWORD}@postgres/pixelhoard
      REDIS_URL: redis://redis:6379
      OBS_AK: ${OBS_AK}
      OBS_SK: ${OBS_SK}
      OBS_ENDPOINT: ${OBS_ENDPOINT}
      OBS_BUCKET: ${OBS_BUCKET}
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      - postgres
      - redis
    ports:
      - "10335:8000"

  worker:
    build: ./api  # 同镜像,不同 entrypoint
    command: ["python", "-m", "worker"]
    environment:
      # 同 api
    depends_on:
      - postgres
      - redis
    # 不暴露端口

  web:
    build: ./web
    # Vite 构建产物由 nginx 服务
    ports:
      - "10336:80"

volumes:
  pgdata:
```

### 部署脚本

```bash
# /Users/mushroom/Documents/ai/hermes/projects/PixelHoard/scripts/deploy.sh
# 1. SSH 到 ECS
# 2. 拉最新镜像 / 同步 src
# 3. docker compose build api web
# 4. docker compose up -d
# 5. 健康检查 curl http://127.0.0.1:10335/health
# 6. 验证 web curl http://127.0.0.1:10336 | grep index-XXX.js
```

## Consequences

### Positive

- 与 ImageHub 部署流程一致(复用经验)
- 三件套独立伸缩:v1 先单实例,worker 压力大时扩 worker
- 数据 + 缓存 + 应用分离,可独立备份

### Negative

- 单 ECS 单点 → v1 可接受,v2 需考虑 HA
- OBS 在外部,网络抖动会拖慢上传/下载(预签名 URL 直连可缓解)

### 风险

- 数据库 / Redis 容器化 → 数据卷需定期备份(`pg_dump`)
- Worker 进程崩溃 → 需重启策略(`restart: unless-stopped`)

## 备份策略(D77-D79)

- postgres 数据卷每日 `pg_dump` 到 OSS
- OBS versioning(D77)防文件层误删
- audit_logs 30 天后自动清(D73-D76)

## 上线流程

1. 本地 Mac 开发 + 单测
2. 本地 Docker Compose 起全栈测试
3. `scripts/deploy.sh` 推到 ECS(SSH 10332)
4. ECS 上 `docker compose build && up -d`
5. `curl http://127.0.0.1:10336 | grep index-XXX.js` 验证 web hash 与本地一致
6. iPhone 真机访问 ECS 业务地址验证移动端(D72)
7. Lighthouse / 真机性能验证(P1-P12)
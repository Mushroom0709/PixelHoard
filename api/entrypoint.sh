#!/bin/sh
# entrypoint.sh — 容器启动入口
# 1. 等 postgres 健康(由 docker-compose depends_on 保证)
# 2. 跑 alembic upgrade head(自动建表 / 升级 schema)
# 3. 启动 uvicorn(或 worker 自己的 command)

set -e

echo "[entrypoint] running alembic upgrade head..."
cd /app
alembic upgrade head
echo "[entrypoint] alembic done"

# 把 CMD 参数透传给 uvicorn(默认 ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
exec "$@"
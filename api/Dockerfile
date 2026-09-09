FROM python:3.11-slim

WORKDIR /app

# 系统依赖:ffmpeg(视频 ffprobe)+ curl + libpq(pg 客户端)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 整个项目根目录(含 alembic.ini + alembic/)
# .dockerignore 会排除 web/node_modules 等大件
COPY . /app

EXPOSE 8000

# 启动时先跑 alembic upgrade head,再起 uvicorn
# 用 entrypoint.sh 而不是直接 CMD,便于 alembic 失败时容器退出
RUN chmod +x /app/api/entrypoint.sh
ENTRYPOINT ["/app/api/entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
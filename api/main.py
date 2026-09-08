"""PixelHoard FastAPI 入口。"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from obs_client import obs
from db import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动/关闭钩子。"""
    # 启动
    print(f"[startup] PixelHoard API starting")
    print(f"[startup] OBS endpoint={settings.OBS_ENDPOINT} bucket={settings.OBS_BUCKET}")
    # DB 探测
    async with engine.connect() as conn:
        await conn.run_sync(lambda s: s.execute(__import__("sqlalchemy").text("SELECT 1")))
    print(f"[startup] DB OK")
    yield
    # 关闭
    print(f"[shutdown] cleanup")


app = FastAPI(
    title="PixelHoard API",
    version="0.0.1",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """健康检查端点。"""
    return {"ok": True, "service": "pixelhoard-api", "version": "0.0.1"}


@app.get("/obs-ping")
async def obs_ping() -> dict:
    """OBS 连通性探测。"""
    try:
        # 简单列出 bucket 前 1 个对象作为连通性证明
        resp = obs.listObjects(bucketName=settings.OBS_BUCKET, max_keys=1)
        return {
            "ok": True,
            "bucket": settings.OBS_BUCKET,
            "endpoint": settings.OBS_ENDPOINT,
            "objects_count": len(resp.get("contents", [])),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
"""审计日志工具 — ticket #20。"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import insert

from .db import async_session
from .models import AuditLog

logger = logging.getLogger("pixelhoard.audit")


async def log(
    action: str,
    *,
    user_id: Optional[int] = None,
    share_id: Optional[int] = None,
    token_id: Optional[int] = None,
    file_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """写入 audit_logs 一行(best-effort,失败仅 log)。"""
    try:
        async with async_session() as db:
            await db.execute(
                insert(AuditLog).values(
                    user_id=user_id,
                    share_id=share_id,
                    token_id=token_id,
                    file_id=file_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    ip=ip,
                    user_agent=user_agent,
                )
            )
            await db.commit()
    except Exception as e:
        # 审计失败不应阻塞主流程
        logger.warning(f"audit log failed: action={action} err={e}")


# ── Cron:清理 30 天前的审计日志 ─────────────────────────
async def cleanup_old_audit(days: int = 30) -> int:
    """清理 days 天前的 audit_logs 行。"""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with async_session() as db:
        result = await db.execute(
            delete(AuditLog).where(AuditLog.occurred_at < cutoff)
        )
        await db.commit()
    return result.rowcount or 0
from sqlalchemy import select, delete, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from app.core.database import get_db_session
from app.services.setting_service import get_setting

import asyncio


# ── Queue helpers ─────────────────────────────────────────────────────────────

def get_audit_log_queue() -> asyncio.Queue:
    """
    Lấy hàng đợi tương ứng với Event Loop hiện tại.
    Gắn trực tiếp vào loop object để đảm bảo không bị lệch loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Queue()

    if not hasattr(loop, "_audit_log_queue"):
        loop._audit_log_queue = asyncio.Queue()
    return loop._audit_log_queue


# ── Write helpers ─────────────────────────────────────────────────────────────

async def create_audit_log(
    session: Optional[AsyncSession] = None,
    request_type: str = "unknown",
    **kwargs,
):
    """
    Đẩy log vào hàng đợi bất đồng bộ (non-blocking).
    Hỗ trợ các field mới: request_id, ip_address, http_method, path.
    """
    log_data = {
        "request_type": request_type,
        "request_time": datetime.now(timezone.utc),
        "duration": kwargs.get("duration", 0.0),
        "total_token": kwargs.get("total_token", 0),
        **kwargs,
    }
    queue = get_audit_log_queue()
    await queue.put(log_data)
    return None


async def flush_audit_log_queue(session: Optional[AsyncSession] = None):
    """Đẩy toàn bộ log trong queue vào DB ngay lập tức."""
    queue = get_audit_log_queue()
    logs_to_insert = []

    while not queue.empty():
        try:
            item = queue.get_nowait()
            logs_to_insert.append(item)
        except asyncio.QueueEmpty:
            break

    if logs_to_insert:
        if session:
            session.add_all([AuditLog(**d) for d in logs_to_insert])
            await session.commit()
            for _ in range(len(logs_to_insert)):
                queue.task_done()
        else:
            async for db_session in get_db_session():
                db_session.add_all([AuditLog(**d) for d in logs_to_insert])
                await db_session.commit()
                for _ in range(len(logs_to_insert)):
                    queue.task_done()
                break
    return len(logs_to_insert)


# ── Background Workers ────────────────────────────────────────────────────────

async def audit_log_batch_worker():
    """Worker gom log theo lô (batch) và ghi vào DB định kỳ — Production."""
    BATCH_SIZE = 50
    INTERVAL = 1
    queue = get_audit_log_queue()

    while True:
        try:
            await queue.get()
            queue.task_done()
            await asyncio.sleep(INTERVAL)
            await flush_audit_log_queue()
        except asyncio.CancelledError:
            await flush_audit_log_queue()
            break
        except Exception as e:
            print(f"[AuditWorker] Error: {e}")


async def audit_cleanup_worker():
    """Background worker dọn dẹp log cũ mỗi 24h theo cấu hình SystemSetting."""
    CLEANUP_INTERVAL = 24 * 3600

    while True:
        try:
            async for session in get_db_session():
                retention_val = await get_setting(session, "audit_retention_days", "90")
                retention_days = int(retention_val)
                deleted = await cleanup_audit_logs(session, retention_days)
                if deleted > 0:
                    print(f"[CleanupWorker] Auto-deleted {deleted} logs older than {retention_days} days.")
                break
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[CleanupWorker] Error: {e}")

        await asyncio.sleep(CLEANUP_INTERVAL)


# ── Query helpers ─────────────────────────────────────────────────────────────

async def get_audit_logs(
    session: AsyncSession,
    request_type: Optional[str] = None,
    system: Optional[str] = None,
    domain: Optional[str] = None,
    user: Optional[str] = None,
    status: Optional[str] = None,
    auth_status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, List[AuditLog]]:
    """
    Trả về (total, items) với đầy đủ filter bao gồm date range.
    """
    base = select(AuditLog)
    if request_type:
        base = base.where(AuditLog.request_type == request_type)
    if system:
        base = base.where(AuditLog.system == system)
    if domain:
        base = base.where(AuditLog.domain == domain)
    if user:
        base = base.where(AuditLog.user == user)
    if status:
        base = base.where(AuditLog.status == status)
    if auth_status:
        base = base.where(AuditLog.auth_status == auth_status)
    if from_date:
        base = base.where(AuditLog.request_time >= from_date)
    if to_date:
        base = base.where(AuditLog.request_time <= to_date)

    # Đếm tổng
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Lấy trang
    paged = base.order_by(AuditLog.request_time.desc()).limit(limit).offset(offset)
    result = await session.execute(paged)
    return total, result.scalars().all()


async def cleanup_audit_logs(session: AsyncSession, days: int) -> int:
    """Xóa log cũ hơn số ngày quy định."""
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = delete(AuditLog).where(AuditLog.request_time < threshold)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def get_audit_stats(session: AsyncSession) -> Dict[str, Any]:
    """
    Thống kê tổng hợp Audit Log cho dashboard.
    Trả về: tổng requests, counts theo trạng thái, top users.
    """
    # Tổng số
    total = (await session.execute(select(func.count(AuditLog.id)))).scalar_one()

    # Đếm theo status
    success_count = (
        await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.status == "success")
        )
    ).scalar_one()

    fail_count = (
        await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.status == "fail")
        )
    ).scalar_one()

    denied_count = (
        await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.auth_status == "denied")
        )
    ).scalar_one()

    # Thống kê theo loại request
    by_type_stmt = (
        select(
            AuditLog.request_type,
            func.count(AuditLog.id).label("total"),
            func.sum(case((AuditLog.status == "success", 1), else_=0)).label("success"),
            func.sum(case((AuditLog.status == "fail", 1), else_=0)).label("fail"),
            func.sum(case((AuditLog.auth_status == "denied", 1), else_=0)).label("denied"),
        )
        .group_by(AuditLog.request_type)
        .order_by(func.count(AuditLog.id).desc())
    )
    by_type_result = await session.execute(by_type_stmt)
    by_type = [
        {
            "request_type": row.request_type,
            "total": row.total,
            "success": row.success,
            "fail": row.fail,
            "denied": row.denied,
        }
        for row in by_type_result
    ]

    # Top 10 users active nhất
    top_users_stmt = (
        select(AuditLog.user, func.count(AuditLog.id).label("count"))
        .where(AuditLog.user.isnot(None))
        .group_by(AuditLog.user)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    top_users_result = await session.execute(top_users_stmt)
    top_users = [{"user": row.user, "count": row.count} for row in top_users_result]

    return {
        "total_requests": total,
        "total_success": success_count,
        "total_fail": fail_count,
        "total_denied": denied_count,
        "by_type": by_type,
        "top_users": top_users,
    }

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.core.database import get_db_session
from app.services.setting_service import get_setting

import asyncio

def get_audit_log_queue() -> asyncio.Queue:
    """
    Lấy hàng đợi tương ứng với Event Loop hiện tại.
    Gắn trực tiếp vào loop object để đảm bảo 100% không bao giờ bị lệch loop trong môi trường test/multiple.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.Queue()
        
    if not hasattr(loop, "_audit_log_queue"):
        loop._audit_log_queue = asyncio.Queue()
    return loop._audit_log_queue

async def create_audit_log(
    session: Optional[AsyncSession] = None,
    request_type: str = "unknown",
    **kwargs
):
    """
    Đẩy log vào hàng đợi (Buffer).
    """
    log_data = {
        "request_type": request_type,
        "request_time": datetime.utcnow(),
        "duration": kwargs.get("duration", 0.0), # Đảm bảo không bị null
        "total_token": kwargs.get("total_token", 0), # Đảm bảo không bị null
        **kwargs
    }
    queue = get_audit_log_queue()
    await queue.put(log_data)
    return None

async def flush_audit_log_queue(session: Optional[AsyncSession] = None):
    """
    Hàm tiện ích để đẩy toàn bộ log hiện có trong queue vào DB ngay lập tức.
    Hữu ích cho Testing hoặc Graceful Shutdown.
    """
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
            db_logs = [AuditLog(**data) for data in logs_to_insert]
            session.add_all(db_logs)
            await session.commit()
            for _ in range(len(logs_to_insert)):
                queue.task_done()
        else:
            async for db_session in get_db_session():
                db_logs = [AuditLog(**data) for data in logs_to_insert]
                db_session.add_all(db_logs)
                await db_session.commit()
                for _ in range(len(logs_to_insert)):
                    queue.task_done()
                break
    return len(logs_to_insert)

async def audit_log_batch_worker():
    """
    Worker gom log theo lô (batch) và ghi vào DB định kỳ. (Dành cho Production)
    """
    BATCH_SIZE = 50
    INTERVAL = 1
    queue = get_audit_log_queue()
    
    while True:
        try:
            # Chờ bản ghi đầu tiên (blocking)
            await queue.get()
            # Trả ngược lời gọi để flush xử lý
            queue.task_done()
            # Chờ thêm một chút để gom batch
            await asyncio.sleep(INTERVAL)
            # Flush sạch queue hiện có
            await flush_audit_log_queue()
        except asyncio.CancelledError:
            # Commit nốt trước khi exit
            await flush_audit_log_queue()
            break
        except Exception as e:
            print(f"[AuditWorker] Error: {e}")

async def cleanup_audit_logs(session: AsyncSession, days: int) -> int:
    """
    Xóa toàn bộ log cũ hơn số ngày quy định.
    """
    threshold = datetime.utcnow() - timedelta(days=days)
    stmt = delete(AuditLog).where(AuditLog.request_time < threshold)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount

async def audit_cleanup_worker():
    """
    Background worker chạy định kỳ (mỗi 24h) để dọn dẹp log cũ theo cấu hình.
    """
    CLEANUP_INTERVAL = 24 * 3600 # 24 giờ
    
    while True:
        try:
            async for session in get_db_session():
                # Lấy số ngày lưu trữ từ SystemSetting (Mặc định 90 ngày nếu chưa set)
                retention_val = await get_setting(session, "audit_retention_days", "90")
                retention_days = int(retention_val)
                
                deleted_count = await cleanup_audit_logs(session, retention_days)
                if deleted_count > 0:
                    print(f"[CleanupWorker] Auto-deleted {deleted_count} logs older than {retention_days} days.")
                break # Thành công thoát session loop
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[CleanupWorker] Error: {e}")
            
        await asyncio.sleep(CLEANUP_INTERVAL)

async def get_audit_logs(
    session: AsyncSession,
    request_type: Optional[str] = None,
    system: Optional[str] = None,
    domain: Optional[str] = None,
    user: Optional[str] = None,
    status: Optional[str] = None,
    auth_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    stmt = select(AuditLog)
    if request_type: stmt = stmt.where(AuditLog.request_type == request_type)
    if system: stmt = stmt.where(AuditLog.system == system)
    if domain: stmt = stmt.where(AuditLog.domain == domain)
    if user: stmt = stmt.where(AuditLog.user == user)
    if status: stmt = stmt.where(AuditLog.status == status)
    if auth_status: stmt = stmt.where(AuditLog.auth_status == auth_status)
    stmt = stmt.order_by(AuditLog.request_time.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()

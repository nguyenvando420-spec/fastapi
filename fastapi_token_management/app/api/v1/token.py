from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user, check_user_permissions
from app.core.database import get_db_session, get_token_db_session
from app.schemas.token import (
    TokenizeRequest, TokenizeResponse,
    DeTokenizeRequest, DeTokenizeResponse,
    TokenStatsResponse,
)
from app.services.token_service import (
    tokenize_data_service,
    detokenize_data_service,
    get_token_stats,
)
from app.models.rbac import User

router = APIRouter()


@router.post("/tokenize", response_model=TokenizeResponse, status_code=status.HTTP_201_CREATED)
async def tokenize_bulk(
    req: TokenizeRequest,
    admin_session: AsyncSession = Depends(get_db_session),
    token_session: AsyncSession = Depends(get_token_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Tokenize hàng loạt (tối đa 1.000 items/request).
    Tự động idempotent: token cùng giá trị sẽ không được tạo lại.
    Yêu cầu quyền write trên `<system>:<domain>`.
    """
    resource = f"{req.system_name}:{req.domain_name}"
    await check_user_permissions(current_user, admin_session, resource, "write")

    result = await tokenize_data_service(admin_session, token_session, req, current_user)
    return TokenizeResponse(**result)


@router.post("/detokenize", response_model=DeTokenizeResponse)
async def detokenize_bulk(
    req: DeTokenizeRequest,
    admin_session: AsyncSession = Depends(get_db_session),
    token_session: AsyncSession = Depends(get_token_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Giải mã hàng loạt (tối đa 1.000 token/request).
    Response bao gồm `missing_tokens` — danh sách token không tìm thấy trong DB.
    Yêu cầu quyền read trên `<system>:<domain>`.
    """
    resource = f"{req.system_name}:{req.domain_name}"
    await check_user_permissions(current_user, admin_session, resource, "read")

    result = await detokenize_data_service(admin_session, token_session, req, current_user)
    return DeTokenizeResponse(**result)


@router.get("/stats", response_model=TokenStatsResponse)
async def token_stats(
    admin_session: AsyncSession = Depends(get_db_session),
    token_session: AsyncSession = Depends(get_token_db_session),
    current_user: User = Depends(get_current_active_user),
    system_name: Optional[str] = Query(None, description="Lọc theo tên System"),
):
    """
    Thống kê số lượng token đã lưu trong từng Domain.
    Chỉ superuser hoặc user có quyền admin:system:read mới xem được.
    """
    await check_user_permissions(current_user, admin_session, "admin:system", "read")
    stats = await get_token_stats(admin_session, token_session, system_name)
    return TokenStatsResponse(items=stats)

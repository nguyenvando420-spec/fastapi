from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_db_session, get_token_db_session
from app.schemas.token import TokenizeRequest, TokenizeResponse, DeTokenizeRequest, DeTokenizeResponse
from app.services.token_service import tokenize_data_service, detokenize_data_service
from app.models.rbac import User

router = APIRouter()

@router.post("/tokenize", response_model=TokenizeResponse, status_code=status.HTTP_201_CREATED)
async def tokenize_bulk(
    req: TokenizeRequest, 
    admin_session: AsyncSession = Depends(get_db_session),
    token_session: AsyncSession = Depends(get_token_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Endpoint thực hiện Tokenization hàng loạt cho một Domain cụ thể.
    """
    # RBAC Enforcement: Kiểm tra quyền write trên system:domain
    from app.api.dependencies import check_user_permissions
    resource = f"{req.system_name}:{req.domain_name}"
    await check_user_permissions(current_user, admin_session, resource, "write")
    
    return await tokenize_data_service(admin_session, token_session, req, current_user)

@router.post("/detokenize", response_model=DeTokenizeResponse)
async def detokenize_bulk(
    req: DeTokenizeRequest, 
    admin_session: AsyncSession = Depends(get_db_session),
    token_session: AsyncSession = Depends(get_token_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Endpoint thực hiện Giải mã (De-tokenize) hàng loạt dựa trên danh sách Token.
    """
    # RBAC Enforcement: Kiểm tra quyền read trên system:domain
    from app.api.dependencies import check_user_permissions
    resource = f"{req.system_name}:{req.domain_name}"
    await check_user_permissions(current_user, admin_session, resource, "read")
    
    decrypted_mapping = await detokenize_data_service(admin_session, token_session, req, current_user)
    return {"results": decrypted_mapping}

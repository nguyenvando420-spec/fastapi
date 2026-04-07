from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.dependencies import SessionDep, require_permissions
from app.schemas.rbac import UserCreate, UserResponse, Token
from app.services.rbac_service import create_user
from app.models.rbac import User
from app.core.security import verify_password, create_access_token
from sqlalchemy import select

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate, 
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "create"))
):
    """
    Tạo tài khoản User mới trên hệ thống (Yêu cầu quyền admin:users:create)
    """
    user = await create_user(session, user_in)
    return user

@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
):
    """
    API xác thực: Nhập Username & Password => Lấy JWT Access Token để dùng cho tác vụ hệ thống
    """
    stmt = select(User).where(User.username == form_data.username)
    user = (await session.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai username hoặc password bảo mật",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản bị khoá chặn")
        
    # Tạo JWT token cho User này
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

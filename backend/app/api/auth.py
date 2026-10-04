from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, serialize_user
from backend.app.core.security import create_access_token, verify_password
from backend.app.database.session import get_db
from backend.app.models.entities import User
from backend.app.schemas.auth import LoginRequest
from backend.app.services.audit import write_operation_log


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        write_operation_log(
            db, "login", "auth", "用户名或密码错误", user=user,
            ip_address=request.client.host if request.client else "127.0.0.1", success=False,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    role_codes = [role.code for role in user.roles]
    token = create_access_token(user.id, user.username, role_codes)
    write_operation_log(
        db, "login", "auth", "登录成功", user=user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)


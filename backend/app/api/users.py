from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_permissions, serialize_user
from backend.app.core.security import hash_password
from backend.app.database.session import get_db
from backend.app.models.entities import Role, User
from backend.app.schemas.auth import UserCreate, UserUpdate
from backend.app.services.audit import write_operation_log


router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _current: User = Depends(require_permissions("users:manage")),
) -> list[dict]:
    return [serialize_user(user) for user in db.scalars(select(User).order_by(User.id)).all()]


@router.post("")
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("users:manage")),
) -> dict:
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    role = db.scalar(select(Role).where(Role.code == payload.role_code))
    if role is None:
        raise HTTPException(status_code=400, detail="角色不存在")
    user = User(
        username=payload.username, display_name=payload.display_name,
        password_hash=hash_password(payload.password), roles=[role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_operation_log(db, "create_user", f"user:{user.id}", f"创建用户 {user.username}", current, request.client.host)
    return serialize_user(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("users:manage")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        if user.id == current.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="不能停用当前登录用户")
        user.is_active = payload.is_active
    if payload.role_code is not None:
        role = db.scalar(select(Role).where(Role.code == payload.role_code))
        if role is None:
            raise HTTPException(status_code=400, detail="角色不存在")
        user.roles = [role]
    db.commit()
    db.refresh(user)
    write_operation_log(db, "update_user", f"user:{user.id}", f"更新用户 {user.username}", current, request.client.host)
    return serialize_user(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("users:manage")),
) -> dict:
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    username = user.username
    db.delete(user)
    db.commit()
    write_operation_log(db, "delete_user", f"user:{user_id}", f"删除用户 {username}", current, request.client.host)
    return {"message": "用户已删除"}


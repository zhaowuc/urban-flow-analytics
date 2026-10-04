from __future__ import annotations

import json
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.database.session import get_db
from backend.app.models.entities import User


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录系统")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    return user


def permissions_for(user: User) -> set[str]:
    values: set[str] = set()
    for role in user.roles:
        try:
            values.update(json.loads(role.permissions))
        except json.JSONDecodeError:
            continue
    return values


def require_permissions(*required: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        current = permissions_for(user)
        if not set(required).issubset(current):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权执行此操作")
        return user

    return dependency


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "roles": [{"code": role.code, "name": role.name} for role in user.roles],
        "permissions": sorted(permissions_for(user)),
        "created_at": user.created_at.isoformat(),
    }


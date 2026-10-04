from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import OperationLog, User


router = APIRouter(prefix="/logs", tags=["操作日志"])


@router.get("")
def list_logs(
    username: str | None = None,
    action: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _current: User = Depends(require_permissions("logs:view")),
) -> list[dict]:
    query = select(OperationLog)
    if username:
        query = query.where(OperationLog.username == username)
    if action:
        query = query.where(OperationLog.action == action)
    if start:
        query = query.where(OperationLog.created_at >= start)
    if end:
        query = query.where(OperationLog.created_at <= end)
    records = db.scalars(query.order_by(OperationLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": item.id, "username": item.username, "action": item.action,
            "resource": item.resource, "detail": item.detail, "ip_address": item.ip_address,
            "success": item.success, "created_at": item.created_at.isoformat(),
        }
        for item in records
    ]


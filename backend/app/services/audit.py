from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.entities import OperationLog, User


def write_operation_log(
    db: Session,
    action: str,
    resource: str,
    detail: str = "",
    user: User | None = None,
    ip_address: str = "127.0.0.1",
    success: bool = True,
) -> OperationLog:
    record = OperationLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        resource=resource,
        detail=detail,
        ip_address=ip_address,
        success=success,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


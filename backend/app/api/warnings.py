from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import DecisionRecord, User, Warning
from backend.app.services.audit import write_operation_log
from backend.app.services.warnings import generate_warnings


router = APIRouter(tags=["预警与决策"])


def serialize_warning(item: Warning) -> dict:
    return {
        "id": item.id, "station_id": item.station_code, "region": item.region,
        "current_flow": item.current_flow, "predicted_flow": item.predicted_flow,
        "capacity": item.capacity, "load_rate": item.load_rate, "level": item.level,
        "source": item.source, "status": item.status, "message": item.message, "created_at": item.created_at.isoformat(),
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }


@router.get("/warnings")
def list_warnings(
    status: str | None = "active",
    level: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("warnings:view")),
) -> list[dict]:
    query = select(Warning)
    if status:
        query = query.where(Warning.status == status)
    if level:
        query = query.where(Warning.level == level)
    return [serialize_warning(item) for item in db.scalars(query.order_by(Warning.created_at.desc())).all()]


@router.post("/warnings/generate")
def generate(
    task_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("prediction:manage")),
) -> dict:
    try:
        result = generate_warnings(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_operation_log(db, "warning_generate", "warnings", f"生成 {result['created_count']} 条预警", current)
    return result


@router.put("/warnings/{warning_id}/resolve")
def resolve_warning(
    warning_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("prediction:manage")),
) -> dict:
    warning = db.get(Warning, warning_id)
    if warning is None:
        raise HTTPException(status_code=404, detail="预警不存在")
    warning.status = "resolved"
    warning.resolved_at = datetime.now()
    db.commit()
    write_operation_log(db, "warning_resolve", f"warning:{warning.id}", "解除预警", current)
    return serialize_warning(warning)


@router.get("/decisions")
def list_decisions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("warnings:view")),
) -> list[dict]:
    records = db.scalars(select(DecisionRecord).order_by(DecisionRecord.created_at.desc()).limit(200)).all()
    return [
        {
            "id": item.id, "warning_id": item.warning_id, "category": item.category,
            "suggestion": item.suggestion, "rationale": item.rationale,
            "status": item.status, "created_at": item.created_at.isoformat(),
        }
        for item in records
    ]

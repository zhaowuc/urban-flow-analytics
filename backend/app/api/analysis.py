from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import AnalysisTask, User
from backend.app.services.analysis import create_analysis_task, latest_analysis, load_result
from backend.app.services.audit import write_operation_log


router = APIRouter(prefix="/analysis", tags=["Spark 离线分析"])


def serialize_task(item: AnalysisTask) -> dict:
    return {
        "id": item.id, "analysis_type": item.analysis_type, "status": item.status,
        "parameters": json.loads(item.parameters or "{}"), "input_count": item.input_count,
        "output_count": item.output_count, "duration_ms": item.duration_ms,
        "error_message": item.error_message,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
    }


class AnalysisRequest(BaseModel):
    analysis_type: str = "full"
    dataset_id: int | None = None
    parameters: dict = Field(default_factory=dict)


@router.post("/tasks")
def start_analysis(
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("analysis:run")),
) -> dict:
    try:
        task = create_analysis_task(payload.analysis_type, payload.dataset_id, current.id, payload.parameters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_operation_log(db, "spark_analysis", f"analysis:{task.id}", f"启动 {payload.analysis_type} 分析", current)
    return serialize_task(task)


@router.get("/tasks")
def list_analysis_tasks(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("statistics:view")),
) -> list[dict]:
    return [serialize_task(item) for item in db.scalars(select(AnalysisTask).order_by(AnalysisTask.id.desc())).all()]


@router.get("/tasks/{task_id}")
def get_analysis_task(
    task_id: int,
    include_result: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("statistics:view")),
) -> dict:
    task = db.get(AnalysisTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    response = serialize_task(task)
    if include_result and task.status == "completed":
        response["result"] = load_result(task)
    return response


@router.get("/latest")
def get_latest_analysis(_user: User = Depends(get_current_user)) -> dict:
    try:
        task, result = latest_analysis()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"task": serialize_task(task), "result": result}

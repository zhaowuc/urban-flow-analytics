from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import PredictionResult, PredictionTask, User
from backend.app.services.audit import write_operation_log
from backend.app.services.predictions import (
    create_prediction_task, latest_model_comparison, prediction_task_result,
)


router = APIRouter(prefix="/models", tags=["客流预测"])


def serialize_task(item: PredictionTask) -> dict:
    return {
        "id": item.id, "model_type": item.model_type, "target": item.target, "status": item.status,
        "parameters": json.loads(item.parameters or "{}"), "metrics": json.loads(item.metrics or "{}"),
        "model_path": item.model_path, "error_message": item.error_message,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
    }


class TrainRequest(BaseModel):
    model_type: str
    target: str = "S001"
    dataset_id: int | None = None
    parameters: dict = Field(default_factory=dict)


@router.post("/train")
def train_model(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("prediction:manage")),
) -> dict:
    try:
        task = create_prediction_task(payload.model_type, payload.target, payload.dataset_id, current.id, payload.parameters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_operation_log(db, "model_train", f"prediction:{task.id}", f"训练模型 {payload.model_type}", current)
    return serialize_task(task)


@router.get("/tasks")
def model_tasks(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("prediction:view")),
) -> list[dict]:
    return [serialize_task(item) for item in db.scalars(select(PredictionTask).order_by(PredictionTask.id.desc())).all()]


@router.get("/tasks/{task_id}")
def model_task(
    task_id: int,
    include_result: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("prediction:view")),
) -> dict:
    task = db.get(PredictionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="模型任务不存在")
    response = serialize_task(task)
    if include_result and task.status == "completed":
        response["result"] = prediction_task_result(task)
    return response


@router.post("/tasks/{task_id}/predict")
def use_prediction(
    task_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("prediction:manage")),
) -> dict:
    task = db.get(PredictionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="模型任务不存在")
    try:
        result = prediction_task_result(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_operation_log(db, "model_predict", f"prediction:{task.id}", f"调用 {task.model_type} 预测结果", current)
    return result


@router.get("/comparison")
def model_comparison(_user: User = Depends(require_permissions("prediction:view"))) -> list[dict]:
    return latest_model_comparison()


@router.get("/results/latest")
def latest_predictions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("prediction:view")),
) -> list[dict]:
    latest_ids = []
    for model_type in ("arima", "random_forest", "gbt"):
        task = db.scalar(
            select(PredictionTask).where(PredictionTask.model_type == model_type, PredictionTask.status == "completed")
            .order_by(PredictionTask.completed_at.desc())
        )
        if task:
            latest_ids.append(task.id)
    if not latest_ids:
        return []
    rows = db.scalars(
        select(PredictionResult).where(PredictionResult.task_id.in_(latest_ids)).order_by(PredictionResult.predicted_at)
    ).all()
    return [
        {
            "id": item.id, "task_id": item.task_id, "station_id": item.station_code,
            "route_id": item.route_code, "region": item.region, "horizon_minutes": item.horizon_minutes,
            "predicted_value": item.predicted_value, "actual_value": item.actual_value,
            "predicted_at": item.predicted_at.isoformat(),
        }
        for item in rows
    ]


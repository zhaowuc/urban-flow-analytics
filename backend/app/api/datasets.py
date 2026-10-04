from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import Dataset, PreprocessingTask, User
from backend.app.services.audit import write_operation_log
from backend.app.services.datasets import (
    create_preprocessing_task, preview_dataset, register_demo_dataset, save_upload, storage_summary,
)


router = APIRouter(tags=["数据管理"])


def serialize_dataset(item: Dataset) -> dict:
    return {
        "id": item.id, "name": item.name, "source": item.source, "file_type": item.file_type,
        "size_bytes": item.size_bytes, "row_count": item.row_count, "status": item.status,
        "processing_status": item.processing_status, "created_at": item.created_at.isoformat(),
    }


def serialize_task(item: PreprocessingTask) -> dict:
    return {
        "id": item.id, "dataset_id": item.dataset_id, "status": item.status,
        "options": json.loads(item.options or "{}"), "report": json.loads(item.report or "{}"),
        "error_message": item.error_message,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
    }


@router.get("/datasets")
def list_datasets(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("data:manage")),
) -> list[dict]:
    return [serialize_dataset(item) for item in db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()]


@router.post("/datasets/upload")
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("data:manage")),
) -> dict:
    try:
        dataset = save_upload(file, current.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_operation_log(db, "upload_dataset", f"dataset:{dataset.id}", f"上传 {dataset.name}", current)
    return serialize_dataset(dataset)


@router.get("/datasets/{dataset_id}/preview")
def dataset_preview(
    dataset_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("data:manage")),
) -> dict:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    try:
        return preview_dataset(dataset, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class PreprocessRequest(BaseModel):
    missing_strategy: str = "fill"


@router.post("/datasets/{dataset_id}/preprocess")
def preprocess_dataset(
    dataset_id: int,
    payload: PreprocessRequest,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("data:manage")),
) -> dict:
    try:
        task = create_preprocessing_task(dataset_id, current.id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    write_operation_log(db, "preprocess_dataset", f"dataset:{dataset_id}", f"创建清洗任务 {task.id}", current)
    return serialize_task(task)


@router.get("/preprocessing/tasks")
def preprocessing_tasks(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("data:manage")),
) -> list[dict]:
    return [serialize_task(item) for item in db.scalars(select(PreprocessingTask).order_by(PreprocessingTask.id.desc())).all()]


@router.get("/preprocessing/tasks/{task_id}")
def preprocessing_task(
    task_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("data:manage")),
) -> dict:
    task = db.get(PreprocessingTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="清洗任务不存在")
    return serialize_task(task)


@router.get("/storage/summary")
def get_storage_summary(_user: User = Depends(require_permissions("data:manage"))) -> dict:
    return storage_summary()


@router.post("/datasets/restore-demo")
def restore_demo_dataset(
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("data:manage")),
) -> dict:
    dataset = register_demo_dataset()
    write_operation_log(db, "restore_demo", f"dataset:{dataset.id}", "恢复统一虚拟城市演示数据", current)
    return serialize_dataset(dataset)


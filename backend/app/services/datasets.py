from __future__ import annotations

import json
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import Dataset, PreprocessingTask
from backend.app.services.demo_data import write_demo_files
from backend.app.spark.session import get_spark
from spark_jobs.preprocessing.clean_passenger_flow import clean_dataset


ALLOWED_SUFFIXES = {".csv", ".json", ".xlsx"}
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="data-task")
_task_lock = threading.Lock()


def _read_frame(path: Path, limit: int | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, nrows=limit, encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                return pd.read_csv(path, nrows=limit, encoding="gb18030")
            except UnicodeDecodeError as exc:
                raise ValueError("CSV 编码无法识别，请使用 UTF-8 或 GB18030") from exc
    if suffix == ".json":
        try:
            return pd.read_json(path, lines=True, nrows=limit)
        except ValueError:
            try:
                frame = pd.read_json(path)
                return frame.head(limit) if limit else frame
            except ValueError as exc:
                raise ValueError("JSON 格式错误，请提供数组或 JSON Lines 格式") from exc
    if suffix == ".xlsx":
        try:
            return pd.read_excel(path, nrows=limit, engine="openpyxl")
        except Exception as exc:
            raise ValueError("Excel 文件无法读取，请确认文件未损坏且格式为 XLSX") from exc
    raise ValueError("仅支持 CSV、JSON 和 XLSX 文件")


def register_demo_dataset() -> Dataset:
    paths = write_demo_files()
    with SessionLocal() as db:
        existing = db.scalar(select(Dataset).where(Dataset.source == "built_in_demo"))
        if existing:
            return existing
        csv_path = paths["csv"]
        row_count = sum(1 for _ in csv_path.open("r", encoding="utf-8-sig")) - 1
        dataset = Dataset(
            name="星海示例市客流数据（内置）",
            stored_path=str(csv_path.relative_to(settings.app_home)),
            source="built_in_demo",
            file_type="csv",
            size_bytes=csv_path.stat().st_size,
            row_count=row_count,
            status="ready",
            processing_status="pending",
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset


def save_upload(upload: UploadFile, user_id: int) -> Dataset:
    original_name = Path(upload.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("文件类型不支持，请上传 CSV、JSON 或 XLSX")
    target_name = f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}{suffix}"
    target = settings.app_home / "data" / "upload" / target_name
    with target.open("wb") as output:
        shutil.copyfileobj(upload.file, output)
    if target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise ValueError("上传文件为空")
    frame = _read_frame(target)
    if frame.empty:
        target.unlink(missing_ok=True)
        raise ValueError("文件没有可用数据行")
    with SessionLocal() as db:
        dataset = Dataset(
            name=original_name,
            stored_path=str(target.relative_to(settings.app_home)),
            source="upload",
            file_type=suffix.lstrip("."),
            size_bytes=target.stat().st_size,
            row_count=len(frame),
            status="ready",
            processing_status="pending",
            created_by=user_id,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset


def preview_dataset(dataset: Dataset, limit: int = 50) -> dict:
    path = settings.app_home / dataset.stored_path
    frame = _read_frame(path, limit=limit)
    frame = frame.where(pd.notnull(frame), None)
    return {"columns": list(frame.columns), "rows": frame.to_dict(orient="records"), "total": dataset.row_count}


def create_preprocessing_task(dataset_id: int, user_id: int, options: dict) -> PreprocessingTask:
    with SessionLocal() as db:
        dataset = db.get(Dataset, dataset_id)
        if dataset is None:
            raise ValueError("数据集不存在")
        task = PreprocessingTask(
            dataset_id=dataset_id,
            status="pending",
            options=json.dumps(options, ensure_ascii=False),
            created_by=user_id,
        )
        dataset.processing_status = "queued"
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    executor.submit(run_preprocessing_task, task_id)
    with SessionLocal() as db:
        return db.get(PreprocessingTask, task_id)


def run_preprocessing_task(task_id: int) -> None:
    with _task_lock:
        with SessionLocal() as db:
            task = db.get(PreprocessingTask, task_id)
            if task is None:
                return
            dataset = db.get(Dataset, task.dataset_id)
            task.status = "running"
            task.started_at = datetime.now()
            dataset.processing_status = "processing"
            db.commit()
            source_path = settings.app_home / dataset.stored_path
            options = json.loads(task.options)
        try:
            report = clean_dataset(
                get_spark(), source_path,
                settings.app_home / "data" / "parquet" / f"dataset_id={dataset.id}",
                settings.app_home / "config" / "demo_city_catalog.json",
                settings.app_home / "work" / "xlsx-bridge",
                missing_strategy=options.get("missing_strategy", "fill"),
            )
            with SessionLocal() as db:
                task = db.get(PreprocessingTask, task_id)
                dataset = db.get(Dataset, task.dataset_id)
                task.status = "completed"
                task.report = json.dumps(report, ensure_ascii=False)
                task.completed_at = datetime.now()
                dataset.processing_status = "completed"
                db.commit()
        except Exception as exc:
            with SessionLocal() as db:
                task = db.get(PreprocessingTask, task_id)
                dataset = db.get(Dataset, task.dataset_id)
                task.status = "failed"
                task.error_message = str(exc)
                task.completed_at = datetime.now()
                dataset.processing_status = "failed"
                db.commit()


def storage_summary() -> dict:
    def summarize(relative: str) -> dict:
        root = settings.app_home / relative
        files = [path for path in root.rglob("*") if path.is_file()]
        return {"path": relative, "file_count": len(files), "size_bytes": sum(path.stat().st_size for path in files)}

    parquet_root = settings.app_home / "data" / "parquet"
    partitions = sorted(
        str(path.relative_to(parquet_root)).replace("\\", "/")
        for path in parquet_root.rglob("*") if path.is_dir() and "=" in path.name
    )
    return {
        "mode": "Spark Local 离线部署模式",
        "format": "Parquet + Snappy + SQLite",
        "locations": [summarize(item) for item in ["data/raw", "data/upload", "data/clean", "data/parquet"]],
        "partitions": partitions[:500],
    }


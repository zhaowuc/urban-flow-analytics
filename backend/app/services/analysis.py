from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import AnalysisTask, PreprocessingTask
from backend.app.spark.session import get_spark
from spark_jobs.batch.passenger_flow_analysis import run_full_analysis


executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis-task")


def _resolve_parquet_path(dataset_id: int | None) -> Path:
    if dataset_id is not None:
        target = settings.app_home / "data" / "parquet" / f"dataset_id={dataset_id}"
        if target.exists():
            return target
    with SessionLocal() as db:
        tasks = db.scalars(
            select(PreprocessingTask).where(PreprocessingTask.status == "completed").order_by(PreprocessingTask.id.desc())
        ).all()
        for task in tasks:
            report = json.loads(task.report or "{}")
            if report.get("output_path"):
                path = Path(report["output_path"])
                if path.exists():
                    return path
    fallback = settings.app_home / "data" / "parquet" / "dataset_id=1"
    if fallback.exists():
        return fallback
    raise ValueError("尚无可分析的 Parquet 数据，请先完成数据预处理")


def create_analysis_task(analysis_type: str, dataset_id: int | None, user_id: int, parameters: dict) -> AnalysisTask:
    if analysis_type not in {"full", "total", "time", "region", "station", "route", "transport", "od"}:
        raise ValueError("不支持的分析类型")
    parquet_path = _resolve_parquet_path(dataset_id)
    params = {**parameters, "dataset_id": dataset_id, "parquet_path": str(parquet_path)}
    with SessionLocal() as db:
        task = AnalysisTask(
            analysis_type=analysis_type, status="pending",
            parameters=json.dumps(params, ensure_ascii=False), created_by=user_id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    executor.submit(run_analysis_task, task_id)
    with SessionLocal() as db:
        return db.get(AnalysisTask, task_id)


def run_analysis_task(task_id: int) -> None:
    started = time.perf_counter()
    with SessionLocal() as db:
        task = db.get(AnalysisTask, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = datetime.now()
        parameters = json.loads(task.parameters)
        db.commit()
    try:
        result = run_full_analysis(get_spark(), Path(parameters["parquet_path"]))
        result_path = settings.app_home / "data" / "result" / f"analysis_{task_id}.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        with SessionLocal() as db:
            task = db.get(AnalysisTask, task_id)
            task.status = "completed"
            task.result_path = str(result_path.relative_to(settings.app_home))
            task.input_count = int(result["input_count"])
            task.output_count = sum(len(value) for value in result.values() if isinstance(value, list))
            task.duration_ms = int((time.perf_counter() - started) * 1000)
            task.completed_at = datetime.now()
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(AnalysisTask, task_id)
            task.status = "failed"
            task.error_message = str(exc)
            task.duration_ms = int((time.perf_counter() - started) * 1000)
            task.completed_at = datetime.now()
            db.commit()


def load_result(task: AnalysisTask) -> dict:
    if task.status != "completed" or not task.result_path:
        raise ValueError("分析任务尚未完成")
    path = settings.app_home / task.result_path
    if not path.exists():
        raise ValueError("分析结果文件不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def latest_analysis() -> tuple[AnalysisTask, dict]:
    with SessionLocal() as db:
        task = db.scalar(
            select(AnalysisTask).where(AnalysisTask.status == "completed").order_by(AnalysisTask.completed_at.desc())
        )
        if task is None:
            raise ValueError("尚无已完成的分析结果")
        db.expunge(task)
    return task, load_result(task)


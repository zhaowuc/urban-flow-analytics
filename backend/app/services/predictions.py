from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import PredictionResult, PredictionTask
from backend.app.services.analysis import _resolve_parquet_path
from backend.app.spark.session import get_spark
from spark_jobs.ml.train_models import train_arima, train_spark_regression


executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prediction-task")


def create_prediction_task(model_type: str, target: str, dataset_id: int | None, user_id: int, parameters: dict) -> PredictionTask:
    if model_type not in {"arima", "random_forest", "gbt"}:
        raise ValueError("模型类型只能是 arima、random_forest 或 gbt")
    parquet_path = _resolve_parquet_path(dataset_id)
    params = {**parameters, "dataset_id": dataset_id, "parquet_path": str(parquet_path)}
    with SessionLocal() as db:
        task = PredictionTask(
            model_type=model_type, target=target or "S001", status="pending",
            parameters=json.dumps(params, ensure_ascii=False), created_by=user_id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    executor.submit(run_prediction_task, task_id)
    with SessionLocal() as db:
        return db.get(PredictionTask, task_id)


def run_prediction_task(task_id: int) -> None:
    with SessionLocal() as db:
        task = db.get(PredictionTask, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = datetime.now()
        parameters = json.loads(task.parameters)
        model_type = task.model_type
        target = task.target
        db.commit()
    try:
        spark = get_spark()
        if model_type == "arima":
            model_path = settings.app_home / "models" / f"arima_task_{task_id}.pkl"
            result = train_arima(spark, Path(parameters["parquet_path"]), target, model_path)
        else:
            model_path = settings.app_home / "models" / f"{model_type}_task_{task_id}"
            result = train_spark_regression(spark, Path(parameters["parquet_path"]), model_type, model_path)
        result_path = settings.app_home / "data" / "result" / f"prediction_{task_id}.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        with SessionLocal() as db:
            task = db.get(PredictionTask, task_id)
            task.status = "completed"
            task.metrics = json.dumps({**result["metrics"], "result_path": str(result_path.relative_to(settings.app_home))}, ensure_ascii=False)
            task.model_path = str(model_path.relative_to(settings.app_home))
            task.completed_at = datetime.now()
            for item in result["future"]:
                db.add(PredictionResult(
                    task_id=task_id, station_code=item["station_id"], route_code=item.get("route_id"),
                    region=item.get("region"), horizon_minutes=item["horizon_minutes"],
                    predicted_value=item["predicted_value"], actual_value=item.get("actual_value"),
                    predicted_at=datetime.fromisoformat(item["predicted_at"]),
                ))
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(PredictionTask, task_id)
            task.status = "failed"
            task.error_message = str(exc)
            task.completed_at = datetime.now()
            db.commit()


def prediction_task_result(task: PredictionTask) -> dict:
    metrics = json.loads(task.metrics or "{}")
    result_path = metrics.get("result_path")
    if task.status != "completed" or not result_path:
        raise ValueError("模型任务尚未完成")
    return json.loads((settings.app_home / result_path).read_text(encoding="utf-8"))


def latest_model_comparison() -> list[dict]:
    result = []
    with SessionLocal() as db:
        for model_type in ("arima", "random_forest", "gbt"):
            task = db.scalar(
                select(PredictionTask)
                .where(PredictionTask.model_type == model_type, PredictionTask.status == "completed")
                .order_by(PredictionTask.completed_at.desc())
            )
            if task:
                metrics = json.loads(task.metrics or "{}")
                result.append({
                    "task_id": task.id, "model_type": model_type, "target": task.target,
                    "mae": metrics.get("mae"), "rmse": metrics.get("rmse"), "r2": metrics.get("r2"),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                })
    return result


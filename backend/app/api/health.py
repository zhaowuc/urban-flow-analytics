from __future__ import annotations

import os

from fastapi import APIRouter
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import PredictionTask
from backend.app.spark.session import spark_manager


router = APIRouter(tags=["系统健康"])


@router.get("/health")
def health() -> dict:
    database = {"ok": False, "status": "异常"}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database = {"ok": True, "status": "正常", "path": "data/database/system.db"}
    except Exception as exc:
        database["detail"] = str(exc)

    data_directory = {"ok": False, "status": "不可写"}
    try:
        target = settings.app_home / "data" / ".healthcheck"
        target.write_text("ok", encoding="utf-8")
        target.unlink()
        data_directory = {"ok": True, "status": "正常", "path": "data/"}
    except OSError as exc:
        data_directory["detail"] = str(exc)

    model_files = list((settings.app_home / "models").glob("**/*"))
    with SessionLocal() as db:
        completed_models = db.query(PredictionTask).filter(PredictionTask.status == "completed").count()
    models = {
        "ok": completed_models > 0 or any(path.is_file() for path in model_files),
        "status": "正常" if completed_models > 0 or any(path.is_file() for path in model_files) else "尚未训练",
        "count": completed_models,
    }
    return {
        "web": {"ok": True, "status": "正常", "bind": "127.0.0.1"},
        "database": database,
        "spark": spark_manager.status(),
        "models": models,
        "data_directory": data_directory,
        "deployment_mode": "Spark Local 离线部署模式",
        "pid": os.getpid(),
    }


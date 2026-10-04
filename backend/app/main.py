from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import api_router
from backend.app.core.config import ensure_runtime_directories, settings
from backend.app.database.init_db import initialize_database
from backend.app.services.datasets import register_demo_dataset
from backend.app.services.realtime import realtime_simulator
from backend.app.spark.session import spark_manager


def configure_logging() -> None:
    ensure_runtime_directories()
    handler = RotatingFileHandler(settings.log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(item, RotatingFileHandler) for item in root.handlers):
        root.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    initialize_database()
    register_demo_dataset()
    spark_manager.warm_async()
    yield
    realtime_simulator.stop()
    spark_manager.stop()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "请求参数不正确", "errors": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("urban_flow").exception("Unhandled error at %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "系统暂时无法处理该请求，详细信息已写入日志"})


@app.get("/api")
def api_root() -> dict:
    return {"name": settings.app_name, "version": "1.0.0", "mode": "Spark Local 离线部署模式"}


if settings.frontend_dist.exists():
    assets_dir = settings.frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        candidate = settings.frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def development_root() -> dict:
        return {"message": "前端尚未构建，请在开发模式运行 Vite。", "api": "/docs"}

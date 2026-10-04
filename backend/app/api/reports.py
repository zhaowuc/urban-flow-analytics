from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.app.api.deps import require_permissions
from backend.app.core.config import settings
from backend.app.models.entities import User
from backend.app.services.reports import generate_decision_report


router = APIRouter(prefix="/reports", tags=["决策报告"])


@router.post("/generate")
def generate_report(_user: User = Depends(require_permissions("report:view"))) -> dict:
    try:
        relative_path, content = generate_decision_report()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": relative_path, "html": content}


@router.get("/download")
def download_report(path: str, _user: User = Depends(require_permissions("report:view"))):
    target = (settings.app_home / path).resolve()
    allowed = (settings.app_home / "data" / "result").resolve()
    if allowed not in target.parents or target.suffix.lower() != ".html" or not target.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")
    return FileResponse(target, media_type="text/html", filename=target.name)


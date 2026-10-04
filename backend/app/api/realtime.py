from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import User
from backend.app.services.audit import write_operation_log
from backend.app.services.realtime import realtime_simulator


router = APIRouter(prefix="/realtime", tags=["实时客流"])


@router.get("/status")
def status(_user: User = Depends(require_permissions("dashboard:view"))) -> dict:
    return realtime_simulator.snapshot()


@router.post("/start")
def start(
    request: Request,
    speed: int = 60,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("realtime:manage")),
) -> dict:
    if speed not in {60, 120}:
        raise HTTPException(status_code=400, detail="演示加速倍数仅支持 60 或 120")
    try:
        result = realtime_simulator.start(speed)
        write_operation_log(db, "realtime_start", "structured_streaming", f"启动实时模拟 ×{speed}", current, request.client.host)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pause")
def pause(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("realtime:manage")),
) -> dict:
    try:
        result = realtime_simulator.pause()
        write_operation_log(db, "realtime_pause", "structured_streaming", "暂停实时模拟", current, request.client.host)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resume")
def resume(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("realtime:manage")),
) -> dict:
    try:
        result = realtime_simulator.resume()
        write_operation_log(db, "realtime_resume", "structured_streaming", "继续实时模拟", current, request.client.host)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/stop")
def stop(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("realtime:manage")),
) -> dict:
    result = realtime_simulator.stop()
    write_operation_log(db, "realtime_stop", "structured_streaming", "停止实时模拟", current, request.client.host)
    return result


@router.post("/reset")
def reset(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("realtime:manage")),
) -> dict:
    result = realtime_simulator.reset()
    write_operation_log(db, "realtime_reset", "structured_streaming", "重置实时模拟环境", current, request.client.host)
    return result

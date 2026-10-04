from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import PredictionResult, PredictionTask, Station, User, Warning
from backend.app.services.analysis import latest_analysis
from backend.app.services.predictions import latest_model_comparison


router = APIRouter(prefix="/dashboard", tags=["数据看板"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions("dashboard:view")),
) -> dict:
    try:
        task, analysis = latest_analysis()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    warnings = db.scalars(select(Warning).where(Warning.status == "active")).all()
    warning_map = {item.station_code: item for item in warnings}
    stations = db.scalars(select(Station).order_by(Station.code)).all()
    flow_map = {item["station_id"]: item["passenger_flow"] for item in analysis["station_latest"]}

    latest_prediction_task = db.scalar(
        select(PredictionTask).where(PredictionTask.status == "completed").order_by(PredictionTask.completed_at.desc())
    )
    predicted_30 = 0.0
    prediction_curve = []
    prediction_task_id = None
    if latest_prediction_task:
        prediction_task_id = latest_prediction_task.id
        predicted_30 = db.scalar(
            select(func.sum(PredictionResult.predicted_value)).where(
                PredictionResult.task_id == latest_prediction_task.id,
                PredictionResult.horizon_minutes == 30,
            )
        ) or 0.0
        from backend.app.services.predictions import prediction_task_result
        prediction_curve = prediction_task_result(latest_prediction_task).get("curve", [])
    station_map = []
    for station in stations:
        warning = warning_map.get(station.code)
        current_flow = float(flow_map.get(station.code, 0))
        station_map.append({
            "station_id": station.code, "station_name": station.name, "region": station.region_id,
            "longitude": station.longitude, "latitude": station.latitude, "capacity": station.capacity,
            "current_flow": current_flow, "load_rate": warning.load_rate if warning else current_flow / station.capacity,
            "warning_level": warning.level if warning else "normal",
            "predicted_30": warning.predicted_flow if warning else None,
        })
    return {
        "analysis_task_id": task.id,
        "prediction_task_id": prediction_task_id,
        "summary": {
            **analysis["summary"],
            "hot_station_count": len(analysis["stations_top10"]),
            "warning_count": len(warnings),
            "predicted_30_minutes": round(float(predicted_30), 2),
        },
        "hourly": analysis["hourly"],
        "transport_types": analysis["transport_types"],
        "stations_top10": analysis["stations_top10"],
        "routes_top10": analysis["routes_top10"],
        "regions": analysis["regions"],
        "od_top10": analysis["od_top10"],
        "station_map": station_map,
        "warnings": [
            {"id": item.id, "station_id": item.station_code, "level": item.level, "message": item.message,
             "load_rate": item.load_rate, "created_at": item.created_at.isoformat()}
            for item in warnings[:10]
        ],
        "prediction_curve": prediction_curve[-96:],
        "model_comparison": latest_model_comparison(),
        "notice": "当前系统使用内置模拟城市交通数据集进行功能验证。",
    }


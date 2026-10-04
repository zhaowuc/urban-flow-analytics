from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from backend.app.database.session import SessionLocal
from backend.app.models.entities import (
    DecisionRecord, PredictionResult, PredictionTask, Station, SystemSetting, Warning,
)


def _thresholds(db) -> tuple[float, float, float]:
    values = {item.key: float(item.value) for item in db.scalars(select(SystemSetting).where(SystemSetting.key.like("warning.%"))).all()}
    return values.get("warning.yellow", 0.6), values.get("warning.orange", 0.8), values.get("warning.red", 1.0)


def _level(load_rate: float, yellow: float, orange: float, red: float) -> str:
    if load_rate > red:
        return "red"
    if load_rate >= orange:
        return "orange"
    if load_rate >= yellow:
        return "yellow"
    return "normal"


def _suggestion(level: str, station: Station, load_rate: float) -> tuple[str, str, str]:
    variants = int(station.code[1:]) % 3
    if level == "red":
        suggestions = ["立即执行临时限流并加开区间车", "启动站外分流并增加接驳车辆", "加密班次并实施分方向客流管控"]
        category = "应急管控"
    elif level == "orange":
        suggestions = ["增加车辆并缩短高峰发车间隔", "加密班次并增派站内引导人员", "提前调配备用运力并设置分流通道"]
        category = "运力调整"
    else:
        suggestions = ["加强客流监测并预置备用车辆", "增加现场引导并滚动评估负载", "通知相邻站点做好客流分担准备"]
        category = "风险准备"
    rationale = f"{station.name}预测负载率为 {load_rate * 100:.1f}%，达到{level}预警规则。"
    return category, suggestions[variants], rationale


def generate_warnings(task_id: int | None = None) -> dict:
    with SessionLocal() as db:
        if task_id is None:
            task = db.scalar(
                select(PredictionTask)
                .where(PredictionTask.status == "completed", PredictionTask.model_type.in_(["gbt", "random_forest", "arima"]))
                .order_by(PredictionTask.completed_at.desc())
            )
        else:
            task = db.get(PredictionTask, task_id)
        if task is None or task.status != "completed":
            raise ValueError("尚无可用于预警的已完成预测任务")
        predictions = db.scalars(
            select(PredictionResult).where(PredictionResult.task_id == task.id, PredictionResult.horizon_minutes == 30)
        ).all()
        if not predictions:
            raise ValueError("预测任务没有 30 分钟预测结果")
        stations = {item.code: item for item in db.scalars(select(Station)).all()}
        yellow, orange, red = _thresholds(db)
        now = datetime.now()
        for old in db.scalars(select(Warning).where(Warning.status == "active", Warning.source == "prediction")).all():
            old.status = "resolved"
            old.resolved_at = now

        grouped: dict[str, dict[str, float]] = {}
        for prediction in predictions:
            if not prediction.station_code:
                continue
            values = grouped.setdefault(prediction.station_code, {"predicted": 0.0, "actual": 0.0})
            values["predicted"] += float(prediction.predicted_value)
            values["actual"] += float(prediction.actual_value or 0)
        created = []
        for station_code, values in grouped.items():
            station = stations.get(station_code)
            if station is None:
                continue
            load_rate = values["predicted"] / float(station.capacity)
            level = _level(load_rate, yellow, orange, red)
            if level == "normal":
                continue
            warning = Warning(
                station_code=station.code,
                region=station.region_id,
                current_flow=values["actual"],
                predicted_flow=values["predicted"],
                capacity=float(station.capacity),
                load_rate=load_rate,
                level=level,
                source="prediction",
                status="active",
                message=f"{station.name}未来30分钟负载率预计达到 {load_rate * 100:.1f}%",
            )
            db.add(warning)
            db.flush()
            category, suggestion, rationale = _suggestion(level, station, load_rate)
            db.add(DecisionRecord(
                warning_id=warning.id, category=category, suggestion=suggestion,
                rationale=rationale, status="proposed",
            ))
            created.append(warning)
        db.commit()
        counts = {"yellow": 0, "orange": 0, "red": 0}
        for item in created:
            counts[item.level] += 1
        return {"prediction_task_id": task.id, "created_count": len(created), "level_counts": counts}

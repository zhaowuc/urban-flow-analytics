from __future__ import annotations

import json

from sqlalchemy import inspect, select, text

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.database.session import Base, SessionLocal, engine
from backend.app.models.entities import Region, Role, Route, Station, SystemSetting, User


ALL_PERMISSIONS = [
    "dashboard:view", "statistics:view", "prediction:view", "data:manage",
    "analysis:run", "realtime:manage", "prediction:manage", "warnings:view",
    "users:manage", "logs:view", "settings:manage", "report:view",
]

ANALYST_PERMISSIONS = [
    "dashboard:view", "statistics:view", "prediction:view", "data:manage",
    "analysis:run", "realtime:manage", "prediction:manage", "warnings:view",
    "logs:view", "report:view",
]

VIEWER_PERMISSIONS = ["dashboard:view", "statistics:view", "prediction:view", "warnings:view", "report:view"]


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    warning_columns = {item["name"] for item in inspect(engine).get_columns("warnings")}
    if "source" not in warning_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE warnings ADD COLUMN source VARCHAR(32) DEFAULT 'prediction'"))
    with SessionLocal() as db:
        roles = {
            "admin": ("管理员", ALL_PERMISSIONS),
            "analyst": ("分析人员", ANALYST_PERMISSIONS),
            "viewer": ("普通用户", VIEWER_PERMISSIONS),
        }
        role_models: dict[str, Role] = {}
        for code, (name, permissions) in roles.items():
            role = db.scalar(select(Role).where(Role.code == code))
            if role is None:
                role = Role(code=code, name=name, permissions=json.dumps(permissions, ensure_ascii=False))
                db.add(role)
            else:
                role.permissions = json.dumps(permissions, ensure_ascii=False)
            role_models[code] = role
        db.flush()

        accounts = {
            "admin": ("系统管理员", "admin123", "admin"),
            "analyst": ("客流分析员", "analyst123", "analyst"),
            "viewer": ("演示访客", "viewer123", "viewer"),
        }
        for username, (display_name, password, role_code) in accounts.items():
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    roles=[role_models[role_code]],
                )
                db.add(user)

        catalog_path = settings.app_home / "config" / "demo_city_catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for item in catalog["regions"]:
            region = db.scalar(select(Region).where(Region.code == item["region_id"]))
            if region is None:
                db.add(Region(
                    code=item["region_id"],
                    name=item["region_name"],
                    center_longitude=item["center"][0],
                    center_latitude=item["center"][1],
                ))
        db.flush()
        for item in catalog["stations"]:
            station = db.scalar(select(Station).where(Station.code == item["station_id"]))
            if station is None:
                db.add(Station(
                    code=item["station_id"],
                    name=item["station_name"],
                    region_id=item["region_id"],
                    longitude=item["longitude"],
                    latitude=item["latitude"],
                    capacity=item["capacity"],
                    station_type=item["station_type"],
                    status=item["status"],
                ))
            else:
                station.name = item["station_name"]
                station.region_id = item["region_id"]
                station.longitude = item["longitude"]
                station.latitude = item["latitude"]
                station.capacity = item["capacity"]
                station.station_type = item["station_type"]
                station.status = item["status"]
        db.flush()
        for item in catalog["routes"]:
            route = db.scalar(select(Route).where(Route.code == item["route_id"]))
            if route is None:
                db.add(Route(
                    code=item["route_id"],
                    name=item["route_name"],
                    transport_type=item["transport_type"],
                    station_sequence=json.dumps(item["station_sequence"], ensure_ascii=False),
                    origin_station=item["origin_station"],
                    destination_station=item["destination_station"],
                ))

        defaults = {
            "warning.yellow": ("0.6", "黄色预警阈值"),
            "warning.orange": ("0.8", "橙色预警阈值"),
            "warning.red": ("1.0", "红色预警阈值"),
            "deployment.mode": ("Spark Local 离线部署模式", "当前部署模式"),
            "demo.speed": ("60", "演示时间加速倍数"),
        }
        for key, (value, description) in defaults.items():
            if db.scalar(select(SystemSetting).where(SystemSetting.key == key)) is None:
                db.add(SystemSetting(key=key, value=value, description=description))
        db.commit()

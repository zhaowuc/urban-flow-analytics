from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models.entities import Region, Route, Station, User


router = APIRouter(prefix="/catalog", tags=["统一城市目录"])


@router.get("/city")
def city_catalog(_user: User = Depends(get_current_user)) -> dict:
    return json.loads((settings.app_home / "config" / "demo_city_catalog.json").read_text(encoding="utf-8"))


@router.get("/geojson")
def city_geojson(_user: User = Depends(get_current_user)) -> dict:
    return json.loads((settings.app_home / "assets" / "maps" / "demo_city.json").read_text(encoding="utf-8"))


@router.get("/regions")
def regions(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    return [
        {"region_id": item.code, "region_name": item.name, "center": [item.center_longitude, item.center_latitude]}
        for item in db.scalars(select(Region).order_by(Region.code)).all()
    ]


@router.get("/stations")
def stations(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "station_id": item.code, "station_name": item.name, "region_id": item.region_id,
            "longitude": item.longitude, "latitude": item.latitude, "capacity": item.capacity,
            "station_type": item.station_type, "status": item.status,
        }
        for item in db.scalars(select(Station).order_by(Station.code)).all()
    ]


@router.get("/routes")
def routes(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "route_id": item.code, "route_name": item.name, "transport_type": item.transport_type,
            "station_sequence": json.loads(item.station_sequence), "origin_station": item.origin_station,
            "destination_station": item.destination_station,
        }
        for item in db.scalars(select(Route).order_by(Route.code)).all()
    ]


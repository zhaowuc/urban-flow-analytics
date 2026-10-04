from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from backend.app.core.config import settings


TRANSPORT_WEIGHTS = {
    "metro": 0.34,
    "bus": 0.31,
    "ride_hailing": 0.15,
    "taxi": 0.11,
    "bike": 0.09,
}

TRANSPORT_BASE_FLOW = {"metro": 24, "bus": 16, "ride_hailing": 3, "taxi": 2, "bike": 2}
POPULAR_STATIONS = {"S001": 1.55, "S002": 1.75, "S003": 1.42, "S005": 1.38, "S023": 1.28, "S026": 1.35, "S032": 1.32, "S040": 1.7}


def load_catalog() -> dict:
    return json.loads((settings.app_home / "config" / "demo_city_catalog.json").read_text(encoding="utf-8"))


def validate_catalog(catalog: dict) -> None:
    regions = {item["region_id"] for item in catalog["regions"]}
    stations = {item["station_id"] for item in catalog["stations"]}
    if len(regions) != 8 or len(stations) != 40 or len(catalog["routes"]) != 12:
        raise ValueError("统一虚拟城市目录必须固定为 8 区域、40 站点、12 线路")
    for station in catalog["stations"]:
        if station["region_id"] not in regions:
            raise ValueError(f"站点 {station['station_id']} 引用了不存在的区域")
    for route in catalog["routes"]:
        sequence = route["station_sequence"]
        if len(sequence) < 2 or any(item not in stations for item in sequence):
            raise ValueError(f"线路 {route['route_id']} 存在无效站点")
        if route["origin_station"] != sequence[0] or route["destination_station"] != sequence[-1]:
            raise ValueError(f"线路 {route['route_id']} 起终点与站点序列不一致")


def _weighted_choice(rng: random.Random, values: list[str], weights: list[float]) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def generate_records(row_count: int, seed: int | None = None) -> pd.DataFrame:
    if row_count <= 0:
        raise ValueError("生成条数必须大于 0")
    catalog = load_catalog()
    validate_catalog(catalog)
    rng = random.Random(settings.demo_seed if seed is None else seed)
    station_map = {item["station_id"]: item for item in catalog["stations"]}
    routes_by_type: dict[str, list[dict]] = {}
    for route in catalog["routes"]:
        routes_by_type.setdefault(route["transport_type"], []).append(route)

    end_date = datetime(2026, 8, 26, 23, 59, 0)
    start_date = end_date - timedelta(days=34)
    dates = [(start_date + timedelta(days=index)).date() for index in range(35)]
    weather_by_date: dict = {}
    for date_value in dates:
        weather = rng.choices(["sunny", "cloudy", "rain", "heavy_rain"], [0.49, 0.29, 0.18, 0.04], k=1)[0]
        weather_by_date[date_value] = (weather, round(20 + rng.random() * 13, 1))

    hour_weights_weekday = [0.25,0.18,0.15,0.14,0.16,0.3,0.75,2.8,3.4,2.4,1.35,1.25,1.4,1.35,1.3,1.45,1.9,3.0,3.5,2.6,1.55,1.0,0.65,0.4]
    hour_weights_weekend = [0.25,0.18,0.15,0.14,0.16,0.25,0.45,0.7,1.0,1.25,1.55,1.8,2.0,2.1,2.15,2.2,2.25,2.3,2.15,1.9,1.55,1.1,0.7,0.4]
    transport_types = list(TRANSPORT_WEIGHTS)
    records: list[dict] = []
    for index in range(row_count):
        event_date = rng.choice(dates)
        is_weekend = event_date.weekday() >= 5
        hour = rng.choices(range(24), weights=hour_weights_weekend if is_weekend else hour_weights_weekday, k=1)[0]
        minute = rng.randrange(60)
        second = rng.randrange(60)
        event_time = datetime.combine(event_date, datetime.min.time()).replace(hour=hour, minute=minute, second=second)
        transport_type = _weighted_choice(rng, transport_types, [TRANSPORT_WEIGHTS[item] for item in transport_types])
        route = rng.choice(routes_by_type[transport_type])
        sequence = route["station_sequence"]
        origin_index = rng.randrange(len(sequence))
        destination_index = rng.randrange(len(sequence) - 1)
        if destination_index >= origin_index:
            destination_index += 1
        origin_station = sequence[origin_index]
        destination_station = sequence[destination_index]
        station_id = destination_station
        station = station_map[station_id]
        weather, temperature = weather_by_date[event_date]

        peak_factor = 1.0
        if not is_weekend and 7 <= hour < 9:
            peak_factor = 1.75
        elif not is_weekend and 17 <= hour < 19:
            peak_factor = 1.95
        elif is_weekend and 11 <= hour < 19:
            peak_factor = 1.25
        weather_factor = 1.0
        if weather in {"rain", "heavy_rain"}:
            weather_factor = 0.55 if transport_type == "bike" else (1.22 if transport_type in {"taxi", "ride_hailing"} else 1.08)
        popularity = POPULAR_STATIONS.get(station_id, 0.88 + (int(station_id[1:]) % 7) * 0.035)
        periodic = 1.0 + 0.08 * math.sin((event_date.toordinal() % 7) / 7 * 2 * math.pi)
        expected = TRANSPORT_BASE_FLOW[transport_type] * peak_factor * weather_factor * popularity * periodic
        passenger_count = max(1, int(rng.gauss(expected, max(1.0, expected * 0.16))))
        records.append({
            "trip_id": f"TRIP-{event_date:%Y%m%d}-{index + 1:07d}",
            "transport_type": transport_type,
            "route_id": route["route_id"],
            "station_id": station_id,
            "origin_station": origin_station,
            "destination_station": destination_station,
            "region": station["region_id"],
            "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            "longitude": station["longitude"],
            "latitude": station["latitude"],
            "weather": weather,
            "temperature": temperature,
            "is_holiday": bool(is_weekend),
            "passenger_count": passenger_count,
        })
    return pd.DataFrame.from_records(records).sort_values("event_time").reset_index(drop=True)


def validate_records(frame: pd.DataFrame, catalog: dict | None = None) -> None:
    catalog = catalog or load_catalog()
    station_ids = {item["station_id"] for item in catalog["stations"]}
    route_map = {item["route_id"]: set(item["station_sequence"]) for item in catalog["routes"]}
    region_ids = {item["region_id"] for item in catalog["regions"]}
    if not set(frame["station_id"]).issubset(station_ids):
        raise ValueError("模拟数据包含目录外站点")
    if not set(frame["origin_station"]).issubset(station_ids) or not set(frame["destination_station"]).issubset(station_ids):
        raise ValueError("模拟数据包含目录外 OD 站点")
    if not set(frame["region"]).issubset(region_ids):
        raise ValueError("模拟数据包含目录外区域")
    if (frame["origin_station"] == frame["destination_station"]).any():
        raise ValueError("模拟数据存在相同的起点与终点")
    for row in frame[["route_id", "station_id", "origin_station", "destination_station"]].itertuples(index=False):
        valid = route_map.get(row.route_id, set())
        if row.station_id not in valid or row.origin_station not in valid or row.destination_station not in valid:
            raise ValueError(f"记录线路与站点关系不一致：{row.route_id}")


def write_demo_files(row_count: int | None = None, force: bool = False) -> dict[str, Path]:
    target_dir = settings.app_home / "data" / "demo"
    target_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "csv": target_dir / "passenger_flow_demo.csv",
        "json": target_dir / "passenger_flow_demo.json",
        "xlsx": target_dir / "passenger_flow_demo.xlsx",
    }
    if not force and all(path.exists() and path.stat().st_size > 0 for path in targets.values()):
        return targets
    frame = generate_records(row_count or settings.demo_rows)
    validate_records(frame)
    frame.to_csv(targets["csv"], index=False, encoding="utf-8-sig")
    frame.to_json(targets["json"], orient="records", lines=True, force_ascii=False, date_format="iso")
    frame.to_excel(targets["xlsx"], index=False, engine="openpyxl")
    return targets


from __future__ import annotations

import json
import math
import random
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.session import SessionLocal
from backend.app.models.entities import DecisionRecord, Station, SystemSetting, Warning
from backend.app.services.demo_data import TRANSPORT_BASE_FLOW, TRANSPORT_WEIGHTS, load_catalog, validate_catalog
from backend.app.services.warnings import _level, _suggestion
from backend.app.spark.session import get_spark


class RealtimeSimulator:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = "stopped"
        self._speed = 60
        self._simulated_time = datetime(2026, 8, 27, 6, 45, 0)
        self._session_id: str | None = None
        self._inbox: Path | None = None
        self._checkpoint: Path | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._queries: list[Any] = []
        self._query_names: dict[str, str] = {}
        self._sequence = 0
        self._error: str | None = None
        self._rng = random.Random(settings.demo_seed + 41)

    def _schema(self):
        from pyspark.sql.types import BooleanType, DoubleType, LongType, StringType, StructField, StructType, TimestampType
        return StructType([
            StructField("trip_id", StringType(), False),
            StructField("transport_type", StringType(), False),
            StructField("route_id", StringType(), False),
            StructField("station_id", StringType(), False),
            StructField("origin_station", StringType(), False),
            StructField("destination_station", StringType(), False),
            StructField("region", StringType(), False),
            StructField("event_time", TimestampType(), False),
            StructField("longitude", DoubleType(), False),
            StructField("latitude", DoubleType(), False),
            StructField("weather", StringType(), False),
            StructField("temperature", DoubleType(), False),
            StructField("is_holiday", BooleanType(), False),
            StructField("passenger_count", LongType(), False),
        ])

    def _start_queries(self) -> None:
        from pyspark.sql import functions as F
        spark = get_spark()
        stream = (
            spark.readStream.schema(self._schema()).option("maxFilesPerTrigger", 2)
            .json(str(self._inbox)).withWatermark("event_time", "2 minutes")
        )
        suffix = self._session_id
        self._query_names = {
            "raw": f"realtime_raw_{suffix}", "flow5": f"realtime_flow5_{suffix}",
            "flow10": f"realtime_flow10_{suffix}", "flow15": f"realtime_flow15_{suffix}",
            "stations": f"realtime_stations_{suffix}", "routes": f"realtime_routes_{suffix}",
            "regions": f"realtime_regions_{suffix}",
        }

        def memory_query(dataframe, key: str, mode: str = "complete"):
            query = (
                dataframe.writeStream.format("memory").queryName(self._query_names[key])
                .outputMode(mode).option("checkpointLocation", str(self._checkpoint / key))
                .trigger(processingTime="1 second").start()
            )
            self._queries.append(query)

        memory_query(stream, "raw", "append")
        for minutes, key in ((5, "flow5"), (10, "flow10"), (15, "flow15")):
            memory_query(
                stream.groupBy(F.window("event_time", f"{minutes} minutes")).agg(
                    F.sum("passenger_count").cast("long").alias("passenger_flow")
                ), key,
            )
        window15 = F.window("event_time", "15 minutes")
        memory_query(stream.groupBy(window15, "station_id").agg(F.sum("passenger_count").cast("long").alias("passenger_flow")), "stations")
        memory_query(stream.groupBy(window15, "route_id").agg(F.sum("passenger_count").cast("long").alias("passenger_flow")), "routes")
        memory_query(stream.groupBy(window15, "region").agg(F.sum("passenger_count").cast("long").alias("passenger_flow")), "regions")

    def _generate_batch(self) -> list[dict]:
        catalog = load_catalog()
        validate_catalog(catalog)
        station_map = {item["station_id"]: item for item in catalog["stations"]}
        transport_types = list(TRANSPORT_WEIGHTS)
        routes_by_type: dict[str, list[dict]] = {}
        for route in catalog["routes"]:
            routes_by_type.setdefault(route["transport_type"], []).append(route)
        hour = self._simulated_time.hour
        peak = 1.75 if 7 <= hour < 9 else (1.95 if 17 <= hour < 19 else 1.0)
        batch_size = 22 + (10 if peak > 1 else 0)
        records = []
        for _ in range(batch_size):
            self._sequence += 1
            transport_type = self._rng.choices(transport_types, [TRANSPORT_WEIGHTS[item] for item in transport_types], k=1)[0]
            route = self._rng.choice(routes_by_type[transport_type])
            sequence = route["station_sequence"]
            origin_index = self._rng.randrange(len(sequence))
            destination_index = self._rng.randrange(len(sequence) - 1)
            if destination_index >= origin_index:
                destination_index += 1
            origin = sequence[origin_index]
            destination = sequence[destination_index]
            station = station_map[destination]
            weather = self._rng.choices(["sunny", "cloudy", "rain"], [0.58, 0.28, 0.14], k=1)[0]
            weather_factor = 0.58 if transport_type == "bike" and weather == "rain" else (1.18 if transport_type in {"taxi", "ride_hailing"} and weather == "rain" else 1.0)
            popularity = 1.4 if destination in {"S001", "S002", "S003", "S005", "S013", "S040"} else 0.95
            expected = TRANSPORT_BASE_FLOW[transport_type] * peak * weather_factor * popularity
            passenger_count = max(1, int(self._rng.gauss(expected, max(1.0, expected * 0.15))))
            event_time = self._simulated_time + timedelta(seconds=self._rng.randrange(60))
            records.append({
                "trip_id": f"STREAM-{self._session_id}-{self._sequence:08d}",
                "transport_type": transport_type, "route_id": route["route_id"],
                "station_id": destination, "origin_station": origin, "destination_station": destination,
                "region": station["region_id"], "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                "longitude": station["longitude"], "latitude": station["latitude"],
                "weather": weather, "temperature": round(24 + 4 * math.sin(hour / 24 * 2 * math.pi), 1),
                "is_holiday": False, "passenger_count": passenger_count,
            })
        return records

    def _generator_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.2)
                continue
            try:
                records = self._generate_batch()
                hidden = self._inbox / f".batch-{self._sequence:08d}.tmp"
                visible = self._inbox / f"batch-{self._sequence:08d}.json"
                hidden.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records), encoding="utf-8")
                hidden.replace(visible)
                with self._lock:
                    self._simulated_time += timedelta(minutes=max(1, self._speed // 60))
                time.sleep(1)
            except Exception as exc:
                with self._lock:
                    self._error = str(exc)
                    self._state = "failed"
                self._stop_event.set()

    def start(self, speed: int = 60) -> dict:
        with self._lock:
            if self._state == "running":
                return self.snapshot()
            if self._state == "paused":
                self._pause_event.clear()
                self._state = "running"
                return self.snapshot()
            self._speed = speed
            self._session_id = uuid.uuid4().hex[:10]
            self._inbox = settings.app_home / "data" / "stream" / "inbox" / self._session_id
            self._checkpoint = settings.app_home / "work" / "stream-checkpoint" / self._session_id
            self._inbox.mkdir(parents=True, exist_ok=True)
            self._checkpoint.mkdir(parents=True, exist_ok=True)
            self._queries = []
            self._stop_event.clear()
            self._pause_event.clear()
            self._error = None
            try:
                self._start_queries()
            except Exception as exc:
                self._state = "failed"
                self._error = str(exc)
                raise RuntimeError(f"实时流启动失败：{exc}") from exc
            self._state = "running"
            self._thread = threading.Thread(target=self._generator_loop, name="stream-data-generator", daemon=True)
            self._thread.start()
        return self.snapshot()

    def pause(self) -> dict:
        with self._lock:
            if self._state != "running":
                raise ValueError("实时模拟当前未运行")
            self._pause_event.set()
            self._state = "paused"
        # Let every query consume files that were already atomically published so
        # the paused snapshot remains stable instead of changing a few seconds later.
        time.sleep(0.25)
        for query in self._queries:
            try:
                if query.isActive:
                    query.processAllAvailable()
            except Exception:
                self._refresh_query_health()
        return self.snapshot()

    def resume(self) -> dict:
        with self._lock:
            if self._state != "paused":
                raise ValueError("实时模拟当前未暂停")
            self._pause_event.clear()
            self._state = "running"
        return self.snapshot()

    def stop(self) -> dict:
        with self._lock:
            self._stop_event.set()
            self._pause_event.clear()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3)
        for query in list(self._queries):
            try:
                if query.isActive:
                    query.stop()
            except Exception:
                pass
        with self._lock:
            if self._state != "failed":
                self._state = "stopped"
        return self.snapshot(include_tables=False)

    def reset(self) -> dict:
        inbox = self._inbox
        checkpoint = self._checkpoint
        self.stop()
        project_root = settings.app_home.resolve()
        for target in (inbox, checkpoint):
            if target and target.exists() and project_root in target.resolve().parents:
                shutil.rmtree(target)
        with self._lock:
            self._simulated_time = datetime(2026, 8, 27, 6, 45, 0)
            self._sequence = 0
            self._session_id = None
            self._inbox = None
            self._checkpoint = None
            self._query_names = {}
            self._error = None
            self._state = "stopped"
        self._sync_realtime_warnings([])
        return self.snapshot(include_tables=False)

    def _table_rows(self, sql: str) -> list[dict]:
        try:
            return [row.asDict(recursive=True) for row in get_spark().sql(sql).collect()]
        except Exception:
            return []

    def _refresh_query_health(self) -> None:
        """Reflect Spark query failures in the public simulator state."""
        if self._state not in {"running", "paused"}:
            return
        failures: list[str] = []
        for query in self._queries:
            try:
                exception = query.exception()
                if exception is not None:
                    failures.append(str(exception).splitlines()[0])
                elif not query.isActive:
                    failures.append(f"查询 {query.name} 已停止")
            except Exception as exc:
                failures.append(str(exc).splitlines()[0])
        if failures:
            with self._lock:
                self._state = "failed"
                self._error = "；".join(failures[:2])
                self._stop_event.set()

    def _latest_window_total(self, key: str) -> int:
        name = self._query_names.get(key)
        if not name:
            return 0
        rows = self._table_rows(f"SELECT passenger_flow FROM {name} ORDER BY window.end DESC LIMIT 1")
        return int(rows[0]["passenger_flow"]) if rows else 0

    def _latest_rank(self, key: str, field: str, limit: int = 10) -> list[dict]:
        name = self._query_names.get(key)
        if not name:
            return []
        return self._table_rows(
            f"WITH latest AS (SELECT max(window.end) end_time FROM {name}) "
            f"SELECT {field}, passenger_flow FROM {name}, latest "
            f"WHERE window.end=latest.end_time ORDER BY passenger_flow DESC LIMIT {limit}"
        )

    def _sync_realtime_warnings(self, station_rows: list[dict]) -> list[dict]:
        with SessionLocal() as db:
            stations = {item.code: item for item in db.scalars(select(Station)).all()}
            settings_values = {item.key: float(item.value) for item in db.scalars(select(SystemSetting).where(SystemSetting.key.like("warning.%"))).all()}
            thresholds = (settings_values.get("warning.yellow", 0.6), settings_values.get("warning.orange", 0.8), settings_values.get("warning.red", 1.0))
            existing = {item.station_code: item for item in db.scalars(select(Warning).where(Warning.status == "active", Warning.source == "realtime")).all()}
            active_codes: set[str] = set()
            response = []
            for row in station_rows:
                station = stations.get(row["station_id"])
                if not station:
                    continue
                load_rate = float(row["passenger_flow"]) / station.capacity
                level = _level(load_rate, *thresholds)
                row["capacity"] = station.capacity
                row["load_rate"] = load_rate
                row["warning_level"] = level
                if level == "normal":
                    continue
                active_codes.add(station.code)
                warning = existing.get(station.code)
                is_new = warning is None
                previous_level = warning.level if warning else None
                if warning is None:
                    warning = Warning(station_code=station.code, region=station.region_id, current_flow=0, predicted_flow=0, capacity=station.capacity, load_rate=0, level=level, source="realtime", status="active", message="")
                    db.add(warning)
                    db.flush()
                warning.current_flow = float(row["passenger_flow"])
                warning.predicted_flow = float(row["passenger_flow"])
                warning.capacity = station.capacity
                warning.load_rate = load_rate
                warning.level = level
                warning.message = f"{station.name}实时15分钟窗口负载率达到 {load_rate * 100:.1f}%"
                if is_new or previous_level != level:
                    category, suggestion, rationale = _suggestion(level, station, load_rate)
                    db.add(DecisionRecord(warning_id=warning.id, category=category, suggestion=suggestion, rationale=rationale, status="proposed"))
                response.append({"station_id": station.code, "level": level, "load_rate": load_rate, "message": warning.message})
            for code, warning in existing.items():
                if code not in active_codes:
                    warning.status = "resolved"
                    warning.resolved_at = datetime.now()
            db.commit()
            return response

    def snapshot(self, include_tables: bool = True) -> dict:
        self._refresh_query_health()
        with self._lock:
            state = self._state
            simulated_time = self._simulated_time
            speed = self._speed
            error = self._error
            session_id = self._session_id
        base = {
            "state": state, "session_id": session_id, "speed": speed,
            "speed_label": f"演示时间加速 ×{speed}",
            "simulated_time": simulated_time.isoformat(), "error": error,
            "engine": "Spark Structured Streaming",
        }
        if not include_tables or not self._query_names:
            return {**base, "current_total": 0, "window_5": 0, "window_10": 0, "window_15": 0, "hot_stations": [], "hot_routes": [], "regions": [], "warnings": [], "processing_rate": 0.0}
        hot_stations = self._latest_rank("stations", "station_id", 40)
        hot_routes = self._latest_rank("routes", "route_id", 10)
        regions = self._latest_rank("regions", "region", 8)
        warnings = self._sync_realtime_warnings(hot_stations)
        processing_rate = 0.0
        for query in self._queries:
            try:
                progress = query.lastProgress
                if progress:
                    processing_rate += float(progress.get("processedRowsPerSecond", 0.0))
            except Exception:
                continue
        raw_name = self._query_names.get("raw")
        current_rows = self._table_rows(
            f"WITH latest AS (SELECT max(event_time) latest_time FROM {raw_name}) "
            f"SELECT cast(coalesce(sum(passenger_count),0) as long) current_total "
            f"FROM {raw_name}, latest WHERE event_time >= latest.latest_time - INTERVAL 1 MINUTE"
        ) if raw_name else []
        return {
            **base,
            "current_total": int(current_rows[0]["current_total"]) if current_rows else 0,
            "window_5": self._latest_window_total("flow5"),
            "window_10": self._latest_window_total("flow10"),
            "window_15": self._latest_window_total("flow15"),
            "hot_stations": hot_stations,
            "hot_routes": hot_routes,
            "regions": regions,
            "warnings": warnings,
            "processing_rate": round(processing_rate, 2),
        }


realtime_simulator = RealtimeSimulator()

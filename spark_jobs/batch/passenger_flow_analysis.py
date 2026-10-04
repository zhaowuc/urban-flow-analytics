from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession


def _rows(frame, keys: tuple[str, ...]) -> list[dict]:
    result: list[dict] = []
    for row in frame.collect():
        item = {}
        for key in keys:
            value = row[key]
            if isinstance(value, datetime):
                value = value.isoformat()
            item[key] = value
        result.append(item)
    return result


def run_full_analysis(spark: SparkSession, parquet_path: Path) -> dict:
    if not parquet_path.exists():
        raise ValueError("尚无清洗后的 Parquet 数据，请先执行数据预处理")
    frame = spark.read.parquet(str(parquet_path))
    input_count = frame.count()
    if input_count == 0:
        raise ValueError("Parquet 数据为空")
    frame.createOrReplaceTempView("passenger_flow")

    bounds = spark.sql(
        "SELECT date_format(max(event_time), 'yyyy-MM-dd') latest_date, "
        "date_format(date_sub(to_date(max(event_time)), 1), 'yyyy-MM-dd') previous_date FROM passenger_flow"
    ).first()
    latest_date = bounds["latest_date"]
    previous_date = bounds["previous_date"]

    day_totals = _rows(spark.sql(
        "SELECT date_format(to_date(event_time), 'yyyy-MM-dd') period, "
        "cast(sum(passenger_count) as long) passenger_flow FROM passenger_flow "
        "GROUP BY to_date(event_time) ORDER BY period"
    ), ("period", "passenger_flow"))
    week_totals = _rows(spark.sql(
        "SELECT date_format(date_trunc('week', event_time), 'yyyy-MM-dd') period, "
        "cast(sum(passenger_count) as long) passenger_flow FROM passenger_flow "
        "GROUP BY date_trunc('week', event_time) ORDER BY period"
    ), ("period", "passenger_flow"))
    month_totals = _rows(spark.sql(
        "SELECT date_format(event_time, 'yyyy-MM') period, cast(sum(passenger_count) as long) passenger_flow "
        "FROM passenger_flow GROUP BY date_format(event_time, 'yyyy-MM') ORDER BY period"
    ), ("period", "passenger_flow"))

    hourly = _rows(spark.sql(f"""
        SELECT hour(event_time) hour, cast(sum(passenger_count) as long) passenger_flow
        FROM passenger_flow WHERE to_date(event_time) = date('{latest_date}')
        GROUP BY hour(event_time) ORDER BY hour
    """), ("hour", "passenger_flow"))
    peak_analysis = _rows(spark.sql(
        "SELECT CASE WHEN hour(event_time) >= 7 AND hour(event_time) < 9 THEN '早高峰' "
        "WHEN hour(event_time) >= 17 AND hour(event_time) < 19 THEN '晚高峰' "
        "WHEN dayofweek(event_time) IN (1,7) THEN '周末' "
        "WHEN is_holiday THEN '节假日' ELSE '平峰' END period_type, "
        "cast(sum(passenger_count) as long) passenger_flow FROM passenger_flow GROUP BY period_type "
        "ORDER BY passenger_flow DESC"
    ), ("period_type", "passenger_flow"))

    regions = _rows(spark.sql(
        "SELECT region as region_id, cast(sum(passenger_count) as long) passenger_flow, "
        "cast(avg(passenger_count) as double) average_flow FROM passenger_flow "
        "GROUP BY region ORDER BY passenger_flow DESC"
    ), ("region_id", "passenger_flow", "average_flow"))
    stations = _rows(spark.sql(
        "SELECT station_id, cast(sum(passenger_count) as long) passenger_flow, "
        "cast(avg(passenger_count) as double) average_flow FROM passenger_flow "
        "GROUP BY station_id ORDER BY passenger_flow DESC LIMIT 10"
    ), ("station_id", "passenger_flow", "average_flow"))
    all_station_flow = _rows(spark.sql(f"""
        SELECT station_id, cast(sum(passenger_count) as long) passenger_flow
        FROM passenger_flow WHERE to_date(event_time) = date('{latest_date}')
        GROUP BY station_id ORDER BY station_id
    """), ("station_id", "passenger_flow"))
    routes = _rows(spark.sql(
        "SELECT route_id, transport_type, cast(sum(passenger_count) as long) passenger_flow "
        "FROM passenger_flow GROUP BY route_id, transport_type ORDER BY passenger_flow DESC LIMIT 10"
    ), ("route_id", "transport_type", "passenger_flow"))
    transport = _rows(spark.sql(
        "SELECT transport_type, cast(sum(passenger_count) as long) passenger_flow "
        "FROM passenger_flow GROUP BY transport_type ORDER BY passenger_flow DESC"
    ), ("transport_type", "passenger_flow"))
    od_top = _rows(spark.sql(
        "SELECT origin_station, destination_station, cast(sum(passenger_count) as long) passenger_flow "
        "FROM passenger_flow WHERE origin_station <> destination_station "
        "GROUP BY origin_station, destination_station ORDER BY passenger_flow DESC LIMIT 10"
    ), ("origin_station", "destination_station", "passenger_flow"))
    od_values = _rows(spark.sql(
        "SELECT origin_station, destination_station, cast(sum(passenger_count) as long) passenger_flow "
        "FROM passenger_flow WHERE origin_station <> destination_station "
        "GROUP BY origin_station, destination_station ORDER BY origin_station, destination_station"
    ), ("origin_station", "destination_station", "passenger_flow"))
    station_trend = _rows(spark.sql(
        "WITH top_station AS (SELECT station_id FROM passenger_flow GROUP BY station_id "
        "ORDER BY sum(passenger_count) DESC LIMIT 5) "
        "SELECT p.station_id, date_format(to_date(p.event_time), 'yyyy-MM-dd') period, "
        "cast(sum(p.passenger_count) as long) passenger_flow FROM passenger_flow p "
        "JOIN top_station t ON p.station_id=t.station_id GROUP BY p.station_id, to_date(p.event_time) "
        "ORDER BY period, p.station_id"
    ), ("station_id", "period", "passenger_flow"))

    latest_total = next((int(item["passenger_flow"]) for item in day_totals if item["period"] == latest_date), 0)
    previous_total = next((int(item["passenger_flow"]) for item in day_totals if item["period"] == previous_date), 0)
    current_hour = max((int(item["hour"]) for item in hourly), default=0)
    current_flow = next((int(item["passenger_flow"]) for item in hourly if int(item["hour"]) == current_hour), 0)
    change_rate = ((latest_total - previous_total) / previous_total * 100.0) if previous_total else 0.0
    return {
        "generated_at": datetime.now().isoformat(),
        "engine": "Spark SQL + DataFrame",
        "input_count": input_count,
        "date_range": {"latest": latest_date, "previous": previous_date},
        "summary": {
            "today_total": latest_total,
            "current_flow": current_flow,
            "yesterday_change_percent": round(change_rate, 2),
            "active_station_count": len(all_station_flow),
        },
        "totals": {"day": day_totals, "week": week_totals, "month": month_totals},
        "hourly": hourly,
        "peak_analysis": peak_analysis,
        "regions": regions,
        "stations_top10": stations,
        "station_latest": all_station_flow,
        "station_trend": station_trend,
        "routes_top10": routes,
        "transport_types": transport,
        "od_top10": od_top,
        "od_matrix": {"values": od_values},
    }

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, SparkSession, functions as F


REQUIRED_COLUMNS = [
    "trip_id", "transport_type", "route_id", "station_id", "origin_station",
    "destination_station", "region", "event_time", "longitude", "latitude",
    "weather", "temperature", "is_holiday", "passenger_count",
]
VALID_TRANSPORT_TYPES = ["bus", "metro", "taxi", "ride_hailing", "bike"]


def read_source(spark: SparkSession, source_path: Path, temp_dir: Path) -> DataFrame:
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        return spark.read.option("header", True).option("inferSchema", True).option("encoding", "UTF-8").csv(str(source_path))
    if suffix == ".json":
        return spark.read.option("multiLine", False).json(str(source_path))
    if suffix == ".xlsx":
        temp_dir.mkdir(parents=True, exist_ok=True)
        csv_path = temp_dir / f"{source_path.stem}-xlsx-bridge.csv"
        pd.read_excel(source_path, engine="openpyxl").to_csv(csv_path, index=False, encoding="utf-8")
        return spark.read.option("header", True).option("inferSchema", True).csv(str(csv_path))
    raise ValueError("仅支持 CSV、JSON 和 XLSX 文件")


def clean_dataset(
    spark: SparkSession,
    source_path: Path,
    output_path: Path,
    catalog_path: Path,
    temp_dir: Path,
    missing_strategy: str = "fill",
) -> dict:
    raw = read_source(spark, source_path, temp_dir)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        raise ValueError(f"文件缺少必要字段：{', '.join(missing_columns)}")
    raw = raw.select(*REQUIRED_COLUMNS)
    original_count = raw.count()
    if original_count == 0:
        raise ValueError("文件为空，没有可处理的数据")

    normalized = (
        raw
        .withColumn("trip_id", F.trim(F.col("trip_id").cast("string")))
        .withColumn("transport_type", F.lower(F.trim(F.col("transport_type").cast("string"))))
        .withColumn("route_id", F.upper(F.trim(F.col("route_id").cast("string"))))
        .withColumn("station_id", F.upper(F.trim(F.col("station_id").cast("string"))))
        .withColumn("origin_station", F.upper(F.trim(F.col("origin_station").cast("string"))))
        .withColumn("destination_station", F.upper(F.trim(F.col("destination_station").cast("string"))))
        .withColumn("region", F.upper(F.trim(F.col("region").cast("string"))))
        .withColumn("event_time", F.to_timestamp("event_time"))
        .withColumn("longitude", F.col("longitude").cast("double"))
        .withColumn("latitude", F.col("latitude").cast("double"))
        .withColumn("temperature", F.col("temperature").cast("double"))
        .withColumn("passenger_count", F.col("passenger_count").cast("long"))
        .withColumn("is_holiday", F.col("is_holiday").cast("boolean"))
    )
    normalized = normalized.replace(
        {"公交": "bus", "地铁": "metro", "出租车": "taxi", "网约车": "ride_hailing", "共享单车": "bike"},
        subset=["transport_type"],
    )

    if missing_strategy == "fill":
        median_temperature = normalized.approxQuantile("temperature", [0.5], 0.01)
        normalized = normalized.fillna({
            "weather": "unknown",
            "temperature": median_temperature[0] if median_temperature else 22.0,
            "is_holiday": False,
        })
    elif missing_strategy != "delete":
        raise ValueError("缺失值策略只能是 fill 或 delete")

    essential = ["trip_id", "transport_type", "route_id", "station_id", "origin_station", "destination_station", "region", "event_time", "passenger_count"]
    missing_count = normalized.filter(F.expr(" OR ".join(f"`{column}` IS NULL" for column in essential))).count()
    normalized = normalized.dropna(subset=essential)

    duplicate_count = normalized.count() - normalized.dropDuplicates(["trip_id"]).count()
    normalized = normalized.dropDuplicates(["trip_id"])

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    station_rows = [
        (item["station_id"], item["region_id"], float(item["longitude"]), float(item["latitude"]), int(item["capacity"]))
        for item in catalog["stations"]
    ]
    route_rows = [
        (route["route_id"], route["transport_type"], station)
        for route in catalog["routes"] for station in route["station_sequence"]
    ]
    stations = spark.createDataFrame(station_rows, ["valid_station_id", "valid_region_id", "catalog_longitude", "catalog_latitude", "station_capacity"])
    route_stations = spark.createDataFrame(route_rows, ["valid_route_id", "valid_route_transport", "valid_route_station"])

    joined = (
        normalized
        .join(F.broadcast(stations), normalized.station_id == stations.valid_station_id, "left")
        .join(
            F.broadcast(route_stations),
            (normalized.route_id == route_stations.valid_route_id)
            & (normalized.station_id == route_stations.valid_route_station)
            & (normalized.transport_type == route_stations.valid_route_transport),
            "left",
        )
    )
    invalid_condition = (
        (F.col("passenger_count") < 0)
        | (~F.col("transport_type").isin(VALID_TRANSPORT_TYPES))
        | F.col("valid_station_id").isNull()
        | F.col("valid_route_id").isNull()
        | (F.col("region") != F.col("valid_region_id"))
        | (F.col("origin_station") == F.col("destination_station"))
        | (F.col("longitude") < 99.0) | (F.col("longitude") > 111.0)
        | (F.col("latitude") < 29.0) | (F.col("latitude") > 41.0)
    )
    invalid_count = joined.filter(invalid_condition).count()
    clean = (
        joined.filter(~invalid_condition)
        .drop("valid_station_id", "valid_region_id", "valid_route_id", "valid_route_transport", "valid_route_station")
        .withColumn("longitude", F.col("catalog_longitude"))
        .withColumn("latitude", F.col("catalog_latitude"))
        .drop("catalog_longitude", "catalog_latitude")
        .withColumn("date", F.date_format("event_time", "yyyy-MM-dd"))
    )
    clean_count = clean.count()
    if clean_count == 0:
        raise ValueError("清洗后无有效数据，请检查文件字段和统一城市目录关系")
    output_path.mkdir(parents=True, exist_ok=True)
    (
        clean.write.mode("overwrite").option("compression", "snappy")
        .partitionBy("date", "transport_type").parquet(str(output_path))
    )
    return {
        "original_count": original_count,
        "missing_count": missing_count,
        "duplicate_count": duplicate_count,
        "invalid_count": invalid_count,
        "clean_count": clean_count,
        "removed_count": original_count - clean_count,
        "output_path": str(output_path),
        "partition_columns": ["date", "transport_type"],
        "storage_format": "Parquet + Snappy",
        "engine": "Spark DataFrame",
    }


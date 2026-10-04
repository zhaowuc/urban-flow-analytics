from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.regression import GBTRegressor, RandomForestRegressor
from pyspark.sql import DataFrame, SparkSession, Window, functions as F
from statsmodels.tsa.arima.model import ARIMA


CATEGORICAL_COLUMNS = ["station_id", "region", "route_id", "transport_type", "weather"]
NUMERIC_COLUMNS = [
    "hour", "day_of_week", "is_weekend", "is_holiday", "temperature",
    "historical_passenger_flow", "recent_passenger_flow",
]


def prepare_ml_frame(frame: DataFrame) -> DataFrame:
    bucketed = (
        frame
        .withColumn("event_bucket", F.from_unixtime(F.floor(F.unix_timestamp("event_time") / 900) * 900).cast("timestamp"))
        .groupBy("event_bucket", "station_id", "region", "route_id", "transport_type", "weather")
        .agg(
            F.sum("passenger_count").cast("double").alias("label"),
            F.avg("temperature").cast("double").alias("temperature"),
            F.max(F.col("is_holiday").cast("int")).alias("is_holiday"),
        )
        .withColumnRenamed("event_bucket", "event_time")
        .withColumn("hour", F.hour("event_time").cast("double"))
        .withColumn("day_of_week", F.dayofweek("event_time").cast("double"))
        .withColumn("is_weekend", F.when(F.dayofweek("event_time").isin([1, 7]), 1.0).otherwise(0.0))
        .withColumn("is_holiday", F.col("is_holiday").cast("double"))
    )
    history_window = Window.partitionBy("station_id", "route_id").orderBy("event_time")
    historical_window = history_window.rowsBetween(-4, -1)
    return (
        bucketed
        .withColumn("recent_passenger_flow", F.lag("label", 1).over(history_window))
        .withColumn("historical_passenger_flow", F.avg("label").over(historical_window))
        .dropna(subset=["recent_passenger_flow", "historical_passenger_flow", "temperature"])
        .withColumn("event_epoch", F.col("event_time").cast("long"))
    )


def _spark_pipeline(model_type: str):
    indexed = [f"{column}_index" for column in CATEGORICAL_COLUMNS]
    encoded = [f"{column}_encoded" for column in CATEGORICAL_COLUMNS]
    indexers = [StringIndexer(inputCol=column, outputCol=output, handleInvalid="keep") for column, output in zip(CATEGORICAL_COLUMNS, indexed)]
    encoder = OneHotEncoder(inputCols=indexed, outputCols=encoded, handleInvalid="keep", dropLast=False)
    assembler = VectorAssembler(inputCols=encoded + NUMERIC_COLUMNS, outputCol="features", handleInvalid="keep")
    if model_type == "random_forest":
        regressor = RandomForestRegressor(
            featuresCol="features", labelCol="label", predictionCol="prediction",
            numTrees=36, maxDepth=8, minInstancesPerNode=2, featureSubsetStrategy="sqrt", seed=20260827,
        )
    elif model_type == "gbt":
        regressor = GBTRegressor(
            featuresCol="features", labelCol="label", predictionCol="prediction",
            maxIter=28, maxDepth=6, stepSize=0.08, minInstancesPerNode=2, seed=20260827,
        )
    else:
        raise ValueError("Spark 模型类型只能是 random_forest 或 gbt")
    return Pipeline(stages=[*indexers, encoder, assembler, regressor])


def train_spark_regression(
    spark: SparkSession,
    parquet_path: Path,
    model_type: str,
    model_path: Path,
) -> dict:
    raw = spark.read.parquet(str(parquet_path))
    prepared = prepare_ml_frame(raw).cache()
    feature_count = prepared.count()
    if feature_count < 200:
        raise ValueError("有效训练样本不足 200 条")
    threshold = prepared.approxQuantile("event_epoch", [0.8], 0.01)[0]
    train = prepared.filter(F.col("event_epoch") <= threshold)
    test = prepared.filter(F.col("event_epoch") > threshold)
    train_count = train.count()
    test_count = test.count()
    if train_count == 0 or test_count == 0:
        raise ValueError("按时间切分后训练集或测试集为空")

    model = _spark_pipeline(model_type).fit(train)
    predictions = model.transform(test).cache()
    metrics = {
        "mae": RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName="mae").evaluate(predictions),
        "rmse": RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName="rmse").evaluate(predictions),
        "r2": RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName="r2").evaluate(predictions),
        "train_count": train_count,
        "test_count": test_count,
        "feature_count": feature_count,
        "split_strategy": "按 event_time 前 80% 训练、后 20% 测试",
        "features": CATEGORICAL_COLUMNS + NUMERIC_COLUMNS,
        "engine": "pyspark.ml",
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.write().overwrite().save(str(model_path))

    curve = [
        {
            "event_time": row["event_time"].isoformat(),
            "station_id": row["station_id"],
            "actual": round(float(row["label"]), 3),
            "predicted": round(max(0.0, float(row["prediction"])), 3),
        }
        for row in predictions.select("event_time", "station_id", "label", "prediction").orderBy("event_time").limit(240).collect()
    ]

    latest_window = Window.partitionBy("station_id", "route_id").orderBy(F.col("event_time").desc())
    latest = prepared.withColumn("row_number", F.row_number().over(latest_window)).filter("row_number = 1").drop("row_number")
    future: list[dict] = []
    for horizon in (15, 30, 60):
        future_frame = (
            latest
            .withColumn("event_time", F.expr(f"event_time + INTERVAL {horizon} MINUTES"))
            .withColumn("hour", F.hour("event_time").cast("double"))
            .withColumn("day_of_week", F.dayofweek("event_time").cast("double"))
            .withColumn("is_weekend", F.when(F.dayofweek("event_time").isin([1, 7]), 1.0).otherwise(0.0))
        )
        station_predictions = (
            model.transform(future_frame)
            .groupBy("station_id", "region")
            .agg(
                F.max("event_time").alias("event_time"),
                F.sum("label").alias("actual_value"),
                F.sum("prediction").alias("predicted_value"),
            )
        )
        for row in station_predictions.collect():
            future.append({
                "station_id": row["station_id"], "route_id": None, "region": row["region"],
                "horizon_minutes": horizon, "predicted_at": row["event_time"].isoformat(),
                "predicted_value": round(max(0.0, float(row["predicted_value"])), 3),
                "actual_value": round(float(row["actual_value"]), 3),
            })
    prepared.unpersist()
    predictions.unpersist()
    return {"metrics": metrics, "curve": curve, "future": future}


def _numeric_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    denominator = float(np.sum(np.square(actual - np.mean(actual))))
    r2 = 1.0 - float(np.sum(np.square(errors))) / denominator if denominator > 0 else 0.0
    return {"mae": mae, "rmse": rmse, "r2": r2}


def train_arima(
    spark: SparkSession,
    parquet_path: Path,
    station_id: str,
    model_path: Path,
) -> dict:
    raw = spark.read.parquet(str(parquet_path)).filter(F.col("station_id") == station_id)
    series_frame = (
        raw.groupBy(F.window("event_time", "15 minutes").alias("time_window"))
        .agg(F.sum("passenger_count").cast("double").alias("passenger_flow"))
        .select(F.col("time_window.start").alias("event_time"), "passenger_flow")
        .orderBy("event_time")
    )
    pandas_frame = series_frame.toPandas()
    if len(pandas_frame) < 120:
        raise ValueError(f"站点 {station_id} 的时间序列样本不足")
    pandas_frame["event_time"] = pd.to_datetime(pandas_frame["event_time"])
    series = (
        pandas_frame.set_index("event_time")["passenger_flow"]
        .resample("15min").sum().fillna(0.0).tail(14 * 24 * 4)
    )
    split = max(96, int(len(series) * 0.8))
    split = min(split, len(series) - 24)
    train, test = series.iloc[:split], series.iloc[split:]
    evaluation_model = ARIMA(train, order=(2, 1, 2), enforce_stationarity=False, enforce_invertibility=False).fit()
    predicted = np.maximum(0.0, np.asarray(evaluation_model.forecast(steps=len(test)), dtype=float))
    metrics = _numeric_metrics(test.to_numpy(dtype=float), predicted)
    metrics.update({
        "train_count": int(len(train)), "test_count": int(len(test)), "feature_count": int(len(series)),
        "split_strategy": "按时间前 80% 训练、后 20% 测试", "features": ["station_history_15min"],
        "engine": "statsmodels ARIMA(2,1,2)",
    })
    final_model = ARIMA(series, order=(2, 1, 2), enforce_stationarity=False, enforce_invertibility=False).fit()
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as output:
        pickle.dump(final_model, output)

    curve = [
        {
            "event_time": timestamp.isoformat(), "station_id": station_id,
            "actual": round(float(actual), 3), "predicted": round(float(prediction), 3),
        }
        for timestamp, actual, prediction in zip(test.index[-192:], test.to_numpy()[-192:], predicted[-192:])
    ]
    forecast = np.maximum(0.0, np.asarray(final_model.forecast(steps=4), dtype=float))
    last_time = series.index[-1]
    future = []
    for horizon, step in ((15, 1), (30, 2), (60, 4)):
        future.append({
            "station_id": station_id, "route_id": None, "region": None,
            "horizon_minutes": horizon,
            "predicted_at": (last_time + pd.Timedelta(minutes=horizon)).isoformat(),
            "predicted_value": round(float(forecast[step - 1]), 3),
            "actual_value": round(float(series.iloc[-1]), 3),
        })
    return {"metrics": metrics, "curve": curve, "future": future}

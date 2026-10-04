import time

from backend.app.database.init_db import initialize_database
from backend.app.services.realtime import realtime_simulator
from backend.app.spark.session import spark_manager


def test_real_structured_streaming_windows_and_pause_resume():
    initialize_database()
    realtime_simulator.reset()
    try:
        started = realtime_simulator.start(60)
        assert started["engine"] == "Spark Structured Streaming"
        deadline = time.time() + 30
        snapshot = started
        while time.time() < deadline:
            time.sleep(1)
            snapshot = realtime_simulator.snapshot()
            if snapshot["window_5"] > 0 and snapshot["hot_stations"] and snapshot["regions"]:
                break
        assert snapshot["state"] == "running", snapshot.get("error")
        assert snapshot["window_5"] > 0
        assert 1 <= len(snapshot["hot_stations"]) <= 40
        assert len(snapshot["regions"]) == 8
        assert snapshot["processing_rate"] >= 0

        paused = realtime_simulator.pause()
        assert paused["state"] == "paused"
        stable_value = paused["window_5"]
        time.sleep(2)
        assert realtime_simulator.snapshot()["window_5"] == stable_value
        assert realtime_simulator.resume()["state"] == "running"
    finally:
        realtime_simulator.stop()
        realtime_simulator.reset()
        spark_manager.stop()

from io import BytesIO

from fastapi.testclient import TestClient

from backend.app.main import app


def _login(client: TestClient, username: str = "admin", password: str = "admin123") -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_data_upload_preview_and_preprocessing_history():
    content = (
        "trip_id,transport_type,route_id,station_id,origin_station,destination_station,region,event_time,longitude,latitude,weather,temperature,is_holiday,passenger_count\n"
        "TEST-1,metro,L001,S002,S001,S002,R01,2026-08-27 08:00:00,104.8,35.0,sunny,25.0,false,18\n"
        "TEST-2,bus,L004,S006,S002,S006,R02,2026-08-27 08:01:00,106.8,35.2,cloudy,24.0,false,12\n"
    ).encode("utf-8")
    with TestClient(app) as client:
        headers = _login(client)
        response = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"file": ("api-upload-test.csv", BytesIO(content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        dataset = response.json()
        assert dataset["row_count"] == 2
        preview = client.get(f"/api/datasets/{dataset['id']}/preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["total"] == 2
        assert preview.json()["rows"][0]["station_id"] == "S002"

        tasks = client.get("/api/preprocessing/tasks", headers=headers)
        assert tasks.status_code == 200
        assert any(item["status"] == "completed" and item["report"].get("engine") == "Spark DataFrame" for item in tasks.json())


def test_analysis_models_warnings_logs_and_settings_apis():
    with TestClient(app) as client:
        admin_headers = _login(client)
        viewer_headers = _login(client, "viewer", "viewer123")

        analysis = client.get("/api/analysis/latest", headers=viewer_headers)
        assert analysis.status_code == 200
        assert analysis.json()["result"]["engine"] == "Spark SQL + DataFrame"
        assert len(analysis.json()["result"]["od_top10"]) == 10

        comparison = client.get("/api/models/comparison", headers=viewer_headers)
        assert comparison.status_code == 200
        assert {item["model_type"] for item in comparison.json()} == {"arima", "random_forest", "gbt"}
        assert all(item["mae"] is not None and item["rmse"] is not None and item["r2"] is not None for item in comparison.json())

        warnings = client.get("/api/warnings", headers=viewer_headers)
        assert warnings.status_code == 200
        assert all(abs(item["load_rate"] - item["predicted_flow"] / item["capacity"]) < 1e-9 for item in warnings.json() if item["source"] == "prediction")

        logs = client.get("/api/logs?limit=20", headers=admin_headers)
        assert logs.status_code == 200
        assert any(item["action"] == "login" for item in logs.json())

        settings = client.get("/api/settings", headers=viewer_headers)
        assert settings.status_code == 200
        assert {"warning.yellow", "warning.orange", "warning.red"}.issubset(settings.json())

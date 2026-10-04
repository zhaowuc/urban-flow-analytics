from fastapi.testclient import TestClient

from backend.app.main import app


def _headers(client: TestClient) -> dict:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_warning_and_map_status_are_consistent():
    with TestClient(app) as client:
        headers = _headers(client)
        overview = client.get("/api/dashboard/overview", headers=headers)
        assert overview.status_code == 200, overview.text
        payload = overview.json()
        assert len(payload["station_map"]) == 40
        warning_by_station = {item["station_id"]: item["level"] for item in payload["warnings"]}
        for station in payload["station_map"]:
            assert station["warning_level"] == warning_by_station.get(station["station_id"], "normal")
        assert payload["summary"]["warning_count"] == len(payload["warnings"])


def test_decision_report_can_be_generated_as_offline_html():
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post("/api/reports/generate", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "星海示例市" in payload["html"]
        assert "内置虚拟示例城市交通数据集" in payload["html"]
        download = client.get("/api/reports/download", params={"path": payload["path"]}, headers=headers)
        assert download.status_code == 200
        assert "text/html" in download.headers["content-type"]


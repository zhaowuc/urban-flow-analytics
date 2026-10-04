from fastapi.testclient import TestClient

from backend.app.main import app


def login(client: TestClient, username: str, password: str) -> tuple[dict, dict]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def test_login_rbac_and_fixed_catalog():
    with TestClient(app) as client:
        admin, admin_headers = login(client, "admin", "admin123")
        analyst, analyst_headers = login(client, "analyst", "analyst123")
        viewer, viewer_headers = login(client, "viewer", "viewer123")
        assert "users:manage" in admin["user"]["permissions"]
        assert "analysis:run" in analyst["user"]["permissions"]
        assert "users:manage" not in viewer["user"]["permissions"]

        assert client.get("/api/users", headers=admin_headers).status_code == 200
        assert client.get("/api/users", headers=analyst_headers).status_code == 403
        assert client.get("/api/users", headers=viewer_headers).status_code == 403

        city = client.get("/api/catalog/city", headers=viewer_headers)
        assert city.status_code == 200
        assert len(city.json()["regions"]) == 8
        assert len(city.json()["stations"]) == 40
        assert len(city.json()["routes"]) == 12

        geojson = client.get("/api/catalog/geojson", headers=viewer_headers)
        assert geojson.status_code == 200
        assert len(geojson.json()["features"]) == 8


def test_health_is_not_hardcoded():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["web"]["ok"] is True
        assert payload["database"]["ok"] is True
        assert payload["data_directory"]["ok"] is True
        assert payload["deployment_mode"] == "Spark Local 离线部署模式"


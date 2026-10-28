from fastapi.testclient import TestClient
from goalpost.main import app


def test_health() -> None:
    with TestClient(app, base_url="http://localhost") as client:  # the API only serves localhost
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

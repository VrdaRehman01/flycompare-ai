from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_api_liveness() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "flycompare-api"}


def test_openapi_document_is_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "FlyCompare AI"

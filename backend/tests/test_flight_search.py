from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import CSRF, future

# Like the website, send the request-verification header that state-changing routes require.
client = TestClient(app, headers=CSRF)


def test_demo_search_returns_explicitly_labeled_offers():
    response = client.post("/api/flights/search", json={
        "origin": "Karachi (KHI)", "destination": "New York (NYC)",
        "departure_date": future(30), "return_date": future(40),
        "trip_type": "round-trip", "passengers": 2, "cabin": "Economy",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_status"] == "demo"
    assert len(payload["results"]) == 3
    assert all(item["data_status"] == "demo" for item in payload["results"])
    assert all("not a live" in item["disclaimer"].lower() for item in payload["results"])


def test_search_rejects_same_origin_and_destination():
    response = client.post("/api/flights/search", json={
        "origin": "Karachi", "destination": "Karachi", "departure_date": future(30),
        "trip_type": "one-way", "passengers": 1, "cabin": "Economy",
    })
    assert response.status_code == 422

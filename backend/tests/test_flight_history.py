from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_search_history_endpoint_returns_saved_searches():
    response = client.get("/api/flights/history")

    assert response.status_code == 200

    history = response.json()
    assert isinstance(history, list)

    if history:
        latest = history[0]
        assert "origin" in latest
        assert "destination" in latest
        assert "departure_date" in latest
        assert "result_count" in latest
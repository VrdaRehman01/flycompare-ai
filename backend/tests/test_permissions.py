from tests.conftest import make_client, register
from tests.conftest import future

OFFER = {"id": "off_abc", "airline": "Example Air", "price": 114.7, "currency": "USD", "origin": "KHI", "destination": "DXB"}
SEARCH = {
    "origin": "Karachi (KHI)", "destination": "Dubai (DXB)", "departure_date": future(40),
    "return_date": future(47), "trip_type": "round-trip", "passengers": 1, "cabin": "Economy",
}


def test_account_endpoints_require_sign_in(client):
    for path in ("/api/account/profile", "/api/account/saved-flights", "/api/account/favourites", "/api/account/history", "/api/account/recently-viewed"):
        assert client.get(path).status_code == 401, path
    assert client.get("/api/insights/analytics?scope=me").status_code == 401


def test_saved_flights_are_private_to_their_owner(client):
    register(client, email="a@example.com")
    saved = client.post("/api/account/saved-flights", json={"offer": OFFER, "search": SEARCH})
    assert saved.status_code == 201
    saved_id = saved.json()["id"]
    # Saving the same offer twice is idempotent.
    assert client.post("/api/account/saved-flights", json={"offer": OFFER}).json()["id"] == saved_id

    other = make_client()
    register(other, email="b@example.com")
    assert other.get("/api/account/saved-flights").json() == []
    assert other.delete(f"/api/account/saved-flights/{saved_id}").status_code == 404

    assert len(client.get("/api/account/saved-flights").json()) == 1
    assert client.delete(f"/api/account/saved-flights/{saved_id}").status_code == 204
    assert client.get("/api/account/saved-flights").json() == []


def test_saved_flight_requires_offer_fields(client):
    register(client)
    assert client.post("/api/account/saved-flights", json={"offer": {"id": "x"}}).status_code == 422


def test_search_history_is_per_user_and_hidden_from_anonymous(client):
    register(client, email="a@example.com")
    assert client.post("/api/flights/search", json=SEARCH).status_code == 200

    other = make_client()
    register(other, email="b@example.com")
    other.post("/api/flights/search", json={**SEARCH, "destination": "London (LHR)"})

    mine = client.get("/api/flights/history").json()
    assert [h["destination_code"] for h in mine] == ["DXB"]
    assert [h["destination_code"] for h in other.get("/api/account/history").json()] == ["LHR"]
    assert make_client().get("/api/flights/history").json() == []


def test_favourites_and_recently_viewed(client):
    register(client)
    assert client.post("/api/account/favourites", json={"airport_code": "DXB"}).json() == ["DXB"]
    assert client.post("/api/account/favourites", json={"airport_code": "DXB"}).json() == ["DXB"]
    assert client.post("/api/account/favourites", json={"airport_code": "dubai"}).status_code == 422
    assert client.delete("/api/account/favourites/DXB").json() == []

    for i in range(25):
        client.post("/api/account/recently-viewed", json={"offer": {**OFFER, "id": f"off_{i}"}})
    recent = client.get("/api/account/recently-viewed").json()
    assert len(recent) == 20
    assert recent[0]["offer_id"] == "off_24"

    other = make_client()
    register(other, email="b@example.com")
    assert other.get("/api/account/recently-viewed").json() == []

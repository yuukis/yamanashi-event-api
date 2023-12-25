from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_read_events():
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_today():
    response = client.get("/events/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_event():
    response = client.get("/events/304904")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_read_events_in_year():
    response = client.get("/events/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_in_year_month():
    response = client.get("/events/in/2023/12")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_in_year_month_day():
    response = client.get("/events/in/2023/12/31")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_fromto_year_month():
    response = client.get("/events/from/2023/12/to/2024/01")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
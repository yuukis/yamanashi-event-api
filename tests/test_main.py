from fastapi.testclient import TestClient
from app.main import app, get_user_agent

client = TestClient(app)


def test_read_events():
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_with_keyword():
    response = client.get("/events?keyword=python")
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
    assert "description" not in response.json()


def test_read_event_detail():
    response = client.get("/events/304904/detail")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    assert "description" in response.json()


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


def test_read_events_fromto_year_month_invalid():
    response = client.get("/events/from/2023/12/to/2022/11")
    assert response.status_code == 400


def test_read_events_full():
    response = client.get("/events/full")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_full_today():
    response = client.get("/events/full/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_events_full_in_year():
    response = client.get("/events/full/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


def test_get_user_agent():
    config = {
        "metadata": {
            "version": "1.0.0"
        },
        "api_client": {
            "user_agent": "MyApp/{version}"
        }
    }
    expected_user_agent = "MyApp/1.0.0"
    user_agent = get_user_agent(config)
    assert user_agent == expected_user_agent

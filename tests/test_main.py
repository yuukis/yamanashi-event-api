from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app, get_user_agent
from app.models import EventDetail, Group
from datetime import datetime, timezone

client = TestClient(app)


class MockConnpassEventRequest:
    def __init__(self, **kwargs):
        pass

    def get_events(self):
        json = [
            {
                "event_id": 1,
                "title": "Event 1",
                "catch": "Catch 1",
                "hash_tag": "Hash Tag",
                "event_url": "Event URL",
                "started_at": "2022-01-01T12:00:00+09:00",
                "ended_at": "2022-01-01T13:00:00+09:00",
                "updated_at": "2022-01-01T00:00:00+09:00",
                "limit": 0,
                "accepted": 0,
                "waiting": 0,
                "owner_name": "Owner 1",
                "place": "Place",
                "address": "Address",
                "group_name": "",
                "group_url": "",
                "description": "Description",
                "lat": "",
                "lon": ""
            },
            {
                "event_id": 2,
                "title": "Python Event",
                "catch": "Python Catch",
                "hash_tag": "Hash Tag",
                "event_url": "Event URL",
                "started_at": "2022-01-02T12:00:00+09:00",
                "ended_at": "2022-01-02T13:00:00+09:00",
                "updated_at": "2022-01-01T00:00:00+09:00",
                "limit": 0,
                "accepted": 0,
                "waiting": 0,
                "owner_name": "Owner 2",
                "place": "Place",
                "address": "Address",
                "group_name": "",
                "group_url": "",
                "description": "Description",
                "lat": "",
                "lon": ""
            }
        ]
        events = EventDetail.from_json(json)
        return events

    def get_last_modified(self):
        last_modified = datetime.fromtimestamp(123, timezone.utc)
        return last_modified


class MockConnpassGroupRequest:
    def __init__(self, **kwargs):
        pass

    def get_groups(self):
        json = [
            {
                "id": 1,
                "key": "Key",
                "title": "Title",
                "sub_title": "Sub Title",
                "url": "URL",
                "description": "Description",
                "owner_text": "Owner Text",
                "image_url": "Image URL",
                "website_url": "Website URL",
                "x_username": "X Username",
                "facebook_url": "Facebook URL",
                "member_users_count": 100
            }
        ]
        groups = Group.from_json(json)
        return groups
    
    def get_last_modified(self):
        last_modified = datetime.fromtimestamp(123, timezone.utc)
        return last_modified


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events():
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_with_keyword():
    response = client.get("/events?keyword=python")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_today():
    response = client.get("/events/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_in_year():
    response = client.get("/events/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_in_year_month():
    response = client.get("/events/in/2023/12")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_in_year_month_day():
    response = client.get("/events/in/2024/01/28")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_fromto_year_month():
    response = client.get("/events/from/2023/12/to/2024/01")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_fromto_year_month_invalid():
    response = client.get("/events/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full():
    response = client.get("/events/full")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_today():
    response = client.get("/events/full/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_in_year():
    response = client.get("/events/full/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_in_year_month():
    response = client.get("/events/full/in/2023/12")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_in_year_month_day():
    response = client.get("/events/full/in/2024/01/28")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_fromto_year_month():
    response = client.get("/events/full/from/2023/12/to/2024/01")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_events_full_fromto_year_month_invalid():
    response = client.get("/events/full/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequest)
def test_read_group():
    response = client.get("/groups")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


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

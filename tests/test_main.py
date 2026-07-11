from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest
from app.main import app, get_user_agent, get_groups_from_icalendar
from app.main import request_events, request_groups, get_groups_from_archives
from app.main import get_archive_urls, preload_archive_indexes
from app.main import get_events
from app.cache import EventRequestCache
from app.archive import ArchiveException
from app.models import EventDetail, Group
from datetime import datetime, timezone

client = TestClient(app)


class MockConnpassEventRequest:
    def __init__(self, **kwargs):
        pass

    def get_events(self):
        json = [
            {
                "uid": "UID 1",
                "event_id": 1,
                "title": "Event 1",
                "catch": "Catch 1",
                "hash_tag": "Hash Tag",
                "event_url": "Event URL",
                "started_at": "2022-01-01T12:00:00+09:00",
                "ended_at": "2022-01-01T13:00:00+09:00",
                "updated_at": "2022-01-01T00:00:00+09:00",
                "open_status": "preopen",
                "limit": 0,
                "accepted": 0,
                "waiting": 0,
                "owner_name": "Owner 1",
                "place": "Place",
                "address": "Address",
                "group_key": "",
                "group_name": "",
                "group_url": "",
                "description": "Description",
                "lat": "",
                "lon": ""
            },
            {
                "uid": "UID 2",
                "event_id": 2,
                "title": "Python Event",
                "catch": "Python Catch",
                "hash_tag": "Hash Tag",
                "event_url": "Event URL",
                "started_at": "2022-01-02T12:00:00+09:00",
                "ended_at": "2022-01-02T13:00:00+09:00",
                "updated_at": "2022-01-01T00:00:00+09:00",
                "open_status": "open",
                "limit": 0,
                "accepted": 0,
                "waiting": 0,
                "owner_name": "Owner 2",
                "place": "Place",
                "address": "Address",
                "group_key": "",
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


class MockICalEventRequest:
    def __init__(self, **kwargs):
        pass

    def get_events(self):
        json = [
            {
                "uid": "UID 1",
                "event_id": None,
                "title": "Event 1",
                "catch": None,
                "hash_tag": None,
                "event_url": "Event URL",
                "started_at": "2022-01-01T12:00:00+09:00",
                "ended_at": "2022-01-01T13:00:00+09:00",
                "updated_at": "2022-01-01T00:00:00+09:00",
                "open_status": "preopen",
                "limit": None,
                "accepted": None,
                "waiting": None,
                "owner_name": None,
                "place": "Place",
                "address": "Address",
                "group_key": "Group Key 1",
                "group_name": "Group Name 1",
                "group_url": "Group URL 1",
                "description": None,
                "lat": None,
                "lon": None
            }
        ]
        events = EventDetail.from_json(json)
        return events

    def get_last_modified(self):
        last_modified = datetime.fromtimestamp(123, timezone.utc)
        return last_modified


class MockArchiveIndexRequest:
    requested_urls = []
    preloaded_urls = []

    def __init__(self, **kwargs):
        self.url = kwargs.get("url")
        MockArchiveIndexRequest.requested_urls.append(self.url)

    def get_events(self):
        json = [
            {
                "uid": "yamanashi-web-2012-05-19-001@yamanashi-event-archive",
                "event_id": None,
                "title": "山梨Web勉強会 第1回",
                "catch": "山梨のWeb制作者・開発者が集まる勉強会",
                "hash_tag": "yamanashiweb",
                "event_url": "https://example.com/archive/yamanashi-web/2012-05-19-001",
                "started_at": "2012-05-19T14:00:00+09:00",
                "ended_at": "2012-05-19T17:00:00+09:00",
                "updated_at": "2026-06-30T00:00:00+09:00",
                "open_status": "close",
                "limit": None,
                "accepted": None,
                "waiting": None,
                "owner_name": None,
                "place": "山梨県立図書館",
                "address": "山梨県甲府市北口2-8-1",
                "group_key": "yamanashi-web",
                "group_name": "山梨Web勉強会",
                "group_url": "https://example.com/yamanashi-web",
                "description": "山梨Web勉強会の初回イベント。",
                "lat": None,
                "lon": None
            }
        ]
        return EventDetail.from_json(json)

    def get_groups(self):
        json = [
            {
                "key": "yamanashi-web",
                "title": "山梨Web勉強会",
                "sub_title": "山梨県内のWeb制作者・開発者向け勉強会",
                "url": "https://example.com/yamanashi-web",
                "description": "山梨県内のWeb制作・Web開発勉強会です。",
                "owner_text": None,
                "image_url": None,
                "website_url": "https://example.com/yamanashi-web",
                "x_username": None,
                "facebook_url": None,
                "member_users_count": None,
                "ical_url": None,
                "archive_source": "yamanashi-event-archive",
                "archive_url": "https://github.com/yuukis/yamanashi-event-archive"
            }
        ]
        return Group.from_json(json)

    def get_last_modified(self):
        last_modified = datetime.fromtimestamp(123, timezone.utc)
        return last_modified

    def preload(self):
        MockArchiveIndexRequest.preloaded_urls.append(self.url)


class MockFailingPreloadArchiveIndexRequest:
    def __init__(self, **kwargs):
        self.url = kwargs.get("url")

    def preload(self):
        raise ArchiveException(500, "Failed to fetch archive index")


@pytest.fixture(autouse=True)
def mock_archive_index_request():
    MockArchiveIndexRequest.requested_urls = []
    MockArchiveIndexRequest.preloaded_urls = []
    with patch("app.main.ArchiveIndexRequest", MockArchiveIndexRequest):
        yield


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events():
    response = client.get("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_with_keyword():
    response = client.get("/events?keyword=python")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_today():
    response = client.get("/events/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_this_week():
    response = client.get("/events/week/this")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_next_week():
    response = client.get("/events/week/next")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year():
    response = client.get("/events/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year_month():
    response = client.get("/events/in/2023/12")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year_month_day():
    response = client.get("/events/in/2024/01/28")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_fromto_year_month():
    response = client.get("/events/from/2023/12/to/2024/01")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_fromto_year_month_invalid():
    response = client.get("/events/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full():
    response = client.get("/events/full")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_today():
    response = client.get("/events/full/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_this_week():
    response = client.get("/events/full/week/this")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_next_week():
    response = client.get("/events/full/week/next")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_in_year():
    response = client.get("/events/full/in/2023")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_in_year_month():
    response = client.get("/events/full/in/2023/12")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_in_year_month_day():
    response = client.get("/events/full/in/2024/01/28")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_fromto_year_month():
    response = client.get("/events/full/from/2023/12/to/2024/01")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "description" in response.json()[0]


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
def test_read_events_full_fromto_year_month_invalid():
    response = client.get("/events/full/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.main.get_groups_from_icalendar")
def test_read_events_summary(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/events/summary")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert "Last-Modified" in response.headers

    data = response.json()
    assert data["from_year"] == 2010
    assert data["granularity"] == "month"
    assert len(data["years"]) == data["to_year"] - data["from_year"] + 1

    # Archive mock event: 2012-05-19, group_key "yamanashi-web" (present in group directory)
    year_2012 = next(y for y in data["years"] if y["year"] == 2012)
    assert year_2012["event_count"] == 1
    assert year_2012["groups"][0]["key"] == "yamanashi-web"
    assert year_2012["groups"][0]["name"] == "山梨Web勉強会"
    assert year_2012["groups"][0]["url"] == "https://example.com/yamanashi-web"

    # Ical mock event: 2022-01-01, group_key "Group Key 1" is absent from the
    # group directory (/groups), so it must not appear even though the event exists
    year_2022 = next(y for y in data["years"] if y["year"] == 2022)
    assert year_2022["event_count"] == 2
    assert all(g["key"] != "Group Key 1" for g in year_2022["groups"])

    # Connpass mock events have an empty group_key and must not appear as a group
    assert all(g["key"] != "" for y in data["years"] for g in y["groups"])

    heatmap_by_period = {h["period"]: h["count"] for h in data["heatmap"]}
    assert heatmap_by_period["2012-05"] == 1
    assert heatmap_by_period["2010-01"] == 0


class MockConnpassGroupRequestNewerLastModified(MockConnpassGroupRequest):
    def get_last_modified(self):
        return datetime.fromtimestamp(999999, timezone.utc)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequestNewerLastModified)
@patch("app.main.get_groups_from_icalendar")
@patch("app.main.cache", EventRequestCache(prefix="test_summary_last_modified_"))
def test_read_events_summary_last_modified_reflects_newer_groups(
        mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/events/summary")
    assert response.status_code == 200

    expected = datetime.fromtimestamp(999999, timezone.utc) \
        .strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert response.headers["Last-Modified"] == expected


class MockConnpassEventRequestCapturingTTL:
    received_cache_ttl = []

    def __init__(self, **kwargs):
        MockConnpassEventRequestCapturingTTL.received_cache_ttl.append(
            kwargs.get("cache_ttl"))

    def get_events(self):
        return []

    def get_last_modified(self):
        return datetime.fromtimestamp(123, timezone.utc)


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequestCapturingTTL)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.main.get_groups_from_icalendar")
@patch("app.main.cache", EventRequestCache(prefix="test_summary_ttl_"))
def test_read_events_summary_uses_extended_ttls(mock_get_groups_from_icalendar):
    import app.main as main_module

    mock_get_groups_from_icalendar.return_value = []
    MockConnpassEventRequestCapturingTTL.received_cache_ttl = []

    response = client.get("/events/summary")
    assert response.status_code == 200

    # The low-level connpass cache_ttl (24h) must reach every
    # ConnpassEventRequest call triggered by the summary endpoint.
    assert len(MockConnpassEventRequestCapturingTTL.received_cache_ttl) > 0
    assert all(ttl == 3600 * 24
              for ttl in MockConnpassEventRequestCapturingTTL.received_cache_ttl)

    # The cached raw EventDetail list (get_events()'s EventRequestCache
    # entry) must use a 7 day expiry, not the default 72 hours used by
    # the other /events endpoints. The years/heatmap payload built from
    # it is not itself cached and is recomputed on every request.
    from_year = 2010
    to_year = datetime.now().year
    ym = [f"{y:04}{m:02}" for y in range(from_year, to_year + 1) for m in range(1, 13)]
    params = {"ym": ym, "keyword": None}
    key = main_module.cache.generate_key(params) + ":content"
    expiry = main_module.cache._expiry[key]
    remaining = expiry - datetime.now(timezone.utc).timestamp()
    assert 3600 * 24 * 6 < remaining <= 3600 * 24 * 7


@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.main.get_groups_from_icalendar")
def test_read_group(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.main.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.main.get_groups_from_icalendar")
@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "subdomain": ["test"],
        "archives": [
            {
                "url": "https://example.com/archive/index.json"
            }
        ]
    }
})
@patch("app.main.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.main.cache", EventRequestCache(prefix="test_archive_group_"))
def test_read_group_includes_archive_source(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups")

    assert response.status_code == 200
    archive_group = [
        group for group in response.json()
        if group["key"] == "yamanashi-web"
    ][0]
    assert archive_group["archive_source"] == "yamanashi-event-archive"
    assert archive_group["archive_url"] == \
        "https://github.com/yuukis/yamanashi-event-archive"


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


def test_get_groups_from_icalendar():
    config = {
        "scope": {
            "icalendar": [
                {
                    "key": "test_key_1",
                    "name": "Test Group 1",
                    "image_url": "http://example.com/image.png",
                    "group_url": "http://example.com/group",
                    "ical_url": "http://example.com/ical"
                },
                {
                    "key": "test_key_2",
                    "name": "Test Group 2",
                    "group_url": "http://example.com/group",
                    "ical_url": "http://example.com/ical"
                }
            ]
        }
    }
    groups = get_groups_from_icalendar(config)
    assert len(groups) == 2

    assert groups[0].key == "test_key_1"
    assert groups[0].title == "Test Group 1"
    assert groups[0].url == "http://example.com/group"
    assert groups[0].image_url == "http://example.com/image.png"
    assert groups[0].ical_url == "http://example.com/ical"

    assert groups[1].key == "test_key_2"
    assert groups[1].title == "Test Group 2"
    assert groups[1].url == "http://example.com/group"
    assert groups[1].image_url is None
    assert groups[1].ical_url == "http://example.com/ical"
    assert groups[1].description is None


@patch("app.main.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.main.IcalEventRequest", MockICalEventRequest)
@patch("app.main.cache", EventRequestCache(prefix="test_get_events_no_bg_"))
def test_get_events_without_background_tasks():
    events, last_modified = get_events({"ym": ["202201"], "keyword": None})

    assert isinstance(events, list)
    assert len(events) > 0


@patch("app.main.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "archives": [
            {
                "url": "https://example.com/archive/index.json"
            }
        ]
    }
})
def test_request_events_from_archives():
    events, last_modified = request_events({"ym": ["201205"]})

    assert len(events) == 1
    assert events[0].uid == \
        "yamanashi-web-2012-05-19-001@yamanashi-event-archive"
    assert events[0].group_key == "yamanashi-web"
    assert last_modified == datetime.fromtimestamp(123, timezone.utc)


@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "archives": [
            {
                "url": [
                    "https://example.com/archive/index-1.json",
                    "https://example.com/archive/index-2.json"
                ]
            }
        ]
    }
})
def test_request_events_from_archive_urls():
    events, last_modified = request_events({})

    assert len(events) == 1
    assert last_modified == datetime.fromtimestamp(123, timezone.utc)
    assert MockArchiveIndexRequest.requested_urls == [
        "https://example.com/archive/index-1.json",
        "https://example.com/archive/index-2.json"
    ]


@patch("app.main.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "archives": [
            {
                "url": "https://example.com/archive/index.json"
            }
        ]
    }
})
def test_request_groups_from_archives():
    groups, last_modified = request_groups({})

    assert len(groups) == 1
    assert groups[0].key == "yamanashi-web"
    assert groups[0].title == "山梨Web勉強会"
    assert groups[0].archive_source == "yamanashi-event-archive"
    assert groups[0].archive_url == \
        "https://github.com/yuukis/yamanashi-event-archive"
    assert last_modified == datetime.fromtimestamp(123, timezone.utc)


@patch("app.main.ArchiveIndexRequest", MockArchiveIndexRequest)
def test_get_groups_from_archives():
    config = {
        "scope": {
            "archives": [
                {
                    "url": "https://example.com/archive/index.json"
                }
            ]
        }
    }

    groups = get_groups_from_archives(config)

    assert len(groups) == 1
    assert groups[0].key == "yamanashi-web"
    assert groups[0].archive_source == "yamanashi-event-archive"
    assert groups[0].archive_url == \
        "https://github.com/yuukis/yamanashi-event-archive"


def test_get_archive_urls():
    config = {
        "scope": {
            "archives": [
                {
                    "url": [
                        "https://example.com/archive/index-1.json",
                        "https://example.com/archive/index-2.json"
                    ]
                },
                {
                    "name": "missing url"
                },
                {
                    "url": "https://example.com/archive/index-3.json"
                }
            ]
        }
    }

    urls = get_archive_urls(config)

    assert urls == [
        "https://example.com/archive/index-1.json",
        "https://example.com/archive/index-2.json",
        "https://example.com/archive/index-3.json"
    ]


@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "archives": [
            {
                "url": [
                    "https://example.com/archive/index-1.json",
                    "https://example.com/archive/index-2.json"
                ]
            }
        ]
    }
})
def test_preload_archive_indexes():
    preload_archive_indexes()

    assert MockArchiveIndexRequest.preloaded_urls == [
        "https://example.com/archive/index-1.json",
        "https://example.com/archive/index-2.json"
    ]


@patch("app.main.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "archives": [
            {
                "url": [
                    "https://example.com/archive/index-1.json"
                ]
            }
        ]
    }
})
def test_preload_archive_indexes_does_not_raise_on_error():
    with patch("app.main.ArchiveIndexRequest",
               MockFailingPreloadArchiveIndexRequest):
        preload_archive_indexes()

from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest
from app.main import app
from app.service import get_user_agent, get_groups_from_icalendar
from app.service import request_events, request_groups, get_groups_from_archives
from app.service import get_archive_urls, preload_archive_indexes
from app.service import get_events, normalize_event_params
from app.routes import get_max_age_until_next_period
from app.cache import EventRequestCache
from app.providers.archive import ArchiveException
from app.models import Event, Group
from datetime import datetime, timedelta, timezone

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
        events = Event.from_json(json)
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
        events = Event.from_json(json)
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
        return Event.from_json(json)

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
    with patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest):
        yield


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events():
    response = client.get("/events")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    # /events now returns full details by default (no more /events/full split)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_with_keyword():
    response = client.get("/events?keyword=python")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_today():
    response = client.get("/events/day/today")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_today_legacy_path_still_works():
    response = client.get("/events/today")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


class MockConnpassEventRequestCapturingYmd:
    received_ymd = []

    def __init__(self, **kwargs):
        MockConnpassEventRequestCapturingYmd.received_ymd.append(kwargs.get("ymd"))

    def get_events(self):
        return []

    def get_last_modified(self):
        return datetime.fromtimestamp(123, timezone.utc)


def _assert_consecutive_week_starting_monday(ymd, expected_monday):
    dates = [datetime.strptime(d, "%Y%m%d").date() for d in ymd]
    assert dates == [expected_monday + timedelta(days=i) for i in range(7)]
    assert dates[0].weekday() == 0


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCapturingYmd)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_this_week():
    MockConnpassEventRequestCapturingYmd.received_ymd = []

    response = client.get("/events/week/this")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]

    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    assert len(MockConnpassEventRequestCapturingYmd.received_ymd) > 0
    for ymd in MockConnpassEventRequestCapturingYmd.received_ymd:
        _assert_consecutive_week_starting_monday(ymd, this_monday)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCapturingYmd)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_next_week():
    MockConnpassEventRequestCapturingYmd.received_ymd = []

    response = client.get("/events/week/next")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]

    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    next_monday = this_monday + timedelta(days=7)
    assert len(MockConnpassEventRequestCapturingYmd.received_ymd) > 0
    for ymd in MockConnpassEventRequestCapturingYmd.received_ymd:
        _assert_consecutive_week_starting_monday(ymd, next_monday)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_year():
    response = client.get("/events/year/2023")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year_legacy_path_still_works():
    response = client.get("/events/in/2023")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month():
    response = client.get("/events/month/2023/12")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year_month_legacy_path_still_works():
    response = client.get("/events/in/2023/12")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


def test_normalize_event_params_shares_cache_key_across_equivalent_uid():
    base = normalize_event_params({"ym": ["202312"], "keyword": None, "uid": None})
    padded = normalize_event_params(
        {"ym": ["202312"], "keyword": None, "uid": "  UID 2  "})
    canonical = normalize_event_params(
        {"ym": ["202312"], "keyword": None, "uid": "UID 2"})
    empty = normalize_event_params({"ym": ["202312"], "keyword": None, "uid": ""})

    # /summary/events omits the "uid" key entirely rather than passing None
    no_uid_key = normalize_event_params({"ym": ["202312"], "keyword": None})

    cache = EventRequestCache()
    assert cache.generate_key(padded) == cache.generate_key(canonical)
    assert cache.generate_key(empty) == cache.generate_key(base)
    assert cache.generate_key(no_uid_key) == cache.generate_key(base)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_uid():
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 2"
    assert events[0]["title"] == "Python Event"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_padded_uid():
    response = client.get("/events/month/2023/12",
                          params={"uid": "  UID 2  "})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 2"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_unmatched_uid():
    response = client.get("/events/month/2023/12",
                          params={"uid": "No Such UID"})
    assert response.status_code == 200
    assert response.json() == []


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.cache", EventRequestCache(prefix="test_uid_noop_"))
def test_read_events_month_with_empty_uid_is_noop():
    # Uses an isolated cache so this comparison isn't polluted by other
    # tests' cache entries for the same year/month. Compares uids rather
    # than full response bodies since uid="" now normalizes to the same
    # cache key as no uid at all, and a cache hit vs. a fresh computation
    # can otherwise disagree on unrelated fields (e.g. keywords).
    baseline = client.get("/events/month/2023/12")
    response = client.get("/events/month/2023/12",
                          params={"uid": ""})
    assert response.status_code == 200
    baseline_uids = sorted(ev["uid"] for ev in baseline.json())
    response_uids = sorted(ev["uid"] for ev in response.json())
    assert response_uids == baseline_uids
    assert len(response_uids) > 0


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_uid_and_keyword():
    # "UID 1" is overwritten by the iCal source's non-matching event during
    # dedup, so combining it with a keyword that only the connpass version
    # would match must yield no results (AND semantics).
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 1", "keyword": "python"})
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2", "keyword": "python"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 2"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_fields():
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2", "fields": "uid,description"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0] == {"uid": "UID 2", "description": "Description"}


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_fields_ignores_unknown_names():
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2", "fields": "uid,bogus"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0] == {"uid": "UID 2"}


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_empty_fields_is_noop():
    baseline = client.get("/events/month/2023/12", params={"uid": "UID 2"})
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2", "fields": ""})
    assert response.status_code == 200
    assert response.json() == baseline.json()


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_with_fields_keeps_cache_headers():
    response = client.get("/events/month/2023/12",
                          params={"uid": "UID 2", "fields": "uid"})
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    assert response.headers["Cache-Control"] == "public, max-age=3600"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_day():
    response = client.get("/events/day/2024/01/28")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_in_year_month_day_legacy_path_still_works():
    response = client.get("/events/in/2024/01/28")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_range():
    response = client.get("/events/range/from/2023/12/to/2024/01")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_range_invalid():
    response = client.get("/events/range/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_fromto_year_month_legacy_path_still_works():
    response = client.get("/events/from/2023/12/to/2024/01")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert "description" in events[0]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_fromto_year_month_invalid_legacy_path_still_works():
    response = client.get("/events/from/2023/12/to/2022/11")
    assert response.status_code == 400


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_events_summary(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/events")
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


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_events_summary_legacy_path_still_works(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/events/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["from_year"] == 2010
    assert data["granularity"] == "month"


class MockConnpassGroupRequestNewerLastModified(MockConnpassGroupRequest):
    def get_last_modified(self):
        return datetime.fromtimestamp(999999, timezone.utc)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequestNewerLastModified)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_last_modified_"))
def test_read_events_summary_last_modified_reflects_newer_groups(
        mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/events")
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


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCapturingTTL)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_ttl_"))
def test_read_events_summary_uses_extended_ttls(mock_get_groups_from_icalendar):
    import app.service as service_module

    mock_get_groups_from_icalendar.return_value = []
    MockConnpassEventRequestCapturingTTL.received_cache_ttl = []

    response = client.get("/summary/events")
    assert response.status_code == 200

    # The low-level connpass cache_ttl (24h) must reach every
    # ConnpassEventRequest call triggered by the summary endpoint.
    assert len(MockConnpassEventRequestCapturingTTL.received_cache_ttl) > 0
    assert all(ttl == 3600 * 24
              for ttl in MockConnpassEventRequestCapturingTTL.received_cache_ttl)

    # The cached raw Event list (get_events()'s EventRequestCache
    # entry) must use a 7 day expiry, not the default 72 hours used by
    # the other /events endpoints. The years/heatmap payload built from
    # it is not itself cached and is recomputed on every request.
    from_year = 2010
    to_year = datetime.now().year
    ym = [f"{y:04}{m:02}" for y in range(from_year, to_year + 1) for m in range(1, 13)]
    params = normalize_event_params({"ym": ym, "keyword": None})
    key = service_module.cache.generate_key(params) + ":content"
    expiry = service_module.cache._expiry[key]
    remaining = expiry - datetime.now(timezone.utc).timestamp()
    assert 3600 * 24 * 6 < remaining <= 3600 * 24 * 7


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_with_fields(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups", params={"fields": "key,title"})
    assert response.status_code == 200
    groups = response.json()
    assert len(groups) > 0
    assert groups[0] == {"key": "Key", "title": "Title"}


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_with_fields_ignores_unknown_names(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups", params={"fields": "key,bogus"})
    assert response.status_code == 200
    groups = response.json()
    assert len(groups) > 0
    assert groups[0] == {"key": "Key"}


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_with_empty_fields_is_noop(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    baseline = client.get("/groups")
    response = client.get("/groups", params={"fields": ""})
    assert response.status_code == 200
    assert response.json() == baseline.json()


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_with_fields_keeps_cache_headers(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups", params={"fields": "key"})
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    assert response.headers["Cache-Control"] == "public, max-age=3600"


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.config", {
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
@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.service.cache", EventRequestCache(prefix="test_archive_group_"))
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


class FixedDatetimeNearBoundary(datetime):
    # Sunday 23:30, 30 minutes before both the daily and weekly rollover
    fixed_now = datetime(2026, 7, 12, 23, 30, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed_now


class FixedDatetimeMidWeek(datetime):
    # Wednesday 10:00, far from any daily or weekly rollover
    fixed_now = datetime(2026, 7, 8, 10, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed_now


def test_get_max_age_until_next_period_clamped_near_boundary():
    with patch("app.routes.datetime", FixedDatetimeNearBoundary):
        assert get_max_age_until_next_period(1) == 1800
        assert get_max_age_until_next_period(7) == 1800


def test_get_max_age_until_next_period_uses_default_far_from_boundary():
    with patch("app.routes.datetime", FixedDatetimeMidWeek):
        assert get_max_age_until_next_period(1) == 3600
        assert get_max_age_until_next_period(7) == 3600


def test_get_max_age_until_next_period_rejects_unsupported_days():
    with pytest.raises(ValueError):
        get_max_age_until_next_period(3)


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


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.cache", EventRequestCache(prefix="test_get_events_no_bg_"))
def test_get_events_without_background_tasks():
    events, last_modified = get_events({"ym": ["202201"], "keyword": None})

    assert isinstance(events, list)
    assert len(events) > 0


@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.service.config", {
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


@patch("app.service.config", {
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


@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest)
@patch("app.service.config", {
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


@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest)
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


@patch("app.service.config", {
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


@patch("app.service.config", {
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
    with patch("app.service.ArchiveIndexRequest",
               MockFailingPreloadArchiveIndexRequest):
        preload_archive_indexes()


def test_legacy_routes_marked_deprecated_in_openapi_schema():
    schema = client.get("/openapi.json").json()
    legacy = [
        "/events/today",
        "/events/in/{year}",
        "/events/in/{year}/{month}",
        "/events/in/{year}/{month}/{day}",
        "/events/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
        "/events/summary",
    ]
    for path in legacy:
        op = schema["paths"][path]["get"]
        assert op["deprecated"] is True
        assert op["operationId"].endswith("_legacy")

    canonical = [
        "/events", "/events/day/today", "/events/week/this", "/events/week/next",
        "/events/year/{year}", "/events/month/{year}/{month}",
        "/events/day/{year}/{month}/{day}",
        "/events/range/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
        "/summary/events", "/groups",
    ]
    for path in canonical:
        op = schema["paths"][path]["get"]
        assert not op.get("deprecated", False)


class MockConnpassEventRequestCapturingSkipCache:
    received_skip_cache = []

    def __init__(self, **kwargs):
        MockConnpassEventRequestCapturingSkipCache.received_skip_cache.append(
            kwargs.get("skip_cache"))

    def get_events(self):
        return []

    def get_last_modified(self):
        return datetime.fromtimestamp(123, timezone.utc)


@patch("app.service.events_refresh_token", None)
def test_refresh_events_requires_token_configured():
    response = client.post("/events/refresh",
                           headers={"X-Refresh-Token": "anything"})
    assert response.status_code == 503


@patch("app.service.events_refresh_token", "secret-token")
def test_refresh_events_rejects_missing_token():
    response = client.post("/events/refresh")
    assert response.status_code == 401


@patch("app.service.events_refresh_token", "secret-token")
def test_refresh_events_rejects_wrong_token():
    response = client.post("/events/refresh",
                           headers={"X-Refresh-Token": "wrong-token"})
    assert response.status_code == 401


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.events_refresh_token", "secret-token")
@patch("app.service.cache", EventRequestCache(prefix="test_refresh_success_"))
def test_refresh_events_success_returns_fresh_data_and_updates_cache():
    import app.service as service_module
    import app.routes as routes_module

    response = client.post("/events/refresh",
                           headers={"X-Refresh-Token": "secret-token"})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    events = response.json()
    assert isinstance(events, list)
    assert len(events) > 0

    days = service_module.config["recent_days"] \
        if "recent_days" in service_module.config else 90
    now = datetime.now()
    dt_from = now - timedelta(days=days)
    dt_to = now + timedelta(days=days)
    ym = routes_module.year_month_range(dt_from.year, dt_from.month,
                                        dt_to.year, dt_to.month)
    params = service_module.normalize_event_params(
        {"ym": ym, "keyword": None, "uid": None})
    cached = service_module.cache.get(params)
    assert cached is not None
    assert cached["json"] is not None


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.events_refresh_token", "secret-token")
@patch("app.service.cache", EventRequestCache(prefix="test_refresh_rate_limit_"))
def test_refresh_events_rate_limited_on_second_call():
    headers = {"X-Refresh-Token": "secret-token"}

    first = client.post("/events/refresh", headers=headers)
    assert first.status_code == 200

    second = client.post("/events/refresh", headers=headers)
    assert second.status_code == 429


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCapturingSkipCache)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.events_refresh_token", "secret-token")
@patch("app.service.cache", EventRequestCache(prefix="test_refresh_skip_cache_"))
def test_refresh_events_forces_connpass_cache_bypass():
    MockConnpassEventRequestCapturingSkipCache.received_skip_cache = []

    response = client.post("/events/refresh",
                           headers={"X-Refresh-Token": "secret-token"})
    assert response.status_code == 200
    assert len(MockConnpassEventRequestCapturingSkipCache.received_skip_cache) > 0
    assert all(MockConnpassEventRequestCapturingSkipCache.received_skip_cache)


def test_refresh_events_excluded_from_schema_and_mcp():
    schema = client.get("/openapi.json").json()
    assert "/events/refresh" not in schema["paths"]

    from app.routes import mcp
    tool_names = {t.name for t in mcp.tools}
    assert "refresh_events" not in tool_names


def test_mcp_excludes_legacy_operations():
    from app.routes import mcp

    tool_names = {t.name for t in mcp.tools}
    for legacy_id in [
        "list_events_today_legacy", "list_events_by_year_legacy",
        "list_events_by_month_legacy", "list_events_by_day_legacy",
        "list_events_by_range_legacy", "summary_events_legacy",
    ]:
        assert legacy_id not in tool_names

    for canonical_id in [
        "list_events", "list_events_today", "list_events_this_week",
        "list_events_next_week", "list_events_by_year", "list_events_by_month",
        "list_events_by_day", "list_events_by_range", "list_groups",
    ]:
        assert canonical_id in tool_names

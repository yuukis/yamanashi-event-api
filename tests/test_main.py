from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest
from app.main import app
from app.service import get_user_agent, get_groups_from_icalendar
from app.service import request_events, request_groups, get_groups_from_archives
from app.service import get_archive_urls, preload_archive_indexes
from app.service import get_events, get_groups, normalize_event_params
from app.service import find_group_source, get_archive_group_keys
from app.service import fetch_events, fetch_groups
from app.service import split_connpass_scope, partition_and_relabel_chapter_events
from app.service import get_groups_from_connpass_chapters, merged_connpass_subdomains
from app.service import merge_duplicate_groups
from app import service
from app.cache import EventRequestCache
from app.providers.archive import ArchiveException
from app.models import Event, Group
from datetime import datetime, timedelta, timezone

client = TestClient(app)


class MockConnpassEventRequest:
    requests = []
    page_requests = []

    def __init__(self, **kwargs):
        MockConnpassEventRequest.requests.append(kwargs)

    def get_events(self):
        return Event.from_json(self._fixed_json())

    def get_events_page(self, item_start, item_count, order="desc"):
        MockConnpassEventRequest.page_requests.append(
            {"item_start": item_start, "item_count": item_count, "order": order})
        # _fixed_json() is ascending; "desc" simulates connpass's native order.
        events = Event.from_json(self._fixed_json())
        if order == "desc":
            events = list(reversed(events))
        return events[item_start - 1:item_start - 1 + item_count]

    def get_total_available(self):
        return 2

    def _fixed_json(self):
        return [
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
                "lon": "",
                "source": "connpass"
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
                "lon": "",
                "source": "connpass"
            }
        ]

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
    requests = []

    def __init__(self, **kwargs):
        MockICalEventRequest.requests.append(kwargs)

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
                "lon": None,
                "source": "icalendar"
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
                "lon": None,
                "source": "archive"
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


class MockArchiveIndexRequestJagyamanashi(MockArchiveIndexRequest):
    """An archive community sharing its key with the real "jagyamanashi" connpass entry."""

    def get_events(self):
        json = [
            {
                "uid": "jagyamanashi-2015-01-01-001@yamanashi-event-archive",
                "event_id": None,
                "title": "日本Androidの会 山梨支部 第1回",
                "catch": None,
                "hash_tag": None,
                "event_url": "https://example.com/archive/jagyamanashi/2015-01-01-001",
                "started_at": "2015-01-01T14:00:00+09:00",
                "ended_at": "2015-01-01T17:00:00+09:00",
                "updated_at": "2026-06-30T00:00:00+09:00",
                "open_status": "close",
                "limit": None,
                "accepted": None,
                "waiting": None,
                "owner_name": None,
                "place": None,
                "address": None,
                "group_key": "jagyamanashi",
                "group_name": "日本Androidの会 山梨支部",
                "group_url": "https://jagyamanashi.connpass.com/",
                "description": None,
                "lat": None,
                "lon": None,
                "source": "archive"
            }
        ]
        return Event.from_json(json)

    def get_groups(self):
        json = [
            {
                "key": "jagyamanashi",
                "title": "日本Androidの会 山梨支部（アーカイブ）",
                "sub_title": None,
                "url": "https://example.com/jagyamanashi",
                "description": None,
                "owner_text": None,
                "image_url": None,
                "website_url": None,
                "x_username": None,
                "facebook_url": None,
                "member_users_count": None,
                "ical_url": None,
                "archive_source": "yamanashi-event-archive",
                "archive_url": "https://github.com/yuukis/yamanashi-event-archive"
            }
        ]
        return Group.from_json(json)


class MockConnpassGroupRequestJagyamanashi(MockConnpassGroupRequest):
    def get_groups(self):
        json = [
            {
                "id": 1,
                "key": "jagyamanashi",
                "title": "日本Androidの会 山梨支部",
                "sub_title": None,
                "url": "https://jagyamanashi.connpass.com/",
                "description": None,
                "owner_text": None,
                "image_url": None,
                "website_url": None,
                "x_username": None,
                "facebook_url": None,
                "member_users_count": 50
            }
        ]
        return Group.from_json(json)


class MockFailingPreloadArchiveIndexRequest:
    def __init__(self, **kwargs):
        self.url = kwargs.get("url")

    def preload(self):
        raise ArchiveException(500, "Failed to fetch archive index")


@pytest.fixture(autouse=True)
def mock_archive_index_request():
    MockArchiveIndexRequest.requested_urls = []
    MockArchiveIndexRequest.preloaded_urls = []
    service._archive_group_keys = None  # reset the process-lifetime memoization
    with patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequest):
        yield
    service._archive_group_keys = None


@pytest.fixture(autouse=True)
def mock_connpass_event_request_calls():
    MockConnpassEventRequest.requests = []
    MockConnpassEventRequest.page_requests = []
    yield


@pytest.fixture(autouse=True)
def mock_ical_event_request_calls():
    MockICalEventRequest.requests = []
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
    assert response.headers["Cache-Control"] == "public, no-cache"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_returns_304_when_not_modified_since():
    baseline = client.get("/events/month/2023/12")
    last_modified = baseline.headers["Last-Modified"]

    response = client.get("/events/month/2023/12",
                          headers={"If-Modified-Since": last_modified})
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["Last-Modified"] == last_modified
    assert response.headers["Cache-Control"] == "public, no-cache"


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_returns_304_when_modified_since_is_later():
    response = client.get(
        "/events/month/2023/12",
        headers={"If-Modified-Since": "Mon, 01 Jan 2035 00:00:00 GMT"})
    assert response.status_code == 304


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_events_month_returns_200_when_modified_since_is_earlier():
    response = client.get(
        "/events/month/2023/12",
        headers={"If-Modified-Since": "Thu, 01 Jan 1970 00:00:00 GMT"})
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_read_events_for_days_if_modified_since_defaults_to_none():
    # read_events_for_days() is a plain internal helper, not a route, so its
    # if_modified_since default must be a real None -- not a
    # fastapi.params.Header instance (which Header(None) would bind to here
    # since FastAPI only performs that substitution for actual routes/
    # dependencies).
    import inspect
    from app.routes import read_events_for_days

    default = inspect.signature(read_events_for_days) \
        .parameters["if_modified_since"].default
    assert default is None


def test_format_last_modified_is_locale_independent():
    import locale
    from app.routes import format_last_modified

    original = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "ja_JP.utf8")
    except locale.Error:
        pytest.skip("ja_JP.utf8 locale not available in this environment")

    try:
        dt = datetime(2026, 7, 13, 1, 2, 3, tzinfo=timezone.utc)
        assert format_last_modified(dt) == "Mon, 13 Jul 2026 01:02:03 GMT"
    finally:
        locale.setlocale(locale.LC_TIME, original)


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


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_plain_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_connpass_plain():
    # Plain group, no keyword/uid: fast path, one request, no background refetch.
    response = client.get("/groups/jagyamanashi/events")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)

    assert len(MockConnpassEventRequest.requests) == 1
    req = MockConnpassEventRequest.requests[0]
    assert req["subdomain"] == ["jagyamanashi"]
    assert "keyword" not in req

    assert MockConnpassEventRequest.page_requests == [
        {"item_start": 1, "item_count": 50, "order": "desc"}]


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_plain_filtered_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_connpass_plain_with_uid_falls_back_to_full_fetch():
    # uid filter forces the get_events() fallback, not the fast path.
    response = client.get("/groups/jagyamanashi/events", params={"uid": "UID 2"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 2"

    assert len(MockConnpassEventRequest.requests) >= 1
    for req in MockConnpassEventRequest.requests:
        assert req["subdomain"] == ["jagyamanashi"]
        assert req["keyword"] is None
    assert MockConnpassEventRequest.page_requests == []


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_plain_blank_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_connpass_plain_with_blank_filters_still_uses_fast_path():
    # Blank keyword/uid must not defeat the upstream-pagination fast path.
    response = client.get("/groups/jagyamanashi/events",
                          params={"keyword": "", "uid": "  ", "per_page": 1})
    assert response.status_code == 200

    assert MockConnpassEventRequest.page_requests == [
        {"item_start": 1, "item_count": 1, "order": "desc"}]


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_default_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_default_pagination():
    # MockConnpassEventRequest always reports 2 events available (UID 1, UID 2)
    response = client.get("/groups/jagyamanashi/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 2

    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Page"] == "1"
    assert response.headers["X-Per-Page"] == "50"
    assert response.headers["X-Total-Pages"] == "1"


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_cors_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_exposes_pagination_headers_for_cors():
    response = client.get("/groups/jagyamanashi/events",
                          headers={"Origin": "https://example.com"})
    assert response.status_code == 200

    exposed = response.headers["access-control-expose-headers"]
    exposed_headers = {h.strip() for h in exposed.split(",")}
    assert exposed_headers == {
        "X-Total-Count", "X-Page", "X-Per-Page", "X-Total-Pages"}


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_slice_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_pagination_slices_pages():
    # Default order "desc" (newest-first): page 2 of 1-per-page is UID 1.
    response = client.get("/groups/jagyamanashi/events",
                          params={"per_page": 1, "page": 2})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 1"

    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Page"] == "2"
    assert response.headers["X-Per-Page"] == "1"
    assert response.headers["X-Total-Pages"] == "2"

    assert len(MockConnpassEventRequest.requests) == 1
    assert MockConnpassEventRequest.page_requests == [
        {"item_start": 2, "item_count": 1, "order": "desc"}]


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_oob_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_pagination_out_of_range_page_is_empty():
    response = client.get("/groups/jagyamanashi/events",
                          params={"per_page": 1, "page": 99})
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Total-Pages"] == "2"


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_invalid_"))
def test_read_group_events_pagination_rejects_invalid_params():
    response = client.get("/groups/jagyamanashi/events", params={"page": 0})
    assert response.status_code == 422

    response = client.get("/groups/jagyamanashi/events", params={"per_page": 0})
    assert response.status_code == 422

    response = client.get("/groups/jagyamanashi/events", params={"per_page": 201})
    assert response.status_code == 422

    response = client.get("/groups/jagyamanashi/events", params={"order": "sideways"})
    assert response.status_code == 422


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_order_asc_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_ascending_order():
    # order=asc reverses the native descending order: page 1 is UID 1.
    response = client.get("/groups/jagyamanashi/events",
                          params={"per_page": 1, "order": "asc"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["uid"] == "UID 1"

    assert MockConnpassEventRequest.page_requests == [
        {"item_start": 1, "item_count": 1, "order": "asc"}]


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_chapter_desc_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_chapter_descending_order():
    # Chapters fall back to get_events() (always ascending); order=desc
    # must reverse that result locally.
    response = client.get("/groups/soracomug-yamanashi/events",
                          params={"order": "desc"})
    assert response.status_code == 200
    events = response.json()
    started_ats = [e["started_at"] for e in events]
    assert started_ats == sorted(started_ats, reverse=True)


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_page_fields_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_pagination_headers_kept_with_fields():
    # Default order "desc": page 1 of 1-per-page is the newest event, UID 2.
    response = client.get("/groups/jagyamanashi/events",
                          params={"per_page": 1, "fields": "uid"})
    assert response.status_code == 200
    assert response.json() == [{"uid": "UID 2"}]
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Per-Page"] == "1"


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_chapter_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
def test_read_group_events_connpass_chapter():
    # Chapter "soracomug-yamanashi" (subdomain "soracomug-tokyo", keyword
    # "山梨") falls back to get_events()'s crawl, not the fast path.
    response = client.get("/groups/soracomug-yamanashi/events")
    assert response.status_code == 200

    assert len(MockConnpassEventRequest.requests) >= 1
    for req in MockConnpassEventRequest.requests:
        assert req["subdomain"] == ["soracomug-tokyo"]
        assert req["keyword"] == "山梨"
    assert MockConnpassEventRequest.page_requests == []


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_ical_"))
@patch("app.service.IcalEventRequest", MockICalEventRequest)
def test_read_group_events_icalendar():
    # config.yaml's real icalendar entry, resolved from config alone
    response = client.get("/groups/yamanashi-wordpress-meetup/events")
    assert response.status_code == 200

    assert len(MockICalEventRequest.requests) >= 1
    for req in MockICalEventRequest.requests:
        assert req["key"] == "yamanashi-wordpress-meetup"
        assert req["url"] == \
            "https://www.meetup.com/ja-JP/Yamanashi-WordPress-Meetup/events/ical/"


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_archive_"))
@patch("app.service.split_connpass_scope", return_value=([], []))
def test_read_group_events_archive(mock_split_connpass_scope):
    # "yamanashi-web" is also a real plain subdomain; neutralize
    # scope.connpass to force the archive-only resolution path.
    response = client.get("/groups/yamanashi-web/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["group_key"] == "yamanashi-web"


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_404_"))
def test_read_group_events_not_found():
    response = client.get("/groups/no-such-group/events")
    assert response.status_code == 404


def test_find_group_source_connpass_plain():
    source = find_group_source("jagyamanashi")
    assert source == {"type": "connpass", "subdomain": "jagyamanashi",
                      "keyword": None, "chapter_entry": None}


def test_find_group_source_connpass_chapter():
    source = find_group_source("soracomug-yamanashi")
    assert source["type"] == "connpass"
    assert source["subdomain"] == "soracomug-tokyo"
    assert source["keyword"] == "山梨"


def test_find_group_source_icalendar():
    source = find_group_source("yamanashi-wordpress-meetup")
    assert source["type"] == "icalendar"
    assert source["ical_url"] == \
        "https://www.meetup.com/ja-JP/Yamanashi-WordPress-Meetup/events/ical/"


@patch("app.service.split_connpass_scope", return_value=([], []))
def test_find_group_source_archive(mock_split_connpass_scope):
    assert find_group_source("yamanashi-web") == {"type": "archive"}


def test_find_group_source_not_found():
    assert find_group_source("no-such-group") is None


@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequestJagyamanashi)
def test_find_group_source_also_archive_when_archive_key_matches_primary():
    # "jagyamanashi" is a real plain connpass entry in config.yaml.
    source = find_group_source("jagyamanashi")
    assert source["type"] == "connpass"
    assert source["subdomain"] == "jagyamanashi"
    assert source["also_archive"] is True


def test_get_archive_group_keys_is_memoized():
    first = get_archive_group_keys()
    assert first == {"yamanashi-web"}
    assert isinstance(first, frozenset)

    requests_before = len(MockArchiveIndexRequest.requested_urls)
    second = get_archive_group_keys()

    assert second is first
    # No new ArchiveIndexRequest was constructed for the memoized call.
    assert len(MockArchiveIndexRequest.requested_urls) == requests_before


@patch("app.service.cache", EventRequestCache(prefix="test_group_events_archive_merge_"))
@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequestJagyamanashi)
def test_read_group_events_merges_archive_when_key_matches_connpass():
    response = client.get("/groups/jagyamanashi/events")
    assert response.status_code == 200
    events = response.json()

    # 2 connpass events + 1 archive event sharing the "jagyamanashi" key
    assert len(events) == 3
    assert response.headers["X-Total-Count"] == "3"
    assert any(ev["uid"] == "jagyamanashi-2015-01-01-001@yamanashi-event-archive"
              for ev in events)
    assert all(ev["group_key"] == "jagyamanashi" for ev in events
              if ev["uid"].startswith("jagyamanashi-"))

    # clients can tell live connpass events apart from archived ones
    by_uid = {ev["uid"]: ev for ev in events}
    assert by_uid["UID 1"]["source"] == "connpass"
    assert by_uid["UID 2"]["source"] == "connpass"
    assert by_uid["jagyamanashi-2015-01-01-001@yamanashi-event-archive"]["source"] == "archive"

    # fast path (upstream pagination) must be disabled when merging archives
    assert MockConnpassEventRequest.page_requests == []


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_events_summary(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/events")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, no-cache"
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
@patch("app.service.cache", EventRequestCache(prefix="test_summary_304_"))
def test_read_events_summary_returns_304_when_not_modified_since(
        mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    baseline = client.get("/summary/events")
    last_modified = baseline.headers["Last-Modified"]

    response = client.get("/summary/events",
                          headers={"If-Modified-Since": last_modified})
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["Cache-Control"] == "public, no-cache"


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
    params = normalize_event_params(
        {"ym": ym, "keyword": None, "include_prefecture": False})
    key = service_module.cache.generate_key(params) + ":content"
    expiry = service_module.cache._expiry[key]
    remaining = expiry - datetime.now(timezone.utc).timestamp()
    assert 3600 * 24 * 6 < remaining <= 3600 * 24 * 7


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_groups_"))
def test_read_groups_summary(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/groups")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, no-cache"
    assert "Last-Modified" in response.headers

    data = response.json()
    assert data["from_year"] == 2010
    to_year = data["to_year"]

    by_key = {g["key"]: g for g in data["groups"]}

    # Archive mock event: 2012-05-19, group_key "yamanashi-web"
    web = by_key["yamanashi-web"]
    assert web["start_year"] == 2012
    assert web["years"][0] == {"year": 2012, "event_count": 1}
    assert web["years"][-1] == {"year": to_year, "event_count": 0}
    assert len(web["years"]) == to_year - 2012 + 1

    # A group with no events anywhere in range gets a null start_year and
    # an empty years list, not a list zero-filled back to from_year
    assert by_key["Key"]["start_year"] is None
    assert by_key["Key"]["years"] == []


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_groups_fields_"))
def test_read_groups_summary_with_fields(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/groups", params={"fields": "key,name,start_year"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["groups"]) > 0
    for group in data["groups"]:
        assert set(group.keys()) == {"key", "name", "start_year"}


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_group_"))
def test_read_group_summary(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/groups/yamanashi-web")
    assert response.status_code == 200

    data = response.json()
    assert data["key"] == "yamanashi-web"
    assert data["start_year"] == 2012
    assert data["years"][0] == {"year": 2012, "event_count": 1}


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_group_404_"))
def test_read_group_summary_not_found(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/summary/groups/no-such-group")
    assert response.status_code == 404


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequest)
@patch("app.service.IcalEventRequest", MockICalEventRequest)
@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_summary_shared_cache_"))
def test_read_groups_summary_reuses_events_summary_cache(mock_get_groups_from_icalendar):
    """/summary/groups must issue the exact same get_events() params as
    /summary/events (same ym range, same keyword=None), so once
    /summary/events has warmed the cache, /summary/groups is served from
    it instead of paying for a second full-history connpass fetch."""
    mock_get_groups_from_icalendar.return_value = []

    events_response = client.get("/summary/events")
    assert events_response.status_code == 200

    from_year = service.MIN_EVENT_YEAR
    to_year = datetime.now().year
    ym = [f"{y:04}{m:02}" for y in range(from_year, to_year + 1) for m in range(1, 13)]
    params = normalize_event_params(
        {"ym": ym, "keyword": None, "include_prefecture": False})

    # The background revalidation triggered by /summary/events must have
    # already populated this exact cache entry by the time the request
    # returns (TestClient runs BackgroundTasks synchronously).
    cached_events, _ = service.get_events_from_cache(service.cache, params)
    assert cached_events is not None

    groups_response = client.get("/summary/groups")
    assert groups_response.status_code == 200
    assert groups_response.json()["to_year"] == to_year


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
    assert response.headers["Cache-Control"] == "public, no-cache"


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [{"subdomain": "test"}],
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


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequestJagyamanashi)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [{"subdomain": "jagyamanashi"}],
        "archives": [
            {
                "url": "https://example.com/archive/index.json"
            }
        ]
    }
})
@patch("app.service.ArchiveIndexRequest", MockArchiveIndexRequestJagyamanashi)
@patch("app.service.cache", EventRequestCache(prefix="test_groups_merge_archive_"))
def test_read_groups_merges_duplicate_key_from_archive(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups")

    assert response.status_code == 200
    matching = [g for g in response.json() if g["key"] == "jagyamanashi"]
    assert len(matching) == 1

    merged = matching[0]
    # connpass's own (non-null) fields win over the archive's duplicate entry...
    assert merged["title"] == "日本Androidの会 山梨支部"
    assert merged["member_users_count"] == 50
    # ...but archive-only fields (null on the connpass entry) get backfilled.
    assert merged["archive_source"] == "yamanashi-event-archive"
    assert merged["archive_url"] == \
        "https://github.com/yuukis/yamanashi-event-archive"


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_by_key(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups/Key")
    assert response.status_code == 200
    group = response.json()
    assert isinstance(group, dict)
    assert group["key"] == "Key"
    assert group["title"] == "Title"


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_by_key_not_found(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups/no-such-group")
    assert response.status_code == 404


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_by_key_with_fields(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    response = client.get("/groups/Key", params={"fields": "key,title"})
    assert response.status_code == 200
    assert response.json() == {"key": "Key", "title": "Title"}


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
def test_read_group_by_key_returns_304_when_not_modified_since(
        mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    baseline = client.get("/groups/Key")
    last_modified = baseline.headers["Last-Modified"]

    response = client.get("/groups/Key",
                          headers={"If-Modified-Since": last_modified})
    assert response.status_code == 304
    assert response.content == b""


def test_events_refresh_min_interval_falls_back_on_invalid_env_value(monkeypatch):
    import importlib
    import app.service as service_module

    monkeypatch.setenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", "not-a-number")
    try:
        importlib.reload(service_module)
        assert service_module.events_refresh_min_interval == 60
    finally:
        monkeypatch.delenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", raising=False)
        importlib.reload(service_module)


def test_events_refresh_min_interval_falls_back_on_non_positive_env_value(monkeypatch):
    # A zero or negative interval would make the refresh-lock's cache entry
    # expire immediately (or already be expired) on write, silently
    # disabling the abuse-prevention rate limit.
    import importlib
    import app.service as service_module

    monkeypatch.setenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", "-5")
    try:
        importlib.reload(service_module)
        assert service_module.events_refresh_min_interval == 60
    finally:
        monkeypatch.delenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", raising=False)
        importlib.reload(service_module)


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


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequest)
@patch("app.service.get_groups_from_icalendar")
@patch("app.service.cache", EventRequestCache(prefix="test_get_groups_no_bg_"))
def test_get_groups_without_background_tasks(mock_get_groups_from_icalendar):
    mock_get_groups_from_icalendar.return_value = []

    groups, last_modified = get_groups({})

    assert isinstance(groups, list)
    assert len(groups) > 0


@patch("app.service.request_events")
@patch("app.service.cache", EventRequestCache(prefix="test_fetch_events_swallow_"))
def test_fetch_events_swallows_upstream_failure(mock_request_events):
    # request_events() converts provider exceptions into HTTPException, so
    # that's what fetch_events() actually needs to catch and swallow when
    # running as a background stale-while-revalidate refresh.
    mock_request_events.side_effect = HTTPException(status_code=502, detail="boom")

    fetch_events({"ym": ["202401"], "keyword": None, "uid": None})


@patch("app.service.request_groups")
@patch("app.service.cache", EventRequestCache(prefix="test_fetch_groups_swallow_"))
def test_fetch_groups_swallows_upstream_failure(mock_request_groups):
    mock_request_groups.side_effect = HTTPException(status_code=502, detail="boom")

    fetch_groups({})


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


def _make_subgroup_event(uid, title, description=None):
    return Event.from_json({
        "uid": uid,
        "event_id": 1,
        "title": title,
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
        "address": "山梨県甲府市",
        "group_key": "soracomug-tokyo",
        "group_name": "SORACOM UG",
        "group_url": "https://soracomug-tokyo.connpass.com/",
        "description": description,
        "lat": None,
        "lon": None
    })


CHAPTER_ENTRY = {
    "subdomain": "soracomug-tokyo",
    "title_keyword": "山梨",
    "key": "soracomug-yamanashi",
    "name": "SORACOM UG 山梨",
    "group_url": "https://soracom-ug.connpass.com/"
}


def test_split_connpass_scope_separates_plain_and_chapter_entries():
    config = {
        "scope": {
            "connpass": [
                {"subdomain": "jagyamanashi"},
                CHAPTER_ENTRY
            ]
        }
    }

    plain, chapters = split_connpass_scope(config)

    assert plain == ["jagyamanashi"]
    assert chapters == [CHAPTER_ENTRY]


def test_split_connpass_scope_dedupes_repeated_plain_entries():
    # A duplicate plain subdomain in config must not leak into `plain`.
    config = {
        "scope": {
            "connpass": [
                {"subdomain": "jagyamanashi"},
                {"subdomain": "coderdojokofu"},
                {"subdomain": "jagyamanashi"},
            ]
        }
    }

    plain, _ = split_connpass_scope(config)

    assert plain == ["jagyamanashi", "coderdojokofu"]


@pytest.mark.parametrize("title_keyword", [None, ""])
def test_split_connpass_scope_rejects_empty_title_keyword(title_keyword):
    config = {
        "scope": {
            "connpass": [{**CHAPTER_ENTRY, "title_keyword": title_keyword}]
        }
    }

    with pytest.raises(ValueError, match="non-empty string title_keyword"):
        split_connpass_scope(config)


def test_split_connpass_scope_rejects_subdomain_as_both_plain_and_chapter():
    config = {
        "scope": {
            "connpass": [
                {"subdomain": "soracomug-tokyo"},
                CHAPTER_ENTRY
            ]
        }
    }

    with pytest.raises(ValueError, match="both a plain entry and a chapter entry"):
        split_connpass_scope(config)


@pytest.mark.parametrize("entry", ["jagyamanashi", ["jagyamanashi"], None])
def test_split_connpass_scope_rejects_non_mapping_entry(entry):
    config = {"scope": {"connpass": [entry]}}

    with pytest.raises(ValueError, match="must be a mapping"):
        split_connpass_scope(config)


@pytest.mark.parametrize("subdomain", [None, "", 123])
def test_split_connpass_scope_rejects_missing_subdomain(subdomain):
    config = {"scope": {"connpass": [{"subdomain": subdomain}]}}

    with pytest.raises(ValueError, match="non-empty string subdomain"):
        split_connpass_scope(config)


def test_split_connpass_scope_rejects_chapter_missing_key():
    entry = {k: v for k, v in CHAPTER_ENTRY.items() if k != "key"}
    config = {"scope": {"connpass": [entry]}}

    with pytest.raises(ValueError, match="requires key and name"):
        split_connpass_scope(config)


def test_split_connpass_scope_rejects_chapter_missing_name():
    entry = {k: v for k, v in CHAPTER_ENTRY.items() if k != "name"}
    config = {"scope": {"connpass": [entry]}}

    with pytest.raises(ValueError, match="requires key and name"):
        split_connpass_scope(config)


def test_split_connpass_scope_title_keyword_error_includes_real_subdomain():
    config = {
        "scope": {
            "connpass": [{"subdomain": "soracomug-tokyo", "title_keyword": ""}]
        }
    }

    with pytest.raises(ValueError, match="subdomain 'soracomug-tokyo'"):
        split_connpass_scope(config)


def test_merged_connpass_subdomains_dedupes_and_preserves_order():
    chapters = [
        {**CHAPTER_ENTRY, "key": "soracomug-yamanashi"},
        {**CHAPTER_ENTRY, "key": "soracomug-tokyo-chapter",
         "subdomain": "soracomug-tokyo"},  # same real subdomain, another chapter
    ]

    merged = merged_connpass_subdomains(
        ["jagyamanashi", "soracomug-tokyo"], chapters)

    assert merged == ["jagyamanashi", "soracomug-tokyo"]


def _make_group(key, **overrides):
    fields = {
        "id": None, "key": key, "title": None, "sub_title": None, "url": None,
        "description": None, "owner_text": None, "image_url": None,
        "website_url": None, "x_username": None, "facebook_url": None,
        "member_users_count": None, "ical_url": None,
        "archive_source": None, "archive_url": None,
    }
    fields.update(overrides)
    return Group(**fields)


def test_merge_duplicate_groups_backfills_null_fields_without_overwriting():
    base = _make_group("k", id=1, title="Title A", url="https://a",
                       member_users_count=10)
    dup = _make_group("k", id=2, title="Title B", sub_title="Sub B",
                      description="Desc B", archive_source="src",
                      archive_url="https://archive")
    other = _make_group("other", title="Other")

    merged = merge_duplicate_groups([base, dup, other])

    assert [g.key for g in merged] == ["k", "other"]
    result = merged[0]
    # base's own already-set fields are kept, not overwritten
    assert result.id == 1
    assert result.title == "Title A"
    assert result.url == "https://a"
    # base's null fields are backfilled from the duplicate
    assert result.sub_title == "Sub B"
    assert result.description == "Desc B"
    assert result.archive_source == "src"
    assert result.archive_url == "https://archive"


def test_merge_duplicate_groups_is_noop_for_unique_keys():
    groups = [_make_group("a", title="A"), _make_group("b", title="B")]
    assert merge_duplicate_groups(groups) == groups


def test_partition_and_relabel_chapter_events_filters_by_title_only():
    events = [
        _make_subgroup_event("UID Yamanashi 1", "SORACOM UG 山梨 #1"),
        _make_subgroup_event("UID Tokyo 1", "SORACOM UG Tokyo #1",
                             description="山梨から来たゲストを迎えます"),
        _make_subgroup_event("UID Other 1", "山梨IT同好会もくもく会"),
    ]
    events[2].group_key = "yamanashi-it"  # unrelated plain-subdomain group

    matched = partition_and_relabel_chapter_events(events, [CHAPTER_ENTRY])

    assert len(matched) == 2
    assert matched[0].uid == "UID Yamanashi 1"
    assert matched[0].group_key == "soracomug-yamanashi"
    assert matched[0].group_name == "SORACOM UG 山梨"
    assert matched[0].group_url == "https://soracom-ug.connpass.com/"
    # Events from groups outside the configured chapters pass through untouched
    assert matched[1].uid == "UID Other 1"
    assert matched[1].group_key == "yamanashi-it"


def test_get_groups_from_connpass_chapters_without_real_group():
    groups = get_groups_from_connpass_chapters([CHAPTER_ENTRY], {})

    assert len(groups) == 1
    assert groups[0].key == "soracomug-yamanashi"
    assert groups[0].title == "SORACOM UG 山梨"
    assert groups[0].url == "https://soracom-ug.connpass.com/"
    assert groups[0].image_url is None
    assert groups[0].member_users_count is None


def test_get_groups_from_connpass_chapters_inherits_unset_fields():
    real_group = Group.from_json({
        "id": 999,
        "key": "soracomug-tokyo",
        "title": "SORACOM UG",
        "url": "https://soracomug-tokyo.connpass.com/",
        "image_url": "https://example.com/real.png",
        "sub_title": "IoT platform community",
        "member_users_count": 1000
    })

    groups = get_groups_from_connpass_chapters(
        [CHAPTER_ENTRY], {"soracomug-tokyo": real_group})

    assert len(groups) == 1
    # Explicitly configured fields still win over the real group's values
    assert groups[0].key == "soracomug-yamanashi"
    assert groups[0].title == "SORACOM UG 山梨"
    assert groups[0].url == "https://soracom-ug.connpass.com/"
    # Fields with no config equivalent (or left unset) fall back to the
    # real group's values instead of staying null
    assert groups[0].image_url == "https://example.com/real.png"
    assert groups[0].sub_title == "IoT platform community"
    assert groups[0].member_users_count is None
    # id belongs to the shared group; two chapters carved out of the same
    # shared group must not both report its id as their own
    assert groups[0].id is None


class MockConnpassEventRequestSubgroup:
    def __init__(self, **kwargs):
        pass

    def get_events(self):
        return [
            _make_subgroup_event("UID Yamanashi 1", "SORACOM UG 山梨 #1"),
            _make_subgroup_event("UID Tokyo 1", "SORACOM UG Tokyo #1",
                                 description="山梨から来たゲストを迎えます"),
        ]

    def get_last_modified(self):
        return datetime.fromtimestamp(456, timezone.utc)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestSubgroup)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [CHAPTER_ENTRY]
    }
})
def test_request_events_from_connpass_chapters():
    events, last_modified = request_events({})

    assert len(events) == 1
    assert events[0].uid == "UID Yamanashi 1"
    assert events[0].group_key == "soracomug-yamanashi"
    assert events[0].group_name == "SORACOM UG 山梨"
    assert last_modified == datetime.fromtimestamp(456, timezone.utc)


class MockConnpassEventRequestCapturingKwargs:
    instances = []

    def __init__(self, **kwargs):
        MockConnpassEventRequestCapturingKwargs.instances.append(kwargs)

    def get_events(self):
        return [
            _make_subgroup_event("UID Yamanashi 1", "SORACOM UG 山梨 #1"),
            _make_subgroup_event("UID Tokyo 1", "SORACOM UG Tokyo #1",
                                 description="山梨から来たゲストを迎えます"),
        ]

    def get_last_modified(self):
        return datetime.fromtimestamp(456, timezone.utc)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCapturingKwargs)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [CHAPTER_ENTRY]
    }
})
def test_request_events_chapter_query_passes_title_keyword_upstream():
    MockConnpassEventRequestCapturingKwargs.instances = []

    events, _ = request_events({})

    # title_keyword is sent to connpass as a narrowing `keyword` filter.
    assert len(MockConnpassEventRequestCapturingKwargs.instances) == 1
    call = MockConnpassEventRequestCapturingKwargs.instances[0]
    assert call["subdomain"] == ["soracomug-tokyo"]
    assert call["keyword"] == ["山梨"]

    # Exact title re-check must still drop the Tokyo event whose
    # *description* happens to mention 山梨.
    assert len(events) == 1
    assert events[0].uid == "UID Yamanashi 1"
    assert events[0].group_key == "soracomug-yamanashi"


class MockConnpassEventRequestCountingCalls:
    instances = []

    def __init__(self, **kwargs):
        MockConnpassEventRequestCountingCalls.instances.append(kwargs)

    def get_events(self):
        return []

    def get_last_modified(self):
        return datetime.fromtimestamp(456, timezone.utc)


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "prefecture": ["山梨県"],
        "connpass": [{"subdomain": "jagyamanashi"}]
    }
})
def test_request_events_includes_prefecture_query_by_default():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({})

    # /events/* (the default) still wants unregistered/one-off events
    # found only through the prefecture-wide search.
    prefecture_calls = [c for c in MockConnpassEventRequestCountingCalls.instances
                        if c.get("prefecture")]
    assert len(prefecture_calls) == 1
    assert prefecture_calls[0]["prefecture"] == ["山梨県"]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "prefecture": ["山梨県"],
        "connpass": [{"subdomain": "jagyamanashi"}]
    }
})
def test_request_events_excludes_prefecture_query_when_opted_out():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({"include_prefecture": False})

    # get_full_history() (backing /summary/*) opts out: an event found
    # only through the prefecture-wide search can never be attributed to
    # a known group, so fetching it would be pure wasted connpass load.
    prefecture_calls = [c for c in MockConnpassEventRequestCountingCalls.instances
                        if c.get("prefecture")]
    assert prefecture_calls == []
    assert len(MockConnpassEventRequestCountingCalls.instances) == 1
    assert MockConnpassEventRequestCountingCalls.instances[0]["subdomain"] == \
        ["jagyamanashi"]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [{"subdomain": "jagyamanashi"}, CHAPTER_ENTRY]
    }
})
def test_request_events_fetches_chapters_separately_from_plain_subdomains():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({})

    # Plain subdomains and chapters must NOT share a query.
    assert len(MockConnpassEventRequestCountingCalls.instances) == 2

    by_subdomain = {tuple(c["subdomain"]): c
                    for c in MockConnpassEventRequestCountingCalls.instances}
    assert set(by_subdomain.keys()) == {("jagyamanashi",), ("soracomug-tokyo",)}

    assert by_subdomain[("jagyamanashi",)].get("keyword") is None
    assert by_subdomain[("soracomug-tokyo",)]["keyword"] == ["山梨"]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [{"subdomain": "jagyamanashi"}, {"subdomain": "jagyamanashi"}]
    }
})
def test_request_events_plain_query_dedupes_repeated_subdomain():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({})

    # A misconfigured duplicate plain entry must not reach the connpass
    # request -- it would shift the query params/cache key for no reason.
    assert len(MockConnpassEventRequestCountingCalls.instances) == 1
    assert MockConnpassEventRequestCountingCalls.instances[0]["subdomain"] == \
        ["jagyamanashi"]


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        # Two chapters carved out of the same shared subdomain
        "connpass": [
            CHAPTER_ENTRY,
            {**CHAPTER_ENTRY, "key": "soracomug-tokyo-chapter",
             "name": "SORACOM UG Tokyo", "title_keyword": "Tokyo"}
        ]
    }
})
def test_request_events_dedupes_repeated_chapter_subdomain():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({})

    # Still a single request for the shared subdomain, with both chapters'
    # title_keyword sent together as connpass's OR-matched keyword filter.
    assert len(MockConnpassEventRequestCountingCalls.instances) == 1
    call = MockConnpassEventRequestCountingCalls.instances[0]
    assert call["subdomain"] == ["soracomug-tokyo"]
    assert set(call["keyword"]) == {"山梨", "Tokyo"}


@patch("app.service.ConnpassEventRequest", MockConnpassEventRequestCountingCalls)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        # Two chapters sharing a subdomain AND (accidentally) the same
        # title_keyword
        "connpass": [
            CHAPTER_ENTRY,
            {**CHAPTER_ENTRY, "key": "soracomug-yamanashi-2"}
        ]
    }
})
def test_request_events_dedupes_repeated_chapter_keyword():
    MockConnpassEventRequestCountingCalls.instances = []

    request_events({})

    # A misconfigured duplicate title_keyword must not reach the connpass
    # request -- it would shift the query params/cache key for no reason.
    assert len(MockConnpassEventRequestCountingCalls.instances) == 1
    assert MockConnpassEventRequestCountingCalls.instances[0]["keyword"] == ["山梨"]


class MockConnpassGroupRequestForChapters:
    def __init__(self, **kwargs):
        pass

    def get_groups(self):
        return Group.from_json([{
            "id": 999,
            "key": "soracomug-tokyo",
            "title": "SORACOM UG",
            "url": "https://soracomug-tokyo.connpass.com/",
            "image_url": "https://example.com/real.png",
            "member_users_count": 1000
        }])

    def get_last_modified(self):
        return datetime.fromtimestamp(789, timezone.utc)


@patch("app.service.ConnpassGroupRequest", MockConnpassGroupRequestForChapters)
@patch("app.service.config", {
    "metadata": {"version": "1.0.0"},
    "scope": {
        "connpass": [CHAPTER_ENTRY]
    }
})
def test_request_groups_from_connpass_chapters():
    groups, last_modified = request_groups({})

    # The shared group itself must not leak into /groups, only the chapter
    assert len(groups) == 1
    assert groups[0].key == "soracomug-yamanashi"
    assert groups[0].title == "SORACOM UG 山梨"
    # group_url was configured explicitly, so it wins over the real group's
    assert groups[0].url == "https://soracom-ug.connpass.com/"
    # image_url wasn't configured, so it's inherited from the real group
    assert groups[0].image_url == "https://example.com/real.png"
    assert groups[0].member_users_count is None
    # id belongs to the shared group, not this chapter
    assert groups[0].id is None
    assert last_modified == datetime.fromtimestamp(789, timezone.utc)


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

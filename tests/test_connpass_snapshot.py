import json
import os
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from app import service
from app.providers.connpass import ConnpassException
from app.providers.connpass_snapshot import ConnpassSnapshot
from app.providers.connpass_snapshot import ConnpassSnapshotEventRequest
from app.providers.connpass_snapshot import ConnpassSnapshotGroupRequest
from app.providers.connpass_snapshot import PREFECTURE_POOL, subdomain_pool_name


def raw_event(event_id, started_at, subdomain="group-a", address="山梨県甲府市",
              title=None):
    return {
        "id": event_id,
        "title": title or f"Event {event_id}",
        "catch": "",
        "hash_tag": "",
        "image_url": None,
        "url": f"https://connpass.com/event/{event_id}/",
        "started_at": started_at,
        "ended_at": started_at,
        "updated_at": "2026-01-01T00:00:00+09:00",
        "open_status": "open",
        "limit": 10,
        "accepted": 1,
        "waiting": 0,
        "owner_display_name": "owner",
        "place": "place",
        "address": address,
        "description": "",
        "lat": None,
        "lon": None,
        "group": None if subdomain is None else {
            "subdomain": subdomain, "title": subdomain,
            "url": f"https://{subdomain}.connpass.com/"},
    }


def pool(*events, changed_at="2026-11-01T00:00:00+00:00"):
    return {"events": {str(e["id"]): e for e in events},
            "changed_at": changed_at}


def write_snapshot(tmp_path, data):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def snapshot(tmp_path):
    path = write_snapshot(tmp_path, {
        "pools": {
            PREFECTURE_POOL: pool(
                raw_event(1, "2026-10-05T19:00:00+09:00", subdomain="other"),
                raw_event(2, "2026-11-05T19:00:00+09:00", subdomain=None,
                          address="東京都千代田区"),
                changed_at="2026-11-02T00:00:00+00:00"),
            subdomain_pool_name(["group-a", "group-b"]): pool(
                raw_event(10, "2026-10-01T19:00:00+09:00"),
                raw_event(11, "2026-11-01T19:00:00+09:00", subdomain="group-b"),
                raw_event(12, "2026-11-20T19:00:00+09:00")),
            subdomain_pool_name(["shared"], ["山梨"]): pool(
                raw_event(20, "2026-11-03T19:00:00+09:00", subdomain="shared",
                          title="Shared 山梨"),
                changed_at="2026-11-03T00:00:00+00:00"),
        },
        "groups": {"items": [
            {"id": 1, "subdomain": "group-a", "title": "A", "sub_title": "",
             "url": "", "description": "", "owner_text": "", "image_url": None,
             "website_url": None, "twitter_username": None,
             "facebook_url": None, "member_users_count": 3},
            {"id": 2, "subdomain": "group-b", "title": "B", "sub_title": "",
             "url": "", "description": "", "owner_text": "", "image_url": None,
             "website_url": None, "twitter_username": None,
             "facebook_url": None, "member_users_count": 4},
        ], "changed_at": "2026-10-01T00:00:00+00:00"},
    })
    return ConnpassSnapshot(path)


def ids(events):
    return [e.event_id for e in events]


def test_prefecture_query_filters_by_address(snapshot):
    r = ConnpassSnapshotEventRequest(snapshot, prefecture=["山梨県"])
    assert ids(r.get_events()) == [1]
    assert r.get_last_modified() == datetime(2026, 11, 2, tzinfo=timezone.utc)


def test_subdomain_query_spans_pools_and_filters_groups(snapshot):
    r = ConnpassSnapshotEventRequest(snapshot, subdomain=["group-a", "shared"])
    # newest first, like connpass's order=2
    assert ids(r.get_events()) == [12, 20, 10]
    assert r.get_last_modified() == datetime(2026, 11, 3, tzinfo=timezone.utc)


def test_ym_and_ymd_filters(snapshot):
    r = ConnpassSnapshotEventRequest(snapshot, subdomain=["group-a", "group-b"],
                                     ym=["202610"], ymd=["20261120"])
    assert ids(r.get_events()) == [12, 10]


def test_get_events_page_and_total(snapshot):
    r = ConnpassSnapshotEventRequest(snapshot, subdomain=["group-a", "group-b"])
    assert ids(r.get_events_page(1, 2)) == [12, 11]
    assert r.get_total_available() == 3
    assert ids(r.get_events_page(1, 2, order="asc")) == [10, 11]


def test_accepts_live_connection_kwargs(snapshot):
    r = ConnpassSnapshotEventRequest(snapshot, subdomain=["group-a"],
                                     cache=object(), api_key="k",
                                     user_agent="ua", cache_ttl=1,
                                     skip_cache=True, keyword=["x"])
    assert ids(r.get_events()) == [12, 10]


def test_group_request(snapshot):
    groups = ConnpassSnapshotGroupRequest(snapshot, subdomain=["group-b"]).get_groups()
    assert [g.key for g in groups] == ["group-b"]
    all_groups = ConnpassSnapshotGroupRequest(snapshot).get_groups()
    assert [g.key for g in all_groups] == ["group-a", "group-b"]


def test_missing_snapshot_raises_503(tmp_path):
    snapshot = ConnpassSnapshot(str(tmp_path / "missing.json"))
    with pytest.raises(ConnpassException) as e:
        snapshot.data()
    assert e.value.status_code == 503


def test_reloads_changed_file_and_keeps_last_good(tmp_path):
    path = write_snapshot(tmp_path, {"pools": {
        PREFECTURE_POOL: pool(raw_event(1, "2026-11-01T00:00:00+09:00"))}})
    snapshot = ConnpassSnapshot(path)
    snapshot.FILE_CHECK_SECONDS = 0
    assert len(snapshot.pool(PREFECTURE_POOL)[0]) == 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"pools": {PREFECTURE_POOL: pool(
            raw_event(1, "2026-11-01T00:00:00+09:00"),
            raw_event(2, "2026-11-02T00:00:00+09:00"))}}, f)
    os.utime(path, (1, 1))
    assert len(snapshot.pool(PREFECTURE_POOL)[0]) == 2

    os.remove(path)
    assert len(snapshot.pool(PREFECTURE_POOL)[0]) == 2


def test_service_uses_snapshot_when_configured(snapshot):
    with patch("app.service.connpass_snapshot", snapshot), \
            patch("app.service.ConnpassEventRequest") as live:
        r = service.new_connpass_event_request(subdomain=["group-a"],
                                               cache=service.cache)
        assert isinstance(r, ConnpassSnapshotEventRequest)
        live.assert_not_called()


def test_service_uses_live_requests_without_snapshot():
    with patch("app.service.connpass_snapshot", None), \
            patch("app.service.ConnpassEventRequest") as live:
        service.new_connpass_event_request(subdomain=["group-a"])
        live.assert_called_once_with(subdomain=["group-a"])


def test_connpass_event_queries_match_snapshot_pools():
    config = {"scope": {
        "prefecture": ["山梨県"],
        "connpass": [
            {"subdomain": "group-a"},
            {"subdomain": "group-b"},
            {"subdomain": "shared", "title_keyword": "山梨",
             "key": "shared-yamanashi", "name": "Shared 山梨"},
        ],
    }}
    assert service.connpass_event_queries(config) == [
        {"pool": PREFECTURE_POOL, "params": {"keyword_or": "山梨県"}},
        {"pool": "subdomain:group-a,group-b",
         "params": {"subdomain": "group-a,group-b"}},
        {"pool": "subdomain:shared|keyword:山梨",
         "params": {"subdomain": "shared", "keyword": "山梨"}},
    ]
    assert service.connpass_group_subdomains(config) == \
        ["group-a", "group-b", "shared"]

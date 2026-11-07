import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from app import sync
from app.providers.connpass import ConnpassException
from app.providers.connpass_snapshot import ConnpassSnapshot
from app.providers.connpass_snapshot import ConnpassSnapshotEventRequest
from tests.test_connpass_snapshot import raw_event

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=JST)

CONFIG = {
    "scope": {"connpass": [{"subdomain": "group-a"}]},
    "connpass_sync": {"daily_request_limit": 90, "interval_minutes": 120},
}
QUERY = {"pool": "subdomain:group-a", "params": {"subdomain": "group-a"}}


class FakeClock:
    def __init__(self, dt=NOW):
        self.t = dt.timestamp()
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class FakeConnpass:
    """Serves `events` like connpass's events/ endpoint (ym, start/count,
    newest first) and counts requests through the real SyncState."""

    def __init__(self, state, events, groups=()):
        self.state = state
        self.events = events
        self.groups = list(groups)
        self.calls = []
        self.fail_with = None

    def get(self, endpoint, params):
        self.state.acquire_request()
        self.calls.append((endpoint, params))
        if self.fail_with is not None:
            raise self.fail_with
        items = self.groups if endpoint == "groups/" else self.events
        if "ym" in params:
            months = params["ym"].split(",")
            items = [e for e in items if sync.event_month(e) in months]
        items = sorted(items, key=lambda e: e.get("started_at", ""),
                       reverse=True)
        start, count = params["start"], params["count"]
        page = items[start - 1:start - 1 + count]
        key = "groups" if endpoint == "groups/" else "events"
        return {key: page, "results_returned": len(page),
                "results_available": len(items)}


def make_state(tmp_path, clock=None, limit=90):
    clock = clock or FakeClock()
    return sync.SyncState(str(tmp_path / "state.json"), limit, 13,
                          clock=clock, sleep=clock.sleep)


def test_budget_paces_requests_and_persists(tmp_path):
    clock = FakeClock()
    state = make_state(tmp_path, clock, limit=2)
    state.acquire_request()
    state.acquire_request()
    assert clock.sleeps == [13]
    with pytest.raises(sync.BudgetExhausted):
        state.acquire_request()

    reloaded = make_state(tmp_path, clock, limit=2)
    assert reloaded.remaining_requests() == 0

    clock.t += 3600 * 24  # next JST day
    assert reloaded.remaining_requests() == 2


def test_recent_months_window():
    assert sync.recent_months(NOW, 1, 2) == ["202610", "202611", "202612", "202701"]


def test_sync_recent_replaces_window_only(tmp_path):
    state = make_state(tmp_path)
    upstream = [raw_event(2, "2026-11-10T19:00:00+09:00"),
                raw_event(3, "2026-12-01T19:00:00+09:00")]
    client = FakeConnpass(state, upstream)
    snapshot = sync.load_snapshot(str(tmp_path / "snap.json"))
    old = raw_event(0, "2025-01-01T19:00:00+09:00")
    deleted = raw_event(1, "2026-11-05T19:00:00+09:00")
    sync.get_pool(snapshot, QUERY["pool"])["events"] = {"0": old, "1": deleted}

    sync.sync_recent(client, snapshot, QUERY, ["202611", "202612"],
                     NOW.astimezone(timezone.utc))

    pool = snapshot["pools"][QUERY["pool"]]
    assert sorted(pool["events"]) == ["0", "2", "3"]
    assert pool["changed_at"] is not None
    assert client.calls[0][1]["ym"] == "202611,202612"


def test_sync_recent_keeps_changed_at_when_unchanged(tmp_path):
    state = make_state(tmp_path)
    upstream = [raw_event(2, "2026-11-10T19:00:00+09:00")]
    client = FakeConnpass(state, upstream)
    snapshot = sync.load_snapshot(str(tmp_path / "snap.json"))
    pool = sync.get_pool(snapshot, QUERY["pool"])
    pool["events"] = {"2": upstream[0]}
    pool["changed_at"] = "2026-01-01T00:00:00+00:00"

    sync.sync_recent(client, snapshot, QUERY, ["202611"], NOW)
    assert pool["changed_at"] == "2026-01-01T00:00:00+00:00"


def test_backfill_allowance_reserves_remaining_cycles(tmp_path):
    state = make_state(tmp_path)
    # 12:00 JST with 2h cycles -> 6 cycles left today, 2 requests each
    assert sync.backfill_allowance(state, 1, 7200, NOW) == 90 - 6 * 2


def test_backfill_resumes_and_prunes(tmp_path):
    state = make_state(tmp_path)
    upstream = [raw_event(i, f"2020-01-{i % 28 + 1:02}T19:00:00+09:00")
                for i in range(1, 151)]
    client = FakeConnpass(state, upstream)
    snapshot = sync.load_snapshot(str(tmp_path / "snap.json"))
    sync.get_pool(snapshot, QUERY["pool"])["events"] = {
        "999": raw_event(999, "2019-01-01T19:00:00+09:00")}
    save = MagicMock()

    used = sync.backfill(client, snapshot, [QUERY], 1, 30, NOW, save)
    assert used == 1
    assert snapshot["backfill"]["start"] == 101
    assert len(snapshot["pools"][QUERY["pool"]]["events"]) == 101

    used = sync.backfill(client, snapshot, [QUERY], 5, 30, NOW, save)
    assert used == 1  # second page finishes the only pool
    pool = snapshot["pools"][QUERY["pool"]]
    assert snapshot["backfill"] is None
    assert pool["full_synced_at"] is not None
    assert "999" not in pool["events"]
    assert len(pool["events"]) == 150

    # Nothing is due again until full_resync_days pass.
    assert sync.backfill(client, snapshot, [QUERY], 5, 30, NOW, save) == 0


def test_backfill_skips_pruning_when_counts_disagree(tmp_path):
    snapshot = {"pools": {}}
    pool = sync.get_pool(snapshot, QUERY["pool"])
    pool["events"] = {"1": raw_event(1, "2020-01-01T00:00:00+09:00"),
                      "2": raw_event(2, "2020-01-02T00:00:00+09:00")}
    job = {"pool": QUERY["pool"], "seen": ["1"],
           "started_at": sync.iso(NOW)}
    assert sync.finish_backfill(pool, job, {"results_available": 2}) is False
    assert sorted(pool["events"]) == ["1", "2"]


def run(tmp_path, client, state):
    path = str(tmp_path / "snap.json")
    result = sync.run_cycle(path, CONFIG, client, state,
                            now=NOW.astimezone(timezone.utc))
    return path, result


def test_run_cycle_writes_snapshot_the_api_can_read(tmp_path):
    state = make_state(tmp_path)
    groups = [{"id": 1, "subdomain": "group-a", "title": "A", "sub_title": "",
               "url": "", "description": "", "owner_text": "",
               "image_url": None, "website_url": None,
               "twitter_username": None, "facebook_url": None,
               "member_users_count": 1}]
    upstream = [raw_event(1, "2026-11-10T19:00:00+09:00"),
                raw_event(2, "2015-05-01T19:00:00+09:00")]
    client = FakeConnpass(state, upstream, groups)

    path, result = run(tmp_path, client, state)
    assert result["stopped"] is None
    assert result["groups"] == 1
    assert result["backfill_requests"] == 1

    r = ConnpassSnapshotEventRequest(ConnpassSnapshot(path),
                                     subdomain=["group-a"])
    assert sorted(e.event_id for e in r.get_events()) == [1, 2]

    # Groups aren't re-fetched within a day.
    client.calls.clear()
    path, result = run(tmp_path, client, state)
    assert [c[0] for c in client.calls] == ["events/"]


def test_run_cycle_stops_on_429(tmp_path):
    state = make_state(tmp_path)
    client = FakeConnpass(state, [])
    client.fail_with = ConnpassException(429, "Too Many Requests")
    path, result = run(tmp_path, client, state)
    assert result["stopped"] == "rate limited by connpass (429)"
    assert len(client.calls) == 1


def test_run_cycle_stops_when_budget_exhausted(tmp_path):
    state = make_state(tmp_path, limit=0)
    client = FakeConnpass(state, [])
    path, result = run(tmp_path, client, state)
    assert result["stopped"] == "daily request budget exhausted"
    assert client.calls == []


def test_main_requires_local_snapshot_path():
    with patch("app.service.connpass_snapshot_location", None):
        assert sync.main([]) == 2
    with patch("app.service.connpass_snapshot_location", "https://x/s.json"):
        assert sync.main([]) == 2


def test_written_files_are_json(tmp_path):
    path = str(tmp_path / "out.json")
    sync.write_json_atomic(path, {"a": "山梨"})
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {"a": "山梨"}

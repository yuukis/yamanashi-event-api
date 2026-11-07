"""connpass -> snapshot sync job.

connpass allows only 1 request / 12s and 100 requests / day per API key,
so the API doesn't query it per request when CONNPASS_SNAPSHOT is set (see
service.py). This job is then the only connpass client: every cycle it
re-fetches a recent window of each query in connpass_event_queries(),
refreshes groups once a day, and spends whatever the day's budget can
spare on backfilling (and periodically re-checking) the full history.
Everything goes into the snapshot file that ConnpassSnapshot reads.

    python -m app.sync          # run one cycle
    python -m app.sync --loop   # keep running, one cycle per interval
"""
import argparse
import fcntl
import json
import os
import re
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from .providers.connpass import ConnpassException
from .providers.connpass_snapshot import PREFECTURE_POOL
from . import service

JST = timezone(timedelta(hours=9))
PAGE_SIZE = 100
GROUPS_SYNC_SECONDS = 3600 * 24
REQUEST_TIMEOUT = 30

DEFAULT_SETTINGS = {
    "interval_minutes": 120,
    # connpass allows 100 / day; the rest is headroom for manual runs.
    "daily_request_limit": 90,
    # connpass allows 1 request / 12s; one more second absorbs clock jitter.
    "request_interval_seconds": 13,
    "recent_months_before": 1,
    "recent_months_after": 6,
    "full_resync_days": 30,
}


class BudgetExhausted(Exception):
    pass


def sync_settings(config) -> dict:
    return {**DEFAULT_SETTINGS, **(config.get("connpass_sync") or {})}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


class SyncState:
    """Request budget and cycle bookkeeping, persisted next to the
    snapshot so restarts can't reset the day's request count. Saved
    *before* each request: a request that fails still counts upstream."""

    def __init__(self, path, daily_limit, interval_seconds,
                 clock=time.time, sleep=time.sleep):
        self.path = path
        self.daily_limit = daily_limit
        self.interval_seconds = interval_seconds
        self.clock = clock
        self.sleep = sleep
        self.state = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.state = json.load(f)

    def today(self) -> str:
        return datetime.fromtimestamp(self.clock(), JST).strftime("%Y-%m-%d")

    def requests_used(self) -> int:
        if self.state.get("date") != self.today():
            return 0
        return self.state.get("count", 0)

    def remaining_requests(self) -> int:
        return max(0, self.daily_limit - self.requests_used())

    def acquire_request(self):
        if self.remaining_requests() <= 0:
            raise BudgetExhausted()
        wait = (self.state.get("last_request_at", 0)
                + self.interval_seconds - self.clock())
        if wait > 0:
            self.sleep(wait)
        # Re-read the date after sleeping, in case midnight passed.
        self.state["count"] = self.requests_used() + 1
        self.state["date"] = self.today()
        self.state["last_request_at"] = self.clock()
        self.save()

    def seconds_until_next_cycle(self, interval_seconds) -> float:
        last = self.state.get("last_cycle_at", 0)
        return max(0.0, last + interval_seconds - self.clock())

    def mark_cycle_started(self):
        self.state["last_cycle_at"] = self.clock()
        self.save()

    def save(self):
        write_json_atomic(self.path, self.state)


class ConnpassClient:
    BASE_URL = "https://connpass.com/api/v2/"

    def __init__(self, state: SyncState, api_key=None, user_agent=None):
        self.state = state
        self.api_key = api_key
        self.user_agent = user_agent

    def get(self, endpoint, params) -> dict:
        self.state.acquire_request()

        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent
        if self.api_key is not None:
            headers["X-API-Key"] = self.api_key

        url = self.BASE_URL + endpoint
        print({"params": params, "url": url,
               "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               "requests_used": self.state.requests_used()})
        response = requests.get(url, headers=headers, params=params,
                                timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            title = re.search(r'<title>(.+?)</title>', response.text)
            message = title.group(1) if title else response.text
            raise ConnpassException(response.status_code, message)

        return response.json()


def write_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_snapshot(path) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"schema_version": "1.0", "pools": {}, "groups": None,
            "backfill": None}


def save_snapshot(path, snapshot, now: datetime):
    snapshot["generated_at"] = iso(now)
    write_json_atomic(path, snapshot)


def get_pool(snapshot, name) -> dict:
    return snapshot["pools"].setdefault(name, {
        "events": {},
        "changed_at": None,
        "recent_synced_at": None,
        "full_synced_at": None,
    })


def recent_months(now: datetime, before: int, after: int) -> list:
    now = now.astimezone(JST)
    index = now.year * 12 + now.month - 1
    return [f"{i // 12:04}{i % 12 + 1:02}"
            for i in range(index - before, index + after + 1)]


def event_month(item) -> str:
    return item["started_at"][:7].replace("-", "")


def fetch_all_pages(client, endpoint, params, key) -> list:
    items = []
    start = 1
    while True:
        json_data = client.get(endpoint, {**params, "count": PAGE_SIZE,
                                          "order": 2, "start": start})
        items += json_data[key]
        if json_data["results_returned"] < PAGE_SIZE:
            return items
        start += PAGE_SIZE


def sync_recent(client, snapshot, query, months, now: datetime):
    """Re-fetch the recent window and treat it as authoritative: events
    in those months that connpass no longer returns (deleted, cancelled
    out of the group, moved to another month) are dropped."""
    items = fetch_all_pages(client, "events/",
                            {**query["params"], "ym": ",".join(months)},
                            "events")

    pool = get_pool(snapshot, query["pool"])
    events = pool["events"]
    before = dict(events)
    for event_id in [k for k, v in events.items() if event_month(v) in months]:
        del events[event_id]
    for item in items:
        events[str(item["id"])] = item

    if events != before:
        pool["changed_at"] = iso(now)
    pool["recent_synced_at"] = iso(now)
    return len(items)


def groups_due(snapshot, now: datetime) -> bool:
    groups = snapshot.get("groups") or {}
    synced_at = parse_iso(groups.get("synced_at"))
    return synced_at is None or \
        (now - synced_at).total_seconds() >= GROUPS_SYNC_SECONDS


def sync_groups(client, snapshot, subdomains, now: datetime):
    # A list, like ConnpassGroupRequest sends it (repeated subdomain=).
    items = fetch_all_pages(client, "groups/",
                            {"subdomain": subdomains}, "groups")
    groups = snapshot.get("groups") or {"items": [], "changed_at": None}
    if groups["items"] != items:
        groups["items"] = items
        groups["changed_at"] = iso(now)
    groups["synced_at"] = iso(now)
    snapshot["groups"] = groups
    return len(items)


def backfill_allowance(state: SyncState, query_count, interval_seconds,
                       now: datetime) -> int:
    """Requests backfill may use now while still leaving enough of today's
    budget for every remaining recent-window cycle (one request per query,
    plus one for groups or a second page)."""
    now = now.astimezone(JST)
    midnight = datetime(now.year, now.month, now.day, tzinfo=JST) \
        + timedelta(days=1)
    cycles_left = int((midnight - now).total_seconds() // interval_seconds)
    reserve = cycles_left * (query_count + 1)
    return max(0, state.remaining_requests() - reserve)


def next_backfill(snapshot, queries, full_resync_days, now: datetime):
    # Group pools first: /summary/* only needs those, and the prefecture
    # query's full history is by far the largest.
    ordered = sorted(queries, key=lambda q: q["pool"] == PREFECTURE_POOL)
    for query in ordered:
        synced_at = parse_iso(get_pool(snapshot, query["pool"])["full_synced_at"])
        if synced_at is None or \
                now - synced_at >= timedelta(days=full_resync_days):
            return {"pool": query["pool"], "start": 1,
                    "started_at": iso(now), "seen": []}
    return None


def backfill(client, snapshot, queries, allowance, full_resync_days,
             now: datetime, save):
    """Page through full histories, at most `allowance` requests per call.
    Progress lives in snapshot["backfill"], so it resumes across cycles
    and restarts."""
    used = 0
    queries_by_pool = {q["pool"]: q for q in queries}
    while used < allowance:
        job = snapshot.get("backfill") or \
            next_backfill(snapshot, queries, full_resync_days, now)
        if job is None:
            break
        snapshot["backfill"] = job

        query = queries_by_pool.get(job["pool"])
        if query is None:  # pool dropped from config since this started
            snapshot["backfill"] = None
            continue

        json_data = client.get("events/", {**query["params"],
                                           "count": PAGE_SIZE, "order": 2,
                                           "start": job["start"]})
        used += 1

        pool = get_pool(snapshot, job["pool"])
        events = pool["events"]
        changed = False
        for item in json_data["events"]:
            event_id = str(item["id"])
            if events.get(event_id) != item:
                events[event_id] = item
                changed = True
            job["seen"].append(event_id)
        job["start"] += PAGE_SIZE

        if json_data["results_returned"] < PAGE_SIZE:
            changed |= finish_backfill(pool, job, json_data)
            pool["full_synced_at"] = iso(now)
            snapshot["backfill"] = None

        if changed:
            pool["changed_at"] = iso(now)
        save()
    return used


def finish_backfill(pool, job, last_page) -> bool:
    """Drop events connpass no longer has. Skipped when the pass didn't
    see exactly results_available distinct events: pages can shift while
    paging, and pruning then could drop an event that merely got skipped."""
    seen = set(job["seen"])
    if last_page.get("results_available") != len(seen):
        print({"message": "Skipped pruning after backfill",
               "pool": job["pool"], "seen": len(seen),
               "results_available": last_page.get("results_available")})
        return False

    started_at = parse_iso(job["started_at"])
    events = pool["events"]
    stale = [k for k, v in events.items()
             if k not in seen and parse_iso(v["updated_at"]) < started_at]
    for event_id in stale:
        del events[event_id]
    return len(stale) > 0


def run_cycle(path, config, client, state: SyncState, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    settings = sync_settings(config)
    snapshot = load_snapshot(path)
    queries = service.connpass_event_queries(config)
    months = recent_months(now, settings["recent_months_before"],
                           settings["recent_months_after"])
    result = {"recent": {}, "groups": None, "backfill_requests": 0,
              "stopped": None}

    def save():
        save_snapshot(path, snapshot, now)

    def run_step(name, fn):
        """Runs one step; returns False when the whole cycle must stop."""
        try:
            fn()
            save()
        except BudgetExhausted:
            result["stopped"] = "daily request budget exhausted"
            return False
        except ConnpassException as e:
            print({"message": "connpass sync step failed", "step": name,
                   "status_code": e.status_code, "detail": e.message})
            if e.status_code == 429:
                result["stopped"] = "rate limited by connpass (429)"
                return False
        except requests.RequestException as e:
            print({"message": "connpass sync step failed", "step": name,
                   "detail": str(e)})
        return True

    for query in queries:
        def step(query=query):
            result["recent"][query["pool"]] = sync_recent(
                client, snapshot, query, months, now)
        if not run_step("recent:" + query["pool"], step):
            return result

    subdomains = service.connpass_group_subdomains(config)
    if len(subdomains) > 0 and groups_due(snapshot, now):
        def step():
            result["groups"] = sync_groups(client, snapshot, subdomains, now)
        if not run_step("groups", step):
            return result

    allowance = backfill_allowance(state, len(queries),
                                   settings["interval_minutes"] * 60, now)

    def step():
        result["backfill_requests"] = backfill(
            client, snapshot, queries, allowance,
            settings["full_resync_days"], now, save)
    run_step("backfill", step)
    return result


def default_state_path(snapshot_path) -> str:
    return os.path.splitext(snapshot_path)[0] + ".state.json"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sync connpass events into the API's snapshot file.")
    parser.add_argument("--loop", action="store_true",
                        help="keep running, one cycle per interval")
    args = parser.parse_args(argv)

    path = service.connpass_snapshot_location
    if not path or path.startswith(("http://", "https://")):
        print("CONNPASS_SNAPSHOT must be set to a local file path",
              file=sys.stderr)
        return 2

    config = service.config
    settings = sync_settings(config)
    state = SyncState(default_state_path(path),
                      settings["daily_request_limit"],
                      settings["request_interval_seconds"])
    client = ConnpassClient(state, api_key=service.connpass_api_key,
                            user_agent=service.get_user_agent(config))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # Two sync processes would each pace themselves but jointly exceed
    # connpass's limits, so only one may run at a time.
    lock_file = open(path + ".lock", "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another connpass sync is already running", file=sys.stderr)
        return 1

    interval = settings["interval_minutes"] * 60
    while True:
        if args.loop:
            # Honors the last cycle across restarts, so a crash loop
            # can't spend the budget on back-to-back cycles.
            time.sleep(state.seconds_until_next_cycle(interval))
        state.mark_cycle_started()
        result = run_cycle(path, config, client, state)
        print({"message": "connpass sync cycle finished", **result,
               "requests_used_today": state.requests_used()})
        if not args.loop:
            return 0


if __name__ == "__main__":
    sys.exit(main())

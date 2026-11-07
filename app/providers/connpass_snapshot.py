import json
import os
import threading
import time
import requests
from datetime import datetime, timezone
from .connpass import ConnpassException, convert_events, convert_groups

SNAPSHOT_REQUEST_TIMEOUT = 10

PREFECTURE_POOL = "prefecture"


def subdomain_pool_name(subdomains, keywords=None) -> str:
    """Stable pool name for one connpass subdomain query; app/sync.py and
    the API both derive it from config, so they must agree on the shape."""
    name = "subdomain:" + ",".join(subdomains)
    if keywords:
        name += "|keyword:" + ",".join(keywords)
    return name


class ConnpassSnapshot:
    """Read side of the connpass snapshot written by app/sync.py.

    The API never calls connpass itself in snapshot mode (connpass now
    allows only 1 request / 12s and 100 / day), so everything it serves
    from connpass comes from this file. `location` is a local path or an
    http(s) URL; the parsed content is kept in memory and reloaded when
    the file changes (or, for a URL, every URL_RELOAD_SECONDS)."""

    FILE_CHECK_SECONDS = 30
    URL_RELOAD_SECONDS = 300

    def __init__(self, location: str):
        self.location = location
        self._data = None
        self._mtime = None
        self._checked_at = 0.0
        self._lock = threading.Lock()

    def is_url(self) -> bool:
        return self.location.startswith(("http://", "https://"))

    def data(self) -> dict:
        with self._lock:
            interval = (self.URL_RELOAD_SECONDS if self.is_url()
                        else self.FILE_CHECK_SECONDS)
            now = time.monotonic()
            if self._data is None or now - self._checked_at >= interval:
                self._checked_at = now
                try:
                    self.__reload()
                except Exception as e:
                    # Keep serving the last good snapshot; only fail when
                    # there has never been one.
                    print({"message": "Failed to load connpass snapshot",
                           "location": self.location, "detail": str(e)})
            if self._data is None:
                raise ConnpassException(
                    503, "connpass snapshot is not available yet")
            return self._data

    def __reload(self):
        if self.is_url():
            response = requests.get(self.location,
                                    timeout=SNAPSHOT_REQUEST_TIMEOUT)
            if response.status_code != 200:
                raise ConnpassException(response.status_code,
                                        "Failed to fetch connpass snapshot")
            self._data = response.json()
            return

        mtime = os.stat(self.location).st_mtime
        if self._data is not None and mtime == self._mtime:
            return
        with open(self.location, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._mtime = mtime

    def pool(self, name: str):
        """Returns (raw connpass events, changed_at) for one pool."""
        pool = self.data().get("pools", {}).get(name)
        if pool is None:
            return [], None
        return list(pool.get("events", {}).values()), \
            parse_timestamp(pool.get("changed_at"))

    def subdomain_pools(self):
        """Yields (raw events, changed_at) for every subdomain pool."""
        for name in self.data().get("pools", {}):
            if name != PREFECTURE_POOL:
                yield self.pool(name)

    def groups(self):
        """Returns (raw connpass groups, changed_at)."""
        groups = self.data().get("groups") or {}
        return groups.get("items", []), parse_timestamp(groups.get("changed_at"))


def parse_timestamp(value):
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


class ConnpassSnapshotEventRequest:
    """Drop-in for ConnpassEventRequest, answering the same queries from a
    ConnpassSnapshot. Connection-related arguments (cache, api_key, ...)
    are accepted so callers can construct either class the same way."""

    def __init__(self, snapshot: ConnpassSnapshot, event_id=None,
                 prefecture=None, subdomain=None, ym=None, ymd=None,
                 keyword=None, **_connection_kwargs):
        self.snapshot = snapshot
        self.prefecture = [] if prefecture is None else prefecture
        self.subdomain = [] if subdomain is None else subdomain
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd
        # keyword is not re-applied: a subdomain pool that needs it was
        # already fetched with it (chapter entries), and the caller's exact
        # title match is what decides membership anyway.
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)
        self.total_available = None

    def get_events(self):
        if len(self.prefecture) > 0:
            raw, changed_at = self.snapshot.pool(PREFECTURE_POOL)
            self.__touch(changed_at)
        else:
            raw = {}
            for items, changed_at in self.snapshot.subdomain_pools():
                matched = [item for item in items
                           if self.__in_subdomain(item)]
                if matched:
                    self.__touch(changed_at)
                for item in matched:
                    raw[item["id"]] = item
            raw = list(raw.values())

        raw = [item for item in raw if self.__in_ym_ymd(item)]
        self.total_available = len(raw)
        # connpass's native order (see ConnpassEventRequest.PAGE_SIZE)
        raw.sort(key=lambda item: item["started_at"], reverse=True)

        events = convert_events(raw)
        if len(self.prefecture) > 0:
            events = [ev for ev in events if self.__is_in_pref(ev)]
        return events

    def get_events_page(self, item_start: int, item_count: int,
                        order: str = "desc"):
        events = self.get_events()
        if order == "asc":
            events.reverse()
        return events[item_start - 1:item_start - 1 + item_count]

    def get_last_modified(self):
        return self.last_modified

    def get_total_available(self):
        return self.total_available

    def __touch(self, changed_at):
        if changed_at is not None:
            self.last_modified = max(self.last_modified, changed_at)

    def __in_subdomain(self, item):
        group = item.get("group")
        return group is not None and group["subdomain"] in self.subdomain

    def __in_ym_ymd(self, item):
        if len(self.ym) == 0 and len(self.ymd) == 0:
            return True
        # started_at is JST (+09:00), the same calendar connpass's own
        # ym/ymd filters use.
        event_date = item["started_at"][:10].replace("-", "")
        return event_date[:6] in self.ym or event_date in self.ymd

    def __is_in_pref(self, event):
        if event.address is None:
            return False
        return any(pref in event.address for pref in self.prefecture)


class ConnpassSnapshotGroupRequest:
    """Drop-in for ConnpassGroupRequest backed by a ConnpassSnapshot."""

    def __init__(self, snapshot: ConnpassSnapshot, subdomain=None,
                 **_connection_kwargs):
        self.snapshot = snapshot
        self.subdomain = subdomain
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)

    def get_group(self):
        groups = self.get_groups()
        if len(groups) == 0:
            return None
        return groups[0]

    def get_groups(self):
        items, changed_at = self.snapshot.groups()
        if changed_at is not None:
            self.last_modified = max(self.last_modified, changed_at)
        if self.subdomain is not None:
            subdomains = (self.subdomain if isinstance(self.subdomain, list)
                          else self.subdomain.split(","))
            items = [item for item in items if item["subdomain"] in subdomains]
        return convert_groups(items)

    def get_last_modified(self):
        return self.last_modified

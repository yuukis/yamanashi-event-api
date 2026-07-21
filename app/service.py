from typing import List, Optional, Tuple
from fastapi import BackgroundTasks, HTTPException
from .providers.connpass import ConnpassEventRequest, ConnpassGroupRequest, ConnpassException
from .providers.icalendar import IcalEventRequest, IcalException
from .providers.archive import ArchiveIndexRequest, ArchiveException
from .models import Event, Group
from .cache import EventRequestCache
from .keywords import KeywordExtractor
import dataclasses
import os
from datetime import datetime, timezone
import yaml
from dotenv import load_dotenv

load_dotenv()
dirname = os.path.dirname(__file__)
config_file = os.path.join(dirname, "config.yaml")

cache = EventRequestCache()
keyword_extractor = KeywordExtractor()

_archive_group_keys = None  # see get_archive_group_keys()

with open(config_file, "r", encoding="utf-8") as yml:
    config = yaml.safe_load(yml)

connpass_api_key = os.getenv("CONNPASS_API_KEY")
events_refresh_token = os.getenv("EVENTS_REFRESH_TOKEN")
try:
    events_refresh_min_interval = int(
        os.getenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", "60"))
    if events_refresh_min_interval <= 0:
        events_refresh_min_interval = 60
except ValueError:
    events_refresh_min_interval = 60


def normalize_event_params(params):
    """Normalize filter values so equivalent requests share a cache key."""
    uid = params.get("uid")
    if uid is not None:
        uid = uid.strip()
        if uid == "":
            uid = None

    result = {**params, "uid": uid}

    if "group_key" in params:
        group_key = params.get("group_key")
        if group_key is not None:
            group_key = group_key.strip()
            if group_key == "":
                group_key = None
        result["group_key"] = group_key

    return result


def get_events(params,
               background_tasks: BackgroundTasks = None,
               ex: int = 3600*72,  # 72 hours
               cache_ttl: int = None
               ) -> Tuple[List[Event], datetime]:
    global cache

    last_modified = None

    params = normalize_event_params(params)

    events, last_modified = get_events_from_cache(cache, params)

    if events is None:
        events, last_modified = request_events(params, cache_ttl=cache_ttl)

    if background_tasks is not None:
        background_tasks.add_task(fetch_events, params, ex, cache_ttl)

    return events, last_modified


def get_events_from_cache(
    cache, params
) -> Tuple[Optional[List[Event]], Optional[datetime]]:
    response = cache.get(params)
    if response is None:
        return None, None
    json = response["json"]
    last_modified = response["last_modified"]
    if json is not None:
        return Event.from_json(json), last_modified
    return None, None


def fetch_events(params, ex: int = 3600*72, cache_ttl: int = None):  # 72 hours
    global cache

    events = None
    last_modified = None
    try:
        events, last_modified = request_events(params, cache_ttl=cache_ttl)

    except HTTPException:
        return

    if events is not None:
        json = Event.to_json(events)
        cache.set(params, json, last_modified=last_modified, ex=ex)


def request_events(params, cache_ttl: int = None,
                   force_refresh: bool = False) -> Tuple[List[Event], datetime]:
    global cache

    ym = params["ym"] if "ym" in params else None
    ymd = params["ymd"] if "ymd" in params else None
    keyword = params["keyword"] if "keyword" in params else None
    uid = params["uid"] if "uid" in params else None
    group_key = params.get("group_key")
    connpass_cache_ttl = cache_ttl if cache_ttl is not None else 3600

    user_agent = get_user_agent(config)

    events = []
    last_modified = datetime.fromtimestamp(0, timezone.utc)
    try:
        if group_key is not None:
            source = find_group_source(group_key)
            if source is not None:
                events, last_modified = request_events_for_group(
                    source, group_key, ym, ymd, connpass_cache_ttl, force_refresh)

        else:
            if "scope" in config and "prefecture" in config["scope"]:
                prefecture = config["scope"]["prefecture"]
                r = ConnpassEventRequest(prefecture=prefecture,
                                         ym=ym, ymd=ymd, cache=cache,
                                         api_key=connpass_api_key,
                                         user_agent=user_agent,
                                         cache_ttl=connpass_cache_ttl,
                                         skip_cache=force_refresh
                                         )
                events += r.get_events()
                last_modified = max(last_modified, r.get_last_modified())

            plain_subdomains, chapters = split_connpass_scope(config)

            if len(plain_subdomains) > 0:
                r = ConnpassEventRequest(subdomain=plain_subdomains,
                                         ym=ym, ymd=ymd, cache=cache,
                                         api_key=connpass_api_key,
                                         user_agent=user_agent,
                                         cache_ttl=connpass_cache_ttl,
                                         skip_cache=force_refresh
                                         )
                events += r.get_events()
                last_modified = max(last_modified, r.get_last_modified())

            # Chapters are fetched separately, one request per shared
            # subdomain, with their title_keyword(s) passed as connpass's
            # `keyword` filter -- a subdomain shared with other chapters
            # (e.g. a nationwide group) can carry far more history than
            # this chapter's own share of it, so narrowing upstream avoids
            # paginating through all of it just to extract a handful of
            # relevant events. partition_and_relabel_chapter_events() still
            # re-checks the title exactly, since connpass's keyword search
            # is broader than a title match (see its docstring).
            chapters_by_subdomain = group_chapters_by_subdomain(chapters)
            for chapter_subdomain, entries in chapters_by_subdomain.items():
                # dict.fromkeys, not a plain list: a misconfigured scope
                # with repeated chapter entries (or entries that happen to
                # share a title_keyword) must not leak a duplicate
                # keyword into the query -- same reasoning as the plain
                # subdomain dedup above.
                keywords = list(dict.fromkeys(
                    entry["title_keyword"] for entry in entries))
                r = ConnpassEventRequest(
                    subdomain=[chapter_subdomain],
                    keyword=keywords,
                    ym=ym, ymd=ymd, cache=cache,
                    api_key=connpass_api_key,
                    user_agent=user_agent,
                    cache_ttl=connpass_cache_ttl,
                    skip_cache=force_refresh
                )
                events += partition_and_relabel_chapter_events(
                    r.get_events(), entries)
                last_modified = max(last_modified, r.get_last_modified())

            if "scope" in config and "icalendar" in config["scope"]:
                icalendar = config["scope"]["icalendar"]
                for group in icalendar:
                    key = group["key"]
                    name = group["name"]
                    image_url = group.get("image_url")
                    group_url = group.get("group_url")
                    ical_url = group["ical_url"]
                    r = IcalEventRequest(url=ical_url,
                                         key=key, name=name,
                                         image_url=image_url, group_url=group_url,
                                         ym=ym, ymd=ymd, cache=cache)
                    events += r.get_events()
                    last_modified = max(last_modified, r.get_last_modified())

            if "scope" in config and "archives" in config["scope"]:
                for url in get_archive_urls(config):
                    r = ArchiveIndexRequest(url=url,
                                            ym=ym, ymd=ymd, cache=cache)
                    events += r.get_events()
                    last_modified = max(last_modified, r.get_last_modified())

    except ConnpassException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except IcalException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except ArchiveException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    events = Event.distinct_by_uid(events)
    events.sort(key=lambda x: x.started_at, reverse=False)

    # Archive events inherit their own keywords; extract for the rest
    for event in events:
        if event.keywords is None:
            event.keywords = keyword_extractor.extract(event)

    if keyword is not None:
        events = [ev for ev in events if ev.contains_keyword(keyword)]

    if uid is not None:
        events = [ev for ev in events if ev.uid == uid]

    return events, last_modified


def get_archive_group_keys() -> frozenset:
    """Community keys across all archives, memoized for the process (a
    frozenset so callers can't mutate the shared cache)."""
    global _archive_group_keys, cache

    if _archive_group_keys is not None:
        return _archive_group_keys

    keys = set()
    if "scope" in config and "archives" in config["scope"]:
        for url in get_archive_urls(config):
            r = ArchiveIndexRequest(url=url, cache=cache)
            keys |= {g.key for g in r.get_groups()}

    _archive_group_keys = frozenset(keys)
    return _archive_group_keys


def find_group_source(group_key) -> Optional[dict]:
    """Resolve group_key to its source; flags "also_archive" when an
    archive also has a community under the same key."""
    plain_subdomains, chapters = split_connpass_scope(config)

    primary = None
    chapter_entry = next((c for c in chapters if c["key"] == group_key), None)
    if chapter_entry is not None:
        primary = {"type": "connpass", "subdomain": chapter_entry["subdomain"],
                   "keyword": chapter_entry["title_keyword"],
                   "chapter_entry": chapter_entry}

    elif group_key in plain_subdomains:
        primary = {"type": "connpass", "subdomain": group_key, "keyword": None,
                   "chapter_entry": None}

    elif "scope" in config and "icalendar" in config["scope"]:
        for entry in config["scope"]["icalendar"]:
            if entry["key"] == group_key:
                primary = {"type": "icalendar", "ical_url": entry["ical_url"],
                           "name": entry["name"],
                           "group_url": entry.get("group_url")}
                break

    has_archive_group = group_key in get_archive_group_keys()

    if primary is not None:
        if has_archive_group:
            primary["also_archive"] = True
        return primary

    if has_archive_group:
        return {"type": "archive"}

    return None


def request_events_for_group(source: dict, group_key, ym, ymd, cache_ttl: int,
                             force_refresh: bool = False
                             ) -> Tuple[List[Event], datetime]:
    """Fetch events for a group whose source was resolved by find_group_source()."""
    global cache

    user_agent = get_user_agent(config)
    events = []
    last_modified = datetime.fromtimestamp(0, timezone.utc)

    if source["type"] == "connpass":
        r = ConnpassEventRequest(subdomain=[source["subdomain"]],
                                 keyword=source["keyword"],
                                 ym=ym, ymd=ymd, cache=cache,
                                 api_key=connpass_api_key, user_agent=user_agent,
                                 cache_ttl=cache_ttl, skip_cache=force_refresh)
        fetched = r.get_events()
        # keyword only narrows the upstream fetch; the exact title match
        # below still runs since connpass's keyword search is broader.
        events += (partition_and_relabel_chapter_events(fetched, [source["chapter_entry"]])
                   if source["chapter_entry"] is not None else fetched)
        last_modified = max(last_modified, r.get_last_modified())

    elif source["type"] == "icalendar":
        r = IcalEventRequest(url=source["ical_url"], key=group_key,
                             name=source["name"], group_url=source["group_url"],
                             ym=ym, ymd=ymd, cache=cache)
        events += r.get_events()
        last_modified = max(last_modified, r.get_last_modified())

    # Not "elif": a primary source and an archive can both contribute events.
    if source["type"] == "archive" or source.get("also_archive"):
        # Archive indexes have no per-group query -- filter client-side.
        for url in get_archive_urls(config):
            r = ArchiveIndexRequest(url=url, ym=ym, ymd=ymd, cache=cache)
            events += [ev for ev in r.get_events() if ev.group_key == group_key]
            last_modified = max(last_modified, r.get_last_modified())

    return events, last_modified


def get_group_events_page(group_key, keyword, uid, page: int, per_page: int,
                          order: str = "desc",
                          background_tasks: BackgroundTasks = None,
                          source: Optional[dict] = None
                          ) -> Tuple[List[Event], int, Optional[datetime]]:
    """Serve one page of a group's events, sorted by started_at.

    Paginates directly against connpass (see get_events_page()) for a
    plain connpass group with no keyword/uid filter. Chapters and
    keyword/uid filters need the full result set to apply correctly, so
    those fall back to get_events() and slice locally.

    Returns (events_for_page, total_count, last_modified)."""
    global cache

    source = source or find_group_source(group_key)
    if source is None:
        return [], 0, None

    # Blank query params arrive as "" here, not None; treat them the same.
    keyword = (keyword.strip() or None) if keyword is not None else None
    uid = (uid.strip() or None) if uid is not None else None

    can_paginate_upstream = (
        source["type"] == "connpass"
        and source["chapter_entry"] is None
        and not source.get("also_archive")
        and keyword is None
        and uid is None
    )

    if can_paginate_upstream:
        user_agent = get_user_agent(config)
        r = ConnpassEventRequest(subdomain=[source["subdomain"]],
                                 cache=cache, api_key=connpass_api_key,
                                 user_agent=user_agent)
        item_start = (page - 1) * per_page + 1
        events = r.get_events_page(item_start, per_page, order=order)
        for event in events:
            if event.keywords is None:
                event.keywords = keyword_extractor.extract(event)
        return events, r.get_total_available() or 0, r.get_last_modified()

    events, last_modified = get_events(
        {"keyword": keyword, "uid": uid, "group_key": group_key},
        background_tasks)
    if order == "desc":
        events = list(reversed(events))
    start = (page - 1) * per_page
    return events[start:start + per_page], len(events), last_modified


def get_groups(params,
               background_tasks: BackgroundTasks = None
               ) -> Tuple[List[Group], datetime]:
    global cache

    last_modified = None

    groups, last_modified = get_groups_from_cache(cache, params)

    if groups is None:
        groups, last_modified = request_groups(params)

    if background_tasks is not None:
        background_tasks.add_task(fetch_groups, params)

    return groups, last_modified


def get_groups_from_cache(
    cache, params
) -> Tuple[Optional[List[Group]], Optional[datetime]]:
    response = cache.get(params)
    if response is None:
        return None, None
    json = response["json"]
    last_modified = response["last_modified"]
    if json is not None:
        return Group.from_json(json), last_modified
    return None, None


def fetch_groups(params):
    global cache

    groups = None
    last_modified = None
    try:
        groups, last_modified = request_groups(params)

    except HTTPException:
        return

    if groups is not None:
        json = Group.to_json(groups)
        cache.set(params, json, last_modified=last_modified,
                  ex=3600*72)  # 72 hours


def request_groups(params) -> Tuple[List[Group], datetime]:
    global cache

    user_agent = get_user_agent(config)

    groups = []
    last_modified = datetime.fromtimestamp(0, timezone.utc)
    try:
        plain_subdomains, chapters = split_connpass_scope(config)
        chapter_subdomains = {c["subdomain"] for c in chapters}
        subdomain = merged_connpass_subdomains(plain_subdomains, chapters)

        real_groups_by_key = {}
        if len(subdomain) > 0:
            r = ConnpassGroupRequest(subdomain=subdomain,
                                     cache=cache, api_key=connpass_api_key,
                                     user_agent=user_agent)
            fetched = r.get_groups()
            last_modified = max(last_modified, r.get_last_modified())
            real_groups_by_key = {g.key: g for g in fetched
                                  if g.key in chapter_subdomains}
            groups += [g for g in fetched if g.key not in chapter_subdomains]

        groups += get_groups_from_connpass_chapters(
            chapters, real_groups_by_key)

        if "scope" in config and "icalendar" in config["scope"]:
            groups += get_groups_from_icalendar(config)

        if "scope" in config and "archives" in config["scope"]:
            for url in get_archive_urls(config):
                r = ArchiveIndexRequest(url=url, cache=cache)
                groups += r.get_groups()
                last_modified = max(last_modified, r.get_last_modified())

    except ConnpassException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except ArchiveException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    groups = merge_duplicate_groups(groups)

    return groups, last_modified


def merge_duplicate_groups(groups: List[Group]) -> List[Group]:
    """Fold Group entries sharing a key into one, backfilling only the
    base's null fields from later duplicates."""
    merged_by_key = {}
    order = []
    for g in groups:
        if g.key not in merged_by_key:
            merged_by_key[g.key] = g
            order.append(g.key)
            continue

        base = merged_by_key[g.key]
        for field in dataclasses.fields(Group):
            if field.name in ("id", "key"):
                continue
            if getattr(base, field.name) is None:
                value = getattr(g, field.name)
                if value is not None:
                    setattr(base, field.name, value)

    return [merged_by_key[key] for key in order]


def get_user_agent(config):
    if "api_client" in config and "user_agent" in config["api_client"]:
        version = config["metadata"]["version"]
        user_agent = config["api_client"]["user_agent"]
        user_agent = user_agent.replace("{version}", version)
        return user_agent
    return None


def split_connpass_scope(config):
    plain = []
    chapters = []
    if "scope" in config and "connpass" in config["scope"]:
        for entry in config["scope"]["connpass"]:
            if not isinstance(entry, dict):
                raise ValueError(
                    "scope.connpass: each entry must be a mapping with "
                    f"at least a subdomain key, got {entry!r}")

            subdomain = entry.get("subdomain")
            if not isinstance(subdomain, str) or subdomain == "":
                raise ValueError(
                    "scope.connpass: each entry requires a non-empty "
                    f"string subdomain, got {entry!r}")

            if "title_keyword" in entry:
                title_keyword = entry.get("title_keyword")
                if not isinstance(title_keyword, str) or title_keyword == "":
                    raise ValueError(
                        "scope.connpass: chapter entry for subdomain "
                        f"'{subdomain}' requires a non-empty string "
                        "title_keyword")
                if not entry.get("key") or not entry.get("name"):
                    raise ValueError(
                        "scope.connpass: chapter entry for subdomain "
                        f"'{subdomain}' requires key and name")
                chapters.append(entry)
            else:
                plain.append(subdomain)

    conflicting = {c["subdomain"] for c in chapters} & set(plain)
    if conflicting:
        raise ValueError(
            f"scope.connpass: subdomain(s) {sorted(conflicting)} are "
            "configured as both a plain entry and a chapter entry "
            "(title_keyword set) -- a subdomain can only be one or the "
            "other")

    # dict.fromkeys, not set(): dedupes a config with repeated plain
    # entries while preserving order, so callers building a connpass
    # request straight from this list get a stable query/cache key
    # regardless of accidental duplicates in scope.connpass.
    plain = list(dict.fromkeys(plain))

    return plain, chapters


def merged_connpass_subdomains(plain_subdomains, chapters):
    # dict.fromkeys, not set(): dedupes while preserving insertion order,
    # so the connpass query params (and their cache key) stay stable
    # regardless of set iteration/hash-seed order.
    merged = dict.fromkeys(plain_subdomains)
    for entry in chapters:
        merged.setdefault(entry["subdomain"], None)
    return list(merged)


def group_chapters_by_subdomain(chapters):
    grouped = {}
    for entry in chapters:
        grouped.setdefault(entry["subdomain"], []).append(entry)
    return grouped


def partition_and_relabel_chapter_events(events, chapters):
    # The exact title substring match here is the source of truth, even
    # when the caller already pre-filtered upstream via connpass's own
    # `keyword` search (see request_events()) -- that search also matches
    # description/address text, so it can still return other chapters'
    # events (sharing the same subdomain); this re-check is what actually
    # keeps only the ones belonging to this chapter.
    if not chapters:
        return events

    entries_by_subdomain = group_chapters_by_subdomain(chapters)

    result = []
    for ev in events:
        entries = entries_by_subdomain.get(ev.group_key)
        if entries is None:
            result.append(ev)
            continue
        for entry in entries:
            if entry["title_keyword"] in ev.title:
                ev.group_key = entry["key"]
                ev.group_name = entry["name"]
                ev.group_url = entry.get("group_url", ev.group_url)
                result.append(ev)
                break
    return result


def get_groups_from_connpass_chapters(chapters, real_groups_by_key):
    groups = []
    for entry in chapters:
        real = real_groups_by_key.get(entry["subdomain"])
        inherited = Group.to_json(real) if real is not None else {}
        # id belongs to the shared group, not this chapter -- multiple
        # chapters carved out of the same shared group would otherwise
        # all report the same id.
        inherited.pop("id", None)
        # member_users_count is the shared group's total, not this chapter's
        inherited.pop("member_users_count", None)
        g = Group.from_json({
            **inherited,
            "key": entry["key"],
            "title": entry["name"],
            "image_url": entry.get("image_url", inherited.get("image_url")),
            "url": entry.get("group_url", inherited.get("url")),
        })
        groups.append(g)

    return groups


def get_groups_from_icalendar(config):
    groups = []
    if "scope" in config and "icalendar" in config["scope"]:
        icalendar = config["scope"]["icalendar"]
        for group in icalendar:
            g = Group.from_json({
                "key": group["key"],
                "title": group["name"],
                "image_url": group.get("image_url"),
                "url": group["group_url"],
                "ical_url": group["ical_url"]
            })
            groups.append(g)

    return groups


def get_groups_from_archives(config):
    groups = []
    for url in get_archive_urls(config):
        r = ArchiveIndexRequest(url=url, cache=cache)
        groups += r.get_groups()

    return groups


def preload_archive_indexes():
    for url in get_archive_urls(config):
        try:
            r = ArchiveIndexRequest(url=url, cache=cache)
            r.preload()
        except ArchiveException as e:
            print({
                "message": "Failed to preload archive index",
                "url": url,
                "status_code": e.status_code,
                "detail": e.message
            })


def get_archive_urls(config):
    if "scope" not in config or "archives" not in config["scope"]:
        return []

    urls = []
    archives = config["scope"]["archives"]
    for archive in archives:
        if "url" not in archive:
            continue
        url = archive["url"]
        if isinstance(url, list):
            urls += url
        else:
            urls.append(url)

    return urls


# Fail fast at startup if scope.connpass is misconfigured, rather than
# only surfacing a clear error on the first /events or /groups request.
split_connpass_scope(config)

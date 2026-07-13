from typing import List, Optional, Tuple
from fastapi import BackgroundTasks, HTTPException
from .providers.connpass import ConnpassEventRequest, ConnpassGroupRequest, ConnpassException
from .providers.icalendar import IcalEventRequest, IcalException
from .providers.archive import ArchiveIndexRequest, ArchiveException
from .models import Event, Group
from .cache import EventRequestCache
from .keywords import KeywordExtractor
import os
from datetime import datetime, timezone
import yaml
from dotenv import load_dotenv

load_dotenv()
dirname = os.path.dirname(__file__)
config_file = os.path.join(dirname, "config.yaml")

cache = EventRequestCache()
keyword_extractor = KeywordExtractor()

with open(config_file, "r", encoding="utf-8") as yml:
    config = yaml.safe_load(yml)

connpass_api_key = os.getenv("CONNPASS_API_KEY")
events_refresh_token = os.getenv("EVENTS_REFRESH_TOKEN")
try:
    events_refresh_min_interval = int(
        os.getenv("EVENTS_REFRESH_MIN_INTERVAL_SECONDS", "60"))
except ValueError:
    events_refresh_min_interval = 60


def normalize_event_params(params):
    """Normalize filter values so equivalent requests share a cache key."""
    uid = params.get("uid")
    if uid is not None:
        uid = uid.strip()
        if uid == "":
            uid = None
    return {**params, "uid": uid}


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
    connpass_cache_ttl = cache_ttl if cache_ttl is not None else 3600

    user_agent = get_user_agent(config)

    events = []
    last_modified = datetime.fromtimestamp(0, timezone.utc)
    try:
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

        if "scope" in config and "subdomain" in config["scope"]:
            subdomain = config["scope"]["subdomain"]
            r = ConnpassEventRequest(subdomain=subdomain,
                                     ym=ym, ymd=ymd, cache=cache,
                                     api_key=connpass_api_key,
                                     user_agent=user_agent,
                                     cache_ttl=connpass_cache_ttl,
                                     skip_cache=force_refresh
                                     )
            events += r.get_events()
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
        if "scope" in config and "subdomain" in config["scope"]:
            subdomain = config["scope"]["subdomain"]
            r = ConnpassGroupRequest(subdomain=subdomain,
                                     cache=cache, api_key=connpass_api_key,
                                     user_agent=user_agent)
            groups += r.get_groups()
            last_modified = max(last_modified, r.get_last_modified())

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

    return groups, last_modified


def get_user_agent(config):
    if "api_client" in config and "user_agent" in config["api_client"]:
        version = config["metadata"]["version"]
        user_agent = config["api_client"]["user_agent"]
        user_agent = user_agent.replace("{version}", version)
        return user_agent
    return None


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

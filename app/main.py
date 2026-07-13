from typing import List, Optional, Tuple
from fastapi import FastAPI, BackgroundTasks, Path, HTTPException
from fastapi.responses import RedirectResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .connpass import ConnpassEventRequest, ConnpassGroupRequest, ConnpassException
from .icalendar import IcalEventRequest, IcalException
from .archive import ArchiveIndexRequest, ArchiveException
from .models import Event, Group
from .models import GroupActivity, YearSummary, HeatmapBucket, EventsSummary
from .cache import EventRequestCache
from .keywords import KeywordExtractor
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, time as time_of_day
import yaml
from dotenv import load_dotenv
from mangum import Mangum
from fastapi_mcp import FastApiMCP

load_dotenv()
dirname = os.path.dirname(__file__)
config_file = os.path.join(dirname, "config.yaml")

cache = EventRequestCache()
keyword_extractor = KeywordExtractor()

with open(config_file, "r", encoding="utf-8") as yml:
    config = yaml.safe_load(yml)

connpass_api_key = os.getenv("CONNPASS_API_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(preload_archive_indexes)
    yield


app = FastAPI(
    title=config["metadata"]["title"],
    description=config["metadata"]["description"],
    version=config["metadata"]["version"],
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

lambda_handler = Mangum(app)


@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/docs")


@app.get("/events", response_model=List[Event],
         operation_id="list_events",
         summary="List recent events")
async def read_events(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    days = config["recent_days"] if "recent_days" in config else 90
    now = datetime.now()
    dt_from = now - timedelta(days=days)
    dt_to = now + timedelta(days=days)
    return await read_events_range(response, background_tasks,
                                   dt_from.year, dt_from.month,
                                   dt_to.year, dt_to.month,
                                   keyword, uid, fields)


@app.get("/events/day/today", response_model=List[Event],
         operation_id="list_events_today",
         summary="List today's events")
async def read_events_day_today(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    today = datetime.now().date()
    return await read_events_for_days(response, background_tasks,
                                      today, 1, keyword, uid, fields)


@app.get("/events/today", response_model=List[Event],
         operation_id="list_events_today_legacy",
         summary="List today's events",
         description="Deprecated. Use GET /events/day/today instead.",
         deprecated=True)
async def read_events_today_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_day_today(response, background_tasks,
                                       keyword, uid, fields)


@app.get("/events/week/this", response_model=List[Event],
         operation_id="list_events_this_week",
         summary="List this week's events")
async def read_events_this_week(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return await read_events_for_days(response, background_tasks,
                                      monday, 7, keyword, uid, fields)


@app.get("/events/week/next", response_model=List[Event],
         operation_id="list_events_next_week",
         summary="List next week's events")
async def read_events_next_week(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    today = datetime.now().date()
    next_monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    return await read_events_for_days(response, background_tasks,
                                      next_monday, 7, keyword, uid, fields)


@app.get("/events/year/{year}", response_model=List[Event],
         operation_id="list_events_by_year",
         summary="List events in a specific year")
async def read_events_year(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_range(response, background_tasks,
                                   year, 1, year, 12,
                                   keyword, uid, fields)


@app.get("/events/in/{year}", response_model=List[Event],
         operation_id="list_events_by_year_legacy",
         summary="List events in a specific year",
         description="Deprecated. Use GET /events/year/{year} instead.",
         deprecated=True)
async def read_events_in_year_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_year(response, background_tasks, year,
                                  keyword, uid, fields)


@app.get("/events/month/{year}/{month}", response_model=List[Event],
         operation_id="list_events_by_month",
         summary="List events in a specific year and month")
async def read_events_month(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_range(response, background_tasks,
                                   year, month, year, month,
                                   keyword, uid, fields)


@app.get("/events/in/{year}/{month}", response_model=List[Event],
         operation_id="list_events_by_month_legacy",
         summary="List events in a specific year and month",
         description="Deprecated. Use GET /events/month/{year}/{month} instead.",
         deprecated=True)
async def read_events_in_year_month_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_month(response, background_tasks, year, month,
                                   keyword, uid, fields)


@app.get("/events/day/{year}/{month}/{day}", response_model=List[Event],
         operation_id="list_events_by_day",
         summary="List events on a specific day")
async def read_events_day(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    ymd = [f"{year:04}{month:02}{day:02}"]
    events, last_modified = get_events(
        {"ymd": ymd, "keyword": keyword, "uid": uid}, background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               "public, max-age=3600", fields)


@app.get("/events/in/{year}/{month}/{day}", response_model=List[Event],
         operation_id="list_events_by_day_legacy",
         summary="List events on a specific day",
         description="Deprecated. Use GET /events/day/{year}/{month}/{day} instead.",
         deprecated=True)
async def read_events_in_year_month_day_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_day(response, background_tasks, year, month, day,
                                 keyword, uid, fields)


@app.get("/events/range/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[Event],
         operation_id="list_events_by_range",
         summary="List events within a date range")
async def read_events_range(
    response: Response,
    background_tasks: BackgroundTasks,
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    if from_year > to_year or (from_year == to_year and from_month > to_month):
        raise HTTPException(status_code=400, detail="Invalid date range")

    ym = year_month_range(from_year, from_month, to_year, to_month)

    events, last_modified = get_events(
        {"ym": ym, "keyword": keyword, "uid": uid}, background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               "public, max-age=3600", fields)


@app.get("/events/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[Event],
         operation_id="list_events_by_range_legacy",
         summary="List events within a date range",
         description="Deprecated. Use GET "
                     "/events/range/from/{from_year}/{from_month}/to/{to_year}/{to_month} "
                     "instead.",
         deprecated=True)
async def read_events_fromto_year_month_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    return await read_events_range(response, background_tasks,
                                   from_year, from_month, to_year, to_month,
                                   keyword, uid, fields)


def year_month_range(from_year: int, from_month: int,
                     to_year: int, to_month: int) -> List[str]:
    ym = []
    y = from_year
    m = from_month
    while True:
        ym.append(f"{y:04}{m:02}")
        if y == to_year and m == to_month:
            break
        m += 1
        if m > 12:
            y += 1
            m = 1
    return ym


async def read_events_for_days(
    response: Response,
    background_tasks: BackgroundTasks,
    base_date,
    days: int,
    keyword: str = None,
    uid: str = None,
    fields: str = None
):
    ymd = [(base_date + timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
    events, last_modified = get_events(
        {"ymd": ymd, "keyword": keyword, "uid": uid}, background_tasks)

    max_age = get_max_age_until_next_period(days)
    return build_list_response(response, events, Event, last_modified,
                               f"public, max-age={max_age}", fields)


def get_max_age_until_next_period(days: int, max_age: int = 3600) -> int:
    """Clamp max_age so an HTTP cache can't outlive the day/week the response
    describes, otherwise a response cached just before midnight (or a week
    boundary) could still be served as "today"/"this week" after it rolls
    over."""
    if days not in (1, 7):
        raise ValueError(f"Unsupported days for cache boundary clamping: {days}")

    now = datetime.now()
    today = now.date()
    period_start = today - timedelta(days=today.weekday()) if days == 7 else today
    boundary = datetime.combine(period_start + timedelta(days=days), time_of_day.min)
    seconds_until_boundary = int((boundary - now).total_seconds())
    return max(0, min(max_age, seconds_until_boundary))


def filter_model_fields(items, model, fields: str = None):
    """Return items pruned to the requested comma-separated field names,
    or None if no filtering should be applied (fields is absent/empty).
    model must provide a to_json() static method, e.g. Event or Group."""
    if fields is None:
        return None

    field_names = {f.strip() for f in fields.split(",") if f.strip()}
    if not field_names:
        return None

    return [{k: v for k, v in d.items() if k in field_names}
            for d in model.to_json(items)]


def build_list_response(response: Response, items, model, last_modified,
                        cache_control: str, fields: str = None):
    headers = {}
    if last_modified is not None:
        headers["Last-Modified"] = last_modified.strftime(
            "%a, %d %b %Y %H:%M:%S GMT")
        headers["Cache-Control"] = cache_control

    filtered = filter_model_fields(items, model, fields)
    if filtered is None:
        for key, value in headers.items():
            response.headers[key] = value
        return items

    # Returning a JSONResponse here deliberately bypasses response_model
    # validation/serialization, since the shape is a client-chosen subset
    # of the model's fields rather than the full declared schema.
    return JSONResponse(content=filtered, headers=headers)


@app.get("/groups", response_model=List[Group],
         operation_id="list_groups",
         summary="List community groups")
async def read_groups(
    response: Response,
    background_tasks: BackgroundTasks,
    fields: str = None
):
    groups, last_modified = get_groups({}, background_tasks)

    return build_list_response(response, groups, Group, last_modified,
                               "public, max-age=3600", fields)


@app.get("/summary/events", response_model=EventsSummary,
         operation_id="summary_events",
         summary="Get yearly event summary with group highlights and activity heatmap")
async def read_events_summary(
    response: Response,
    background_tasks: BackgroundTasks
):
    from_year = 2010
    to_year = datetime.now().year

    ym = [f"{y:04}{m:02}" for y in range(from_year, to_year + 1) for m in range(1, 13)]

    events, last_modified = get_events({"ym": ym, "keyword": None},
                                       background_tasks,
                                       ex=3600*24*7,  # 7 days
                                       cache_ttl=3600*24)  # 24 hours
    groups, groups_last_modified = get_groups({}, background_tasks)
    group_by_key = {g.key: g for g in groups}

    if groups_last_modified is not None:
        last_modified = (groups_last_modified if last_modified is None
                         else max(last_modified, groups_last_modified))

    year_stats = {
        y: {"event_count": 0, "group_counts": {}}
        for y in range(from_year, to_year + 1)
    }
    heatmap_counts = {
        f"{y:04}-{m:02}": 0
        for y in range(from_year, to_year + 1) for m in range(1, 13)
    }

    for ev in events:
        year = int(ev.started_at[:4])
        period = ev.started_at[:7]
        if period in heatmap_counts:
            heatmap_counts[period] += 1
        if year not in year_stats:
            continue
        stats = year_stats[year]
        stats["event_count"] += 1
        if ev.group_key and ev.group_key in group_by_key:
            stats["group_counts"][ev.group_key] = \
                stats["group_counts"].get(ev.group_key, 0) + 1

    years = []
    for year in range(from_year, to_year + 1):
        stats = year_stats[year]
        sorted_keys = sorted(stats["group_counts"].items(),
                             key=lambda kv: kv[1], reverse=True)
        group_activities = [
            GroupActivity(
                key=key,
                name=group_by_key[key].title,
                image_url=group_by_key[key].image_url,
                url=group_by_key[key].url,
                event_count=count
            )
            for key, count in sorted_keys
        ]
        years.append(YearSummary(year=year, event_count=stats["event_count"],
                                 groups=group_activities))

    heatmap = [HeatmapBucket(period=p, count=c)
              for p, c in sorted(heatmap_counts.items())]

    summary = EventsSummary(from_year=from_year, to_year=to_year,
                            granularity="month", years=years, heatmap=heatmap)

    if last_modified is not None:
        last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response.headers["Last-Modified"] = last_modified_str
        response.headers["Cache-Control"] = "public, max-age=3600"
    return summary


@app.get("/events/summary", response_model=EventsSummary,
         operation_id="summary_events_legacy",
         summary="Get yearly event summary with group highlights and activity heatmap",
         description="Deprecated. Use GET /summary/events instead.",
         deprecated=True)
async def read_events_summary_legacy(
    response: Response,
    background_tasks: BackgroundTasks
):
    return await read_events_summary(response, background_tasks)


mcp = FastApiMCP(app, include_operations=[
    "list_events",
    "list_events_today",
    "list_events_this_week",
    "list_events_next_week",
    "list_events_by_year",
    "list_events_by_month",
    "list_events_by_day",
    "list_events_by_range",
    "list_groups",
])
mcp.mount_http()


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

    except (ConnpassException, IcalException, ArchiveException):
        return

    if events is not None:
        json = Event.to_json(events)
        cache.set(params, json, last_modified=last_modified, ex=ex)


def request_events(params, cache_ttl: int = None) -> Tuple[List[Event], datetime]:
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
                                     cache_ttl=connpass_cache_ttl
                                     )
            events += r.get_events()
            last_modified = max(last_modified, r.get_last_modified())

        if "scope" in config and "subdomain" in config["scope"]:
            subdomain = config["scope"]["subdomain"]
            r = ConnpassEventRequest(subdomain=subdomain,
                                     ym=ym, ymd=ymd, cache=cache,
                                     api_key=connpass_api_key,
                                     user_agent=user_agent,
                                     cache_ttl=connpass_cache_ttl
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

    except (ConnpassException, ArchiveException):
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

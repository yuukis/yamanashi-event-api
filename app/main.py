from typing import List, Tuple
from fastapi import FastAPI, BackgroundTasks, Path, HTTPException
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from .connpass import ConnpassEventRequest, ConnpassGroupRequest, ConnpassException
from .icalendar import IcalEventRequest, IcalException
from .models import Event, EventDetail, Group
from .cache import EventRequestCache
import os
from datetime import datetime, timedelta, timezone
import yaml
from dotenv import load_dotenv
from mangum import Mangum

load_dotenv()
dirname = os.path.dirname(__file__)
config_file = os.path.join(dirname, "config.yaml")

cache = EventRequestCache()

with open(config_file, "r") as yml:
    config = yaml.safe_load(yml)

connpass_api_key = os.getenv("CONNPASS_API_KEY")

app = FastAPI(
    title=config["metadata"]["title"],
    description=config["metadata"]["description"],
    version=config["metadata"]["version"]
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


@app.get("/events", response_model=List[Event])
async def read_events(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None
):
    days = config["recent_days"] if "recent_days" in config else 90
    now = datetime.now()
    dt_from = now - timedelta(days=days)
    dt_to = now + timedelta(days=days)
    return await read_events_fromto_year_month(response, background_tasks,
                                               dt_from.year, dt_from.month,
                                               dt_to.year, dt_to.month,
                                               keyword)


@app.get("/events/today", response_model=List[Event])
async def read_events_today(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None
):
    now = datetime.now()
    return await read_events_in_year_month_day(response, background_tasks,
                                               now.year, now.month,
                                               now.day, keyword)


@app.get("/events/in/{year}", response_model=List[Event])
async def read_events_in_year(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    keyword: str = None
):
    return await read_events_fromto_year_month(response, background_tasks,
                                               year, 1, year, 12,
                                               keyword)


@app.get("/events/in/{year}/{month}", response_model=List[Event])
async def read_events_in_year_month(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return await read_events_fromto_year_month(response, background_tasks,
                                               year, month, year, month,
                                               keyword)


@app.get("/events/in/{year}/{month}/{day}", response_model=List[Event])
async def read_events_in_year_month_day(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None
):
    ymd = [f"{year:04}{month:02}{day:02}"]
    events, last_modified = get_events({"ymd": ymd, "keyword": keyword},
                                       background_tasks)

    if last_modified is not None:
        last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response.headers["Last-Modified"] = last_modified_str
        response.headers["Cache-Control"] = "public, max-age=3600"
    return events


@app.get("/events/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[Event])
async def read_events_fromto_year_month(
    response: Response,
    background_tasks: BackgroundTasks,
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None
):
    if from_year > to_year or (from_year == to_year and from_month > to_month):
        raise HTTPException(status_code=400, detail="Invalid date range")

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

    events, last_modified = get_events({"ym": ym, "keyword": keyword},
                                       background_tasks)

    if last_modified is not None:
        last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response.headers["Last-Modified"] = last_modified_str
        response.headers["Cache-Control"] = "public, max-age=3600"
    return events


@app.get("/events/full", response_model=List[EventDetail])
async def read_events_full(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None
):
    return await read_events(response, background_tasks, keyword)


@app.get("/events/full/today", response_model=List[EventDetail])
async def read_events_full_today(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None
):
    return await read_events_today(response, background_tasks, keyword)


@app.get("/events/full/in/{year}", response_model=List[EventDetail])
async def read_events_full_in_year(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    keyword: str = None
):
    return await read_events_in_year(response, background_tasks, year, keyword)


@app.get("/events/full/in/{year}/{month}", response_model=List[EventDetail])
async def read_events_full_in_year_month(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return await read_events_in_year_month(response, background_tasks,
                                           year, month, keyword)


@app.get("/events/full/in/{year}/{month}/{day}",
         response_model=List[EventDetail])
async def read_events_full_in_year_month_day(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None
):
    return await read_events_in_year_month_day(response, background_tasks,
                                               year, month, day, keyword)


@app.get("/events/full/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[EventDetail])
async def read_events_full_fromto_year_month(
    response: Response,
    background_tasks: BackgroundTasks,
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return await read_events_fromto_year_month(response, background_tasks,
                                               from_year, from_month,
                                               to_year, to_month,
                                               keyword)


@app.get("/groups", response_model=List[Group])
async def read_groups(
    response: Response,
    background_tasks: BackgroundTasks
):
    groups, last_modified = get_groups({}, background_tasks)

    if last_modified is not None:
        last_modified_str = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response.headers["Last-Modified"] = last_modified_str
        response.headers["Cache-Control"] = "public, max-age=3600"
    return groups


def get_events(params,
               background_tasks: BackgroundTasks = None
               ) -> Tuple[List[EventDetail], datetime]:
    global cache

    last_modified = None

    events, last_modified = get_events_from_cache(cache, params)

    if events is None:
        events, last_modified = request_events(params)

    background_tasks.add_task(fetch_events, params)

    return events, last_modified


def get_events_from_cache(cache, params) -> Tuple[List[EventDetail], datetime]:
    response = cache.get(params)
    if response is None:
        return None, None
    json = response["content"]
    last_modified = response["last_modified"]
    if json is not None:
        return EventDetail.from_json(json), last_modified
    return None, None


def fetch_events(params):
    global cache

    events = None
    last_modified = None
    try:
        events, last_modified = request_events(params)

    except ConnpassException:
        return

    if events is not None:
        json = EventDetail.to_json(events)
        cache.set(params, json, last_modified=last_modified,
                  ex=3600*72)  # 72 hours


def request_events(params) -> Tuple[List[EventDetail], datetime]:
    global cache

    ym = params["ym"] if "ym" in params else None
    ymd = params["ymd"] if "ymd" in params else None
    keyword = params["keyword"] if "keyword" in params else None

    user_agent = get_user_agent(config)

    events = []
    last_modified = datetime.fromtimestamp(0, timezone.utc)
    try:
        if "scope" in config and "prefecture" in config["scope"]:
            prefecture = config["scope"]["prefecture"]
            r = ConnpassEventRequest(prefecture=prefecture,
                                     ym=ym, ymd=ymd, cache=cache,
                                     api_key=connpass_api_key,
                                     user_agent=user_agent
                                     )
            events += r.get_events()
            last_modified = max(last_modified, r.get_last_modified())

        if "scope" in config and "subdomain" in config["scope"]:
            subdomain = config["scope"]["subdomain"]
            r = ConnpassEventRequest(subdomain=subdomain,
                                     ym=ym, ymd=ymd, cache=cache,
                                     api_key=connpass_api_key,
                                     user_agent=user_agent
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
                                     image_url=image_url,
                                     group_url=group_url,
                                     ym=ym, ymd=ymd)
                events += r.get_events()

    except ConnpassException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except IcalException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    events = Event.distinct_by_uid(events)
    events.sort(key=lambda x: x.started_at, reverse=False)

    if keyword is not None:
        events = [ev for ev in events if ev.contains_keyword(keyword)]

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


def get_groups_from_cache(cache, params) -> Tuple[List[Group], datetime]:
    response = cache.get(params)
    if response is None:
        return None, None
    json = response["content"]
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

    except ConnpassException:
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

    except ConnpassException as e:
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

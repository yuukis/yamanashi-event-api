from typing import List
from fastapi import FastAPI, Path, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from .connpass import ConnpassEventRequest, ConnpassException
from .models import Event, EventDetail
from .cache import EventRequestCache
import os
import datetime
import yaml
from dotenv import load_dotenv

load_dotenv()
dirname = os.path.dirname(__file__)
config_file = os.path.join(dirname, "config.yaml")

with open(config_file, "r") as yml:
    config = yaml.safe_load(yml)

redis_url = os.getenv("REDIS_URL")

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


@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/docs")


@app.get("/events", response_model=List[Event])
def read_events(keyword: str = None):
    days = config["recent_days"] if "recent_days" in config else 90
    now = datetime.datetime.now()
    dt_from = now - datetime.timedelta(days=days)
    dt_to = now + datetime.timedelta(days=days)
    return read_events_fromto_year_month(dt_from.year, dt_from.month,
                                         dt_to.year, dt_to.month, keyword)


@app.get("/events/today", response_model=List[Event])
def read_events_today(keyword: str = None):
    now = datetime.datetime.now()
    return read_events_in_year_month_day(now.year, now.month, now.day, keyword)


@app.get("/events/in/{year}", response_model=List[Event])
def read_events_in_year(
    year: int = Path(ge=2010, le=2040),
    keyword: str = None
):
    return read_events_fromto_year_month(year, 1, year, 12, keyword)


@app.get("/events/in/{year}/{month}", response_model=List[Event])
def read_events_in_year_month(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return read_events_fromto_year_month(year, month, year, month, keyword)


@app.get("/events/in/{year}/{month}/{day}", response_model=List[Event])
def read_events_in_year_month_day(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None
):
    ymd = [f"{year:04}{month:02}{day:02}"]

    cache = None
    if redis_url is not None:
        cache = EventRequestCache(url=redis_url)
    user_agent = get_user_agent(config)

    events = []
    try:
        if "scope" in config and "prefecture" in config["scope"]:
            prefecture = config["scope"]["prefecture"]
            events += ConnpassEventRequest(prefecture=prefecture, ymd=ymd,
                                           keyword=keyword, cache=cache,
                                           user_agent=user_agent
                                           ).get_events()
        if "scope" in config and "series_id" in config["scope"]:
            series_id = config["scope"]["series_id"]
            events += ConnpassEventRequest(series_id=series_id, ymd=ymd,
                                           keyword=keyword, cache=cache,
                                           user_agent=user_agent
                                           ).get_events()
    except ConnpassException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    events = Event.distinct_by_id(events)
    events.sort(key=lambda x: x.started_at, reverse=False)
    return events


@app.get("/events/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[Event])
def read_events_fromto_year_month(
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

    cache = None
    if redis_url is not None:
        cache = EventRequestCache(url=redis_url)
    user_agent = get_user_agent(config)

    events = []
    try:
        if "scope" in config and "prefecture" in config["scope"]:
            prefecture = config["scope"]["prefecture"]
            events += ConnpassEventRequest(prefecture=prefecture, ym=ym,
                                           keyword=keyword, cache=cache,
                                           user_agent=user_agent
                                           ).get_events()
        if "scope" in config and "series_id" in config["scope"]:
            series_id = config["scope"]["series_id"]
            events += ConnpassEventRequest(series_id=series_id, ym=ym,
                                           keyword=keyword, cache=cache,
                                           user_agent=user_agent
                                           ).get_events()
    except ConnpassException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    events = Event.distinct_by_id(events)
    events.sort(key=lambda x: x.started_at, reverse=False)
    return events


@app.get("/events/full", response_model=List[EventDetail])
def read_events_full(keyword: str = None):
    return read_events(keyword)


@app.get("/events/full/today", response_model=List[EventDetail])
def read_events_full_today(keyword: str = None):
    return read_events_today(keyword)


@app.get("/events/full/in/{year}", response_model=List[EventDetail])
def read_events_full_in_year(
    year: int = Path(ge=2010, le=2040),
    keyword: str = None
):
    return read_events_in_year(year, keyword)


@app.get("/events/full/in/{year}/{month}", response_model=List[EventDetail])
def read_events_full_in_year_month(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return read_events_in_year_month(year, month, keyword)


@app.get("/events/full/in/{year}/{month}/{day}",
         response_model=List[EventDetail])
def read_events_full_in_year_month_day(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None
):
    return read_events_in_year_month_day(year, month, day, keyword)


@app.get("/events/full/from/{from_year}/{from_month}/to/{to_year}/{to_month}",
         response_model=List[EventDetail])
def read_events_full_fromto_year_month(
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return read_events_fromto_year_month(from_year, from_month,
                                         to_year, to_month, keyword)


def get_user_agent(config):
    if "api_client" in config and "user_agent" in config["api_client"]:
        version = config["metadata"]["version"]
        user_agent = config["api_client"]["user_agent"]
        user_agent = user_agent.replace("{version}", version)
        return user_agent
    return None

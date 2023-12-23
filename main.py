from fastapi import FastAPI, Path, HTTPException
from fastapi.responses import RedirectResponse
from connpass import ConnpassEventRequest
import datetime
import yaml

with open('config.yaml', 'r') as yml:
    config = yaml.safe_load(yml)

app = FastAPI(
    title=config["metadata"]["title"],
    description=config["metadata"]["description"],
    version=config["metadata"]["version"]
)


def distinct_by_key(data: list[dict], key: str) -> list[dict]:
    return list({element[key]: element for element in data}.values())


@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url='/docs')


@app.get("/events")
def read_events(keyword: str = None):
    days = 90
    now = datetime.datetime.now()
    dt_from = now - datetime.timedelta(days=days)
    dt_to = now + datetime.timedelta(days=days)
    return read_events_fromto_year_month(dt_from.year, dt_from.month,
                                         dt_to.year, dt_to.month, keyword)


@app.get("/events/today")
def read_events_today(keyword: str = None):
    now = datetime.datetime.now()
    return read_events_in_year_month_day(now.year, now.month, now.day, keyword)


@app.get("/events/{event_id}")
def read_event(
    event_id: int = Path(ge=1)
):
    connpass = ConnpassEventRequest(event_id=event_id)
    event = connpass.get_event()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/events/in/{year}")
def read_events_in_year(
    year: int = Path(ge=2010, le=2040),
    keyword: str = None
):
    return read_events_fromto_year_month(year, 1, year, 12, keyword)


@app.get("/events/in/{year}/{month}")
def read_events_in_year_month(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    keyword: str = None
):
    return read_events_fromto_year_month(year, month, year, month, keyword)


@app.get("/events/in/{year}/{month}/{day}")
def read_events_in_year_month_day(
    year: int = Path(ge=2010, le=2040),
    month: int = Path(ge=1, le=12),
    day: int = Path(ge=1, le=31),
    keyword: str = None
):
    ymd = [f"{year:04}{month:02}{day:02}"]
    events = []
    if "prefecture" in config:
        events += ConnpassEventRequest(prefecture=config["prefecture"],
                                       keyword=keyword,
                                       ymd=ymd).get_events()
    if "series_id" in config:
        events += ConnpassEventRequest(series_id=config["series_id"],
                                       keyword=keyword,
                                       ymd=ymd).get_events()
    events = distinct_by_key(events, "event_id")
    events.sort(key=lambda x: x["started_at"], reverse=False)
    return events


@app.get("/events/from/{from_year}/{from_month}/to/{to_year}/{to_month}")
def read_events_fromto_year_month(
    from_year: int = Path(ge=2010, le=2040),
    from_month: int = Path(ge=1, le=12),
    to_year: int = Path(ge=2010, le=2040),
    to_month: int = Path(ge=1, le=12),
    keyword: str = None
):
    if from_year > to_year or (from_year == to_year and from_month > to_month):
        raise HTTPException(status_code=400, detail="Invalid year/month")

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

    events = []
    if "prefecture" in config:
        events += ConnpassEventRequest(prefecture=config["prefecture"],
                                       keyword=keyword,
                                       ym=ym).get_events()
    if "series_id" in config:
        events += ConnpassEventRequest(series_id=config["series_id"],
                                       keyword=keyword,
                                       ym=ym).get_events()
    events = distinct_by_key(events, "event_id")
    events.sort(key=lambda x: x["started_at"], reverse=False)
    return events

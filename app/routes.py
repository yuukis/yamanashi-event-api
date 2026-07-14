from typing import List
from fastapi import BackgroundTasks, Path, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse, Response, JSONResponse
from fastapi_mcp import FastApiMCP
from . import service
from .models import Event, Group
from .models import GroupActivity, YearSummary, HeatmapBucket, EventsSummary
import hmac
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime

from .main import app

LIST_CACHE_CONTROL = "public, no-cache"


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    days = service.config["recent_days"] if "recent_days" in service.config else 90
    now = datetime.now()
    dt_from = now - timedelta(days=days)
    dt_to = now + timedelta(days=days)
    return await read_events_range(response, background_tasks,
                                   dt_from.year, dt_from.month,
                                   dt_to.year, dt_to.month,
                                   keyword, uid, fields, if_modified_since)


@app.get("/events/day/today", response_model=List[Event],
         operation_id="list_events_today",
         summary="List today's events")
async def read_events_day_today(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    today = datetime.now().date()
    return await read_events_for_days(response, background_tasks,
                                      today, 1, keyword, uid, fields,
                                      if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_day_today(response, background_tasks,
                                       keyword, uid, fields, if_modified_since)


@app.get("/events/week/this", response_model=List[Event],
         operation_id="list_events_this_week",
         summary="List this week's events")
async def read_events_this_week(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return await read_events_for_days(response, background_tasks,
                                      monday, 7, keyword, uid, fields,
                                      if_modified_since)


@app.get("/events/week/next", response_model=List[Event],
         operation_id="list_events_next_week",
         summary="List next week's events")
async def read_events_next_week(
    response: Response,
    background_tasks: BackgroundTasks,
    keyword: str = None,
    uid: str = None,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    today = datetime.now().date()
    next_monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    return await read_events_for_days(response, background_tasks,
                                      next_monday, 7, keyword, uid, fields,
                                      if_modified_since)


@app.get("/events/year/{year}", response_model=List[Event],
         operation_id="list_events_by_year",
         summary="List events in a specific year")
async def read_events_year(
    response: Response,
    background_tasks: BackgroundTasks,
    year: int = Path(ge=2010, le=2040),
    keyword: str = None,
    uid: str = None,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_range(response, background_tasks,
                                   year, 1, year, 12,
                                   keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_year(response, background_tasks, year,
                                  keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_range(response, background_tasks,
                                   year, month, year, month,
                                   keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_month(response, background_tasks, year, month,
                                   keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    ymd = [f"{year:04}{month:02}{day:02}"]
    events, last_modified = service.get_events(
        {"ymd": ymd, "keyword": keyword, "uid": uid}, background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_day(response, background_tasks, year, month, day,
                                 keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    if from_year > to_year or (from_year == to_year and from_month > to_month):
        raise HTTPException(status_code=400, detail="Invalid date range")

    ym = year_month_range(from_year, from_month, to_year, to_month)

    events, last_modified = service.get_events(
        {"ym": ym, "keyword": keyword, "uid": uid}, background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    return await read_events_range(response, background_tasks,
                                   from_year, from_month, to_year, to_month,
                                   keyword, uid, fields, if_modified_since)


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
    fields: str = None,
    if_modified_since: str = None
):
    ymd = [(base_date + timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
    events, last_modified = service.get_events(
        {"ymd": ymd, "keyword": keyword, "uid": uid}, background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               fields, if_modified_since)


def format_last_modified(last_modified: datetime) -> str:
    """Format as an RFC 7231 IMF-fixdate. Uses email.utils rather than
    strftime("%a"/"%b") since those directives are locale-dependent and
    would break HTTP date parsing under a non-English locale."""
    return format_datetime(last_modified, usegmt=True)


def is_not_modified(if_modified_since: str, last_modified) -> bool:
    """Compare the client's If-Modified-Since header against the resource's
    actual last-modified time. HTTP dates only carry second precision, so
    last_modified is truncated the same way before comparing."""
    if last_modified is None or if_modified_since is None:
        return False
    try:
        since = parsedate_to_datetime(if_modified_since)
    except (TypeError, ValueError):
        return False
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return last_modified.replace(microsecond=0) <= since


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
                        fields: str = None, if_modified_since: str = None):
    headers = {"Cache-Control": LIST_CACHE_CONTROL}
    if last_modified is not None:
        headers["Last-Modified"] = format_last_modified(last_modified)

    if is_not_modified(if_modified_since, last_modified):
        return Response(status_code=304, headers=headers)

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
    fields: str = None,
    if_modified_since: str = Header(None)
):
    groups, last_modified = service.get_groups({}, background_tasks)

    return build_list_response(response, groups, Group, last_modified,
                               fields, if_modified_since)


@app.get("/groups/{group_key}", response_model=Group,
         operation_id="get_group",
         summary="Get a single community group")
async def read_group(
    response: Response,
    background_tasks: BackgroundTasks,
    group_key: str,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    groups, last_modified = service.get_groups({}, background_tasks)
    group = next((g for g in groups if g.key == group_key), None)
    if group is None:
        raise HTTPException(status_code=404,
                            detail=f"Group '{group_key}' not found")

    headers = {"Cache-Control": LIST_CACHE_CONTROL}
    if last_modified is not None:
        headers["Last-Modified"] = format_last_modified(last_modified)

    if is_not_modified(if_modified_since, last_modified):
        return Response(status_code=304, headers=headers)

    filtered = filter_model_fields([group], Group, fields)
    if filtered is None:
        for key, value in headers.items():
            response.headers[key] = value
        return group

    return JSONResponse(content=filtered[0], headers=headers)


@app.get("/groups/{group_key}/events", response_model=List[Event],
         operation_id="list_group_events",
         summary="List events for a specific group")
async def read_group_events(
    response: Response,
    background_tasks: BackgroundTasks,
    group_key: str,
    keyword: str = None,
    uid: str = None,
    fields: str = None,
    if_modified_since: str = Header(None)
):
    if service.find_group_source(group_key) is None:
        raise HTTPException(status_code=404,
                            detail=f"Group '{group_key}' not found")

    # Unlike the date-scoped endpoints under /events, this URL carries no
    # period of its own, so it returns the group's full history rather
    # than silently applying the recent_days default.
    events, last_modified = service.get_events(
        {"keyword": keyword, "uid": uid, "group_key": group_key},
        background_tasks)

    return build_list_response(response, events, Event, last_modified,
                               fields, if_modified_since)


@app.get("/summary/events", response_model=EventsSummary,
         operation_id="summary_events",
         summary="Get yearly event summary with group highlights and activity heatmap")
async def read_events_summary(
    response: Response,
    background_tasks: BackgroundTasks,
    if_modified_since: str = Header(None)
):
    from_year = 2010
    to_year = datetime.now().year

    ym = [f"{y:04}{m:02}" for y in range(from_year, to_year + 1) for m in range(1, 13)]

    events, last_modified = service.get_events(
        {"ym": ym, "keyword": None},
        background_tasks,
        ex=3600*24*7,  # 7 days
        cache_ttl=3600*24)  # 24 hours
    groups, groups_last_modified = service.get_groups({}, background_tasks)
    group_by_key = {g.key: g for g in groups}

    if groups_last_modified is not None:
        last_modified = (groups_last_modified if last_modified is None
                         else max(last_modified, groups_last_modified))

    headers = {"Cache-Control": LIST_CACHE_CONTROL}
    if last_modified is not None:
        headers["Last-Modified"] = format_last_modified(last_modified)

    if is_not_modified(if_modified_since, last_modified):
        return Response(status_code=304, headers=headers)

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

    for key, value in headers.items():
        response.headers[key] = value
    return summary


@app.get("/events/summary", response_model=EventsSummary,
         operation_id="summary_events_legacy",
         summary="Get yearly event summary with group highlights and activity heatmap",
         description="Deprecated. Use GET /summary/events instead.",
         deprecated=True)
async def read_events_summary_legacy(
    response: Response,
    background_tasks: BackgroundTasks,
    if_modified_since: str = Header(None)
):
    return await read_events_summary(response, background_tasks, if_modified_since)


def verify_refresh_token(x_refresh_token: str = Header(None)):
    """Auth guard for POST /events/refresh. Fails closed (503) if no secret
    is configured, so the endpoint can never be reached by matching an empty
    token, and uses a constant-time comparison to avoid timing attacks."""
    if not service.events_refresh_token:
        raise HTTPException(status_code=503,
                            detail="Refresh endpoint is not configured")
    if not x_refresh_token or not hmac.compare_digest(
        x_refresh_token, service.events_refresh_token
    ):
        raise HTTPException(status_code=401,
                            detail="Invalid or missing refresh token")


def try_acquire_refresh_lock() -> bool:
    """Process-local minimum-interval lock, acquired before the upstream
    fetch so concurrent calls within the window are also rejected."""
    lock_key = "events-refresh-lock"
    if service.cache.get(lock_key) is not None:
        return False
    service.cache.set(lock_key, "1", ex=service.events_refresh_min_interval)
    return True


@app.post("/events/refresh", response_model=List[Event],
         operation_id="refresh_events",
         summary="Force-refresh recent events, bypassing cache",
         include_in_schema=False)
async def refresh_events(
    response: Response,
    _: None = Depends(verify_refresh_token)
):
    if not try_acquire_refresh_lock():
        raise HTTPException(status_code=429,
                            detail="Refresh already performed recently")

    days = service.config["recent_days"] if "recent_days" in service.config else 90
    now = datetime.now()
    dt_from = now - timedelta(days=days)
    dt_to = now + timedelta(days=days)
    ym = year_month_range(dt_from.year, dt_from.month, dt_to.year, dt_to.month)

    params = service.normalize_event_params(
        {"ym": ym, "keyword": None, "uid": None})
    events, last_modified = service.request_events(params, force_refresh=True)

    service.cache.set(params, Event.to_json(events), last_modified=last_modified,
                      ex=3600*72)  # 72 hours, matches GET /events' outer cache TTL

    response.headers["Cache-Control"] = "no-store"
    if last_modified is not None:
        response.headers["Last-Modified"] = format_last_modified(last_modified)
    return events


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
    "get_group",
    "list_group_events",
])
mcp.mount_http()

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from connpass import ConnpassEventRequest
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
def read_events():
    events = []
    if "prefecture" in config:
        events += ConnpassEventRequest(prefecture=config["prefecture"],
                                       months=6).get_events()
    if "series_id" in config:
        events += ConnpassEventRequest(series_ids=config["series_id"],
                                       months=6).get_events()
    events = distinct_by_key(events, "event_id")
    events.sort(key=lambda x: x["started_at"], reverse=True)
    return events


@app.get("/events/{event_id}")
def read_event(event_id: int):
    connpass = ConnpassEventRequest(event_id=event_id)
    event = connpass.get_event()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

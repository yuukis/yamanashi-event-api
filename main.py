from fastapi import FastAPI, HTTPException
from connpass import ConnpassEventRequest

app = FastAPI()

# 山梨県で開催されたIT勉強会コミュニティ
SERIES_IDS = [
    "1678",   # 日本Androidの会 山梨支部
    "4255",   # 子ども向けプログラミングクラブ コーダー道場甲府
    "5327",   # Redmineプラグインもくもく会 山梨
    "7069",   # shingen.py
    "7465",   # 子どものためのプログラミングクラブ CoderDojo北杜
    "7466",   # 子どものためのプログラミングクラブ CoderDojo韮崎
    "7759",   # 山梨IT同好会(仮)
    "9176",   # 富士もくもく会
    "10940",  # 山梨Web勉強会
    "11367"   # 山梨SPA
]


def distinct_by_key(data: list[dict], key: str) -> list[dict]:
    return list({element[key]: element for element in data}.values())


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/events")
def read_events():
    events1 = ConnpassEventRequest(prefecture="山梨県", months=6).get_events()
    events2 = ConnpassEventRequest(series_ids=SERIES_IDS, months=6).get_events()
    events = distinct_by_key(events1 + events2, "event_id")
    events.sort(key=lambda x: x["started_at"], reverse=True)
    return events


@app.get("/events/{event_id}")
def read_event(event_id: int):
    connpass = ConnpassEventRequest(prefecture="山梨県", event_id=event_id)
    event = connpass.get_event()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

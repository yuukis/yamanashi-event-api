from typing import Optional
from dataclasses import dataclass


@dataclass
class Event:
    event_id: int
    title: str
    catch: str
    hash_tag: str
    event_url: str
    started_at: str
    ended_at: str
    updated_at: str
    owner_name: str
    place: Optional[str]
    address: Optional[str]
    group_name: Optional[str]
    group_url: Optional[str]

    @staticmethod
    def distinct_by_id(data):
        return list({event.event_id: event for event in data}.values())


@dataclass
class EventDetail(Event):
    event_id: int
    title: str
    catch: str
    hash_tag: str
    event_url: str
    started_at: str
    ended_at: str
    updated_at: str
    limit: Optional[int]
    accepted: Optional[int]
    waiting: Optional[int]
    owner_name: str
    place: Optional[str]
    address: Optional[str]
    group_name: Optional[str]
    group_url: Optional[str]
    description: str
    lat: Optional[str]
    lon: Optional[str]

    def contains_keyword(self, keyword: str):
        if keyword is None:
            return True

        keyword = keyword.replace(",", " ").replace("　", " ")
        keywords = keyword.split()

        for k in keywords:
            k = k.lower()
            if not any([
                k in self.title.lower(),
                k in self.catch.lower(),
                k in self.owner_name.lower(),
                k in (self.place.lower() if self.place else ""),
                k in (self.address.lower() if self.address else ""),
                k in (self.group_name.lower() if self.group_name else ""),
                k in self.description.lower(),
            ]):
                return False

        return True

    @staticmethod
    def from_json(data: any):
        if isinstance(data, list):
            return [EventDetail.from_json(item) for item in data]

        if isinstance(data, dict):
            return EventDetail(
                event_id=data["event_id"],
                title=data["title"],
                catch=data["catch"],
                hash_tag=data["hash_tag"],
                event_url=data["event_url"],
                started_at=data["started_at"],
                ended_at=data["ended_at"],
                updated_at=data["updated_at"],
                limit=data["limit"],
                accepted=data["accepted"],
                waiting=data["waiting"],
                owner_name=data["owner_name"],
                place=data["place"],
                address=data["address"],
                group_name=data["group_name"],
                group_url=data["group_url"],
                description=data["description"],
                lat=data["lat"],
                lon=data["lon"]
            )

        raise ValueError("data must be EventDetail or List[EventDetail]")

    @staticmethod
    def to_json(data: any):
        if isinstance(data, list):
            return [EventDetail.to_json(item) for item in data]

        if isinstance(data, EventDetail):
            return {
                "event_id": data.event_id,
                "title": data.title,
                "catch": data.catch,
                "hash_tag": data.hash_tag,
                "event_url": data.event_url,
                "started_at": data.started_at,
                "ended_at": data.ended_at,
                "updated_at": data.updated_at,
                "limit": data.limit,
                "accepted": data.accepted,
                "waiting": data.waiting,
                "owner_name": data.owner_name,
                "place": data.place,
                "address": data.address,
                "group_name": data.group_name,
                "group_url": data.group_url,
                "description": data.description,
                "lat": data.lat,
                "lon": data.lon
            }

        raise ValueError("data must be EventDetail or List[EventDetail]")

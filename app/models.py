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
    group_key: Optional[str]
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
    group_key: Optional[str]
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
                k in (self.group_key.lower() if self.group_key else ""),
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
                group_key=data["group_key"],
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
                "group_key": data.group_key,
                "group_name": data.group_name,
                "group_url": data.group_url,
                "description": data.description,
                "lat": data.lat,
                "lon": data.lon
            }

        raise ValueError("data must be EventDetail or List[EventDetail]")


@dataclass
class Group:
    id: int
    key: str
    title: str
    sub_title: str
    url: str
    description: str
    owner_text: str
    image_url: str
    website_url: str
    x_username: str
    facebook_url: str
    member_users_count: int

    @staticmethod
    def from_json(data: any):
        if isinstance(data, list):
            return [Group.from_json(item) for item in data]

        if isinstance(data, dict):
            return Group(
                id=data["id"],
                key=data["key"],
                title=data["title"],
                sub_title=data["sub_title"],
                url=data["url"],
                description=data["description"],
                owner_text=data["owner_text"],
                image_url=data["image_url"],
                website_url=data["website_url"],
                x_username=data["x_username"],
                facebook_url=data["facebook_url"],
                member_users_count=data["member_users_count"]
            )

        raise ValueError("data must be Group or List[Group]")

    @staticmethod
    def to_json(data: any):
        if isinstance(data, list):
            return [Group.to_json(item) for item in data]

        if isinstance(data, Group):
            return {
                "id": data.id,
                "key": data.key,
                "title": data.title,
                "sub_title": data.sub_title,
                "url": data.url,
                "description": data.description,
                "owner_text": data.owner_text,
                "image_url": data.image_url,
                "website_url": data.website_url,
                "x_username": data.x_username,
                "facebook_url": data.facebook_url,
                "member_users_count": data.member_users_count
            }

        raise ValueError("data must be Group or List[Group]")

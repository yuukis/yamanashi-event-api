from typing import Optional
from dataclasses import dataclass


@dataclass
class Event:
    uid: str
    event_id: Optional[int]
    title: str
    catch: Optional[str]
    hash_tag: Optional[str]
    event_url: str
    started_at: str
    ended_at: str
    updated_at: str
    open_status: str
    owner_name: Optional[str]
    place: Optional[str]
    address: Optional[str]
    group_key: Optional[str]
    group_name: Optional[str]
    group_url: Optional[str]

    @staticmethod
    def distinct_by_uid(data):
        return list({event.uid: event for event in data}.values())


@dataclass
class EventDetail(Event):
    uid: str
    event_id: Optional[int]
    title: str
    catch: Optional[str]
    hash_tag: Optional[str]
    event_url: str
    started_at: str
    ended_at: str
    updated_at: str
    open_status: str
    limit: Optional[int]
    accepted: Optional[int]
    waiting: Optional[int]
    owner_name: Optional[str]
    place: Optional[str]
    address: Optional[str]
    group_key: Optional[str]
    group_name: Optional[str]
    group_url: Optional[str]
    description: Optional[str]
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
                k in (self.catch.lower() if self.catch else ""),
                k in (self.owner_name.lower() if self.owner_name else ""),
                k in (self.place.lower() if self.place else ""),
                k in (self.address.lower() if self.address else ""),
                k in (self.group_key.lower() if self.group_key else ""),
                k in (self.group_name.lower() if self.group_name else ""),
                k in (self.description.lower() if self.description else ""),
            ]):
                return False

        return True
    
    def is_valid(self):
        return all([
            self.uid,
            self.title,
            self.event_url,
            self.started_at,
            self.ended_at,
            self.updated_at,
            self.open_status
        ])

    @staticmethod
    def from_json(data: any):
        if isinstance(data, list):
            return [EventDetail.from_json(item) for item in data]

        if isinstance(data, dict):
            return EventDetail(
                uid=data["uid"],
                event_id=data.get("event_id"),
                title=data["title"],
                catch=data.get("catch"),
                hash_tag=data.get("hash_tag"),
                event_url=data["event_url"],
                started_at=data["started_at"],
                ended_at=data["ended_at"],
                updated_at=data["updated_at"],
                open_status=data["open_status"],
                limit=data.get("limit"),
                accepted=data.get("accepted"),
                waiting=data.get("waiting"),
                owner_name=data.get("owner_name"),
                place=data.get("place"),
                address=data.get("address"),
                group_key=data.get("group_key"),
                group_name=data.get("group_name"),
                group_url=data.get("group_url"),
                description=data.get("description"),
                lat=data.get("lat"),
                lon=data.get("lon")
            )

        raise ValueError("data must be EventDetail or List[EventDetail]")

    @staticmethod
    def to_json(data: any):
        if isinstance(data, list):
            return [EventDetail.to_json(item) for item in data]

        if isinstance(data, EventDetail):
            return {
                "uid": data.uid,
                "event_id": data.event_id,
                "title": data.title,
                "catch": data.catch,
                "hash_tag": data.hash_tag,
                "event_url": data.event_url,
                "started_at": data.started_at,
                "ended_at": data.ended_at,
                "updated_at": data.updated_at,
                "open_status": data.open_status,
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
    id: Optional[int]
    key: str
    title: str
    sub_title: Optional[str]
    url: Optional[str]
    description: Optional[str]
    owner_text: Optional[str]
    image_url: Optional[str]
    website_url: Optional[str]
    x_username: Optional[str]
    facebook_url: Optional[str]
    member_users_count: Optional[int]
    ical_url: Optional[str]

    @staticmethod
    def from_json(data: any):
        if isinstance(data, list):
            return [Group.from_json(item) for item in data]

        if isinstance(data, dict):
            return Group(
                id=data.get("id"),
                key=data["key"],
                title=data["title"],
                sub_title=data.get("sub_title"),
                url=data.get("url"),
                description=data.get("description"),
                owner_text=data.get("owner_text"),
                image_url=data.get("image_url"),
                website_url=data.get("website_url"),
                x_username=data.get("x_username"),
                facebook_url=data.get("facebook_url"),
                member_users_count=data.get("member_users_count"),
                ical_url=data.get("ical_url")
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
                "member_users_count": data.member_users_count,
                "ical_url": data.ical_url
            }

        raise ValueError("data must be Group or List[Group]")

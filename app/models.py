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

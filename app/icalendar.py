import requests
from icalendar import Calendar as IcalCalendar
from .models import EventDetail
from datetime import datetime, timezone


class IcalException(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


class IcalEventRequest:
    def __init__(self, url, key, name=None, image_url=None, group_url=None,
                 ym=None, ymd=None, cache=None):
        self.url = url
        self.key = key
        self.name = name
        self.image_url = image_url
        self.group_url = group_url
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd
        self.cache = cache
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)

    def get_events(self):
        url = self.url
        cache = self.cache
        ym = self.ym
        ymd = self.ymd

        try:
            content = self.__get_content_from_cache(url, cache)
            if content is None:
                content = self.__get_content(url)
                last_modified = datetime.now(timezone.utc)
                self.__set_content_to_cache(url, cache, content, last_modified)
            all_events = self.__parse_icalendar(content)
            selected_events = self.__find_by_ym_ymd(all_events, ym, ymd)
            return selected_events

        except requests.RequestException as e:
            raise IcalException(500, str(e))

        except IcalException as e:
            raise e

        except Exception as e:
            raise IcalException(500, str(e))

    def get_last_modified(self):
        return self.last_modified

    def __find_by_ym_ymd(self, events, ym, ymd):
        if len(ym) == 0 and len(ymd) == 0:
            return events

        selected = []
        for event in events:
            event_date = event.started_at[:10].replace("-", "")
            if event_date[:6] in self.ym or event_date in self.ymd:
                selected.append(event)
        return selected

    def __get_content_from_cache(self, url, cache):
        if cache is None:
            return None
        cache_content = cache.get(url)
        if cache_content is None:
            return None

        content_text = cache_content["content"]
        content = content_text.encode("utf-8")
        self.last_modified = cache_content["last_modified"]

        return content

    def __set_content_to_cache(self, url, cache, content, last_modified):
        if cache is None:
            return
        content_text = content.decode("utf-8")
        cache.set(url, content_text, last_modified=last_modified)

    def __get_content(self, url):
        print(f"Fetching content from {url}")
        response = requests.get(url)
        status_code = response.status_code
        if status_code != 200:
            raise IcalException(status_code, "Failed to fetch content")

        self.last_modified = datetime.now(timezone.utc)

        return response.content

    def __parse_icalendar(self, ical_str):
        cal = IcalCalendar.from_ical(ical_str)

        events = []
        for data in cal.walk("VEVENT"):
            dtstart = data.get("dtstart").dt
            dtend = data.get("dtend").dt
            open_status = self.__make_open_status(dtstart, dtend)

            event = EventDetail.from_json({
                "uid": data.get("uid"),
                "title": data.get("summary"),
                "event_url": data.get("url"),
                "started_at": dtstart.isoformat(),
                "ended_at": dtend.isoformat(),
                "updated_at": data.get("last-modified").dt.isoformat(),
                "open_status": open_status,
                "place": data.get("location"),
                "description": data.get("description"),
                "group_key": self.key,
                "group_name": self.name,
                "group_url": self.group_url,
            })
            events.append(event)

        return events

    def __make_open_status(self, dtstart, dtend):
        now = datetime.now(dtstart.tzinfo)
        if dtstart > now:
            return "preopen"
        elif dtend > now:
            return "open"
        else:
            return "close"

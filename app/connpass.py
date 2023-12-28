import requests
import re
from .models import EventDetail


class ConnpassException(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


class ConnpassEventRequest:
    def __init__(self, event_id=None, prefecture=None, series_id=None,
                 ym=None, ymd=None, keyword=None, cache=None, user_agent=None):
        self.url = "https://connpass.com/api/v1/event/"
        self.event_id = event_id
        self.prefecture = [] if prefecture is None else prefecture
        if keyword is None:
            self.keyword = []
        elif isinstance(keyword, str):
            self.keyword = keyword.split(",")
        else:
            self.keyword = keyword
        self.series_id = [] if series_id is None else series_id
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd
        self.cache = cache
        self.user_agent = user_agent

    def get_event(self):
        events = self.get_events()
        if len(events) == 0:
            return None
        return events[0]

    def get_events(self):
        params = {}
        if self.event_id is not None:
            params["event_id"] = self.event_id
        if len(self.prefecture) > 0:
            params["keyword_or"] = ",".join(self.prefecture)
        if len(self.series_id) > 0:
            params["series_id"] = ",".join(self.series_id)
        if len(self.ym) > 0:
            params["ym"] = ",".join(self.ym)
        if len(self.ymd) > 0:
            params["ymd"] = ",".join(self.ymd)
        if len(self.keyword) > 0:
            params["keyword"] = ",".join(self.keyword)

        page_size = 100
        params["count"] = page_size
        params["order"] = 2
        page = 0
        events = []
        while True:
            params["start"] = page * page_size + 1

            json = None
            if self.cache is not None:
                json = self.cache.get(params)
            if json is None:
                try:
                    response = self.__get(params)
                except ConnpassException as e:
                    raise e

                json = response.json()
                if self.cache is not None:
                    self.cache.set(params, json)
            events += EventDetail.from_json(json['events'])

            if json['results_returned'] < page_size:
                break
            page += 1

        if len(self.prefecture) > 0:
            events = list(filter(self.__is_in_pref, events))

        return events

    def __get(self, params):
        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent

        print({"params": params, "headers": headers})
        response = requests.get(self.url, headers=headers, params=params)

        if response.status_code != 200:
            status_code = response.status_code
            text = response.text
            title = re.search(r'<title>(.+?)</title>', text)
            message = title.group(1) if title else text
            raise ConnpassException(status_code, message)

        return response

    def __is_in_pref(self, event):
        if event.address is None:
            return False

        for pref in self.prefecture:
            if pref in event.address:
                return True

        return False

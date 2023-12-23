import requests


class ConnpassEventRequest:

    def __init__(self, event_id=None, prefecture="", series_id=None,
                 ym=None, ymd=None, keyword=None):
        self.url = "https://connpass.com/api/v1/event/"
        self.event_id = event_id
        self.prefecture = prefecture
        self.keyword = [] if keyword is None else keyword
        self.series_id = [] if series_id is None else series_id
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd

    def get_event(self):
        events = self.get_events()
        if len(events) == 0:
            return None
        return events[0]

    def get_events(self):
        params = {}
        if self.event_id is not None:
            params["event_id"] = self.event_id
        if self.prefecture != "":
            self.keyword.append(self.prefecture)
        if len(self.keyword) > 0:
            params["keyword"] = ",".join(self.keyword)
        if len(self.series_id) > 0:
            params["series_id"] = ",".join(self.series_id)
        if len(self.ym) > 0:
            params["ym"] = ",".join(self.ym)
        if len(self.ymd) > 0:
            params["ymd"] = ",".join(self.ymd)

        page_size = 100
        params["count"] = page_size
        params["order"] = 2
        page = 0
        events = []
        while True:
            params["start"] = page * page_size + 1
            response = self.__get(params)
            json = response.json()
            events += json['events']

            if json['results_returned'] < page_size:
                break
            page += 1

        if self.prefecture != "":
            events = list(filter(self.__is_in_pref, events))

        return events

    def __get(self, params):
        headers = {
            "User-Agent": "YamanashiEventApiBot/1.0"
        }
        response = requests.get(self.url, headers=headers, params=params)
        return response

    def __is_in_pref(self, event):
        if event["address"] is None:
            return False
        return event["address"].startswith(self.prefecture)

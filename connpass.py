import requests
import datetime


class ConnpassEventRequest:

    def __init__(self, event_id=None, prefecture="", series_id=None,
                 ym=None, ymd=None, keyword=None, months=None):
        self.url = "https://connpass.com/api/v1/event/"
        self.event_id = event_id
        self.prefecture = prefecture
        if keyword is None:
            self.keyword = []
        else:
            self.keyword = keyword
        if series_id is None:
            self.series_id = []
        else:
            self.series_id = series_id
        if ym is None:
            self.ym = []
        else:
            self.ym = ym
        if ymd is None:
            self.ymd = []
        else:
            self.ymd = ymd
        self.months = months

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
        if self.months is not None:
            delta = self.months
            ym_array = []
            now = datetime.datetime.now()
            for i in range(-delta, delta + 1):
                y = now.year
                m = now.month + i - 1
                if m < 0:
                    y -= 1
                elif m >= 12:
                    y += 1
                m = m % 12
                dt = datetime.datetime(y, m + 1, 1)
                ym_array.append(dt.strftime("%Y%m"))
            params["ym"] = ",".join(ym_array)

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

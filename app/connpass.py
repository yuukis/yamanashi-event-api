import requests
import re
import time
from datetime import datetime, timezone
from .models import EventDetail, Group


class ConnpassException(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


class ConnpassEventRequest:
    def __init__(self, event_id=None, prefecture=None, subdomain=None,
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
        self.subdomain = [] if subdomain is None else subdomain
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd
        self.cache = cache
        self.user_agent = user_agent
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)

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
        if len(self.subdomain) > 0:
            params["subdomain"] = ",".join(self.subdomain)
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
                response = self.cache.get(params)
                if response is not None:
                    json = response["content"]
                    last_modified = response["last_modified"]
            if json is None:
                try:
                    response = self.__get(params)
                except ConnpassException as e:
                    raise e

                json = response.json()
                last_modified = datetime.now(timezone.utc)
                if self.cache is not None:
                    self.cache.set(params, json, last_modified=last_modified)
            events += self.__convert_to_events(json['events'])

            if last_modified is not None:
                self.last_modified = max(self.last_modified, last_modified)

            if json['results_returned'] < page_size:
                break
            page += 1

        if len(self.prefecture) > 0:
            events = list(filter(self.__is_in_pref, events))

        return events

    def get_last_modified(self):
        return self.last_modified

    def __get(self, params):
        if self.cache is not None:
            while True:
                wait_sec = self.cache.get_wait_for_request()
                if wait_sec == 0:
                    break
                time.sleep(wait_sec)
            self.cache.set_wait_for_request(5)

        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent

        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        print({"params": params, "headers": headers, "url": self.url,
               "date": date_str})
        response = requests.get(self.url, headers=headers, params=params)

        if self.cache is not None:
            self.cache.set_wait_for_request(5)

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

    def __convert_to_events(self, json: dict):
        events = []

        for item in json:
            series_title = None
            series_url = None
            if item["series"] is not None:
                series_subdomain = item["series"]["subdomain"]
                series_title = item["series"]["title"]
                series_url = item["series"]["url"]

            events.append(
                EventDetail(
                    event_id=item["id"],
                    title=item["title"],
                    catch=item["catch"],
                    hash_tag=item["hash_tag"],
                    event_url=item["url"],
                    started_at=item["started_at"],
                    ended_at=item["ended_at"],
                    updated_at=item["updated_at"],
                    limit=item["limit"],
                    accepted=item["accepted"],
                    waiting=item["waiting"],
                    owner_name=item["owner_display_name"],
                    place=item["place"],
                    address=item["address"],
                    group_key=series_subdomain,
                    group_name=series_title,
                    group_url=series_url,
                    description=item["description"],
                    lat=item["lat"],
                    lon=item["lon"]
                )
            )
        return events


class ConnpassGroupRequest:
    def __init__(self, subdomain=None, cache=None, user_agent=None):
        self.url = "https://connpass.com/api/v1/group/"
        self.subdomain = subdomain
        self.cache = cache
        self.user_agent = user_agent
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)

    def get_group(self):
        groups = self.get_groups()
        if len(groups) == 0:
            return None
        return groups[0]

    def get_groups(self):
        params = {}
        if self.subdomain is not None:
            params["subdomain"] = self.subdomain

        page_size = 100
        params["count"] = page_size
        page = 0
        groups = []
        while True:
            params["start"] = page * page_size + 1

            json = None
            if self.cache is not None:
                response = self.cache.get(params)
                if response is not None:
                    json = response["content"]
                    last_modified = response["last_modified"]
            if json is None:
                try:
                    response = self.__get(params)
                except ConnpassException as e:
                    raise e

                json = response.json()
                last_modified = datetime.now(timezone.utc)
                if self.cache is not None:
                    self.cache.set(params, json, last_modified=last_modified)
            groups += self.__convert_to_groups(json['groups'])

            if last_modified is not None:
                self.last_modified = max(self.last_modified, last_modified)

            if json['results_returned'] < page_size:
                break
            page += 1

        return groups

    def get_last_modified(self):
        return self.last_modified

    def __get(self, params):
        if self.cache is not None:
            while True:
                wait_sec = self.cache.get_wait_for_request()
                if wait_sec == 0:
                    break
                time.sleep(wait_sec)
            self.cache.set_wait_for_request(5)

        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent

        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        print({"params": params, "headers": headers, "url": self.url,
               "date": date_str})
        response = requests.get(self.url, headers=headers, params=params)

        if self.cache is not None:
            self.cache.set_wait_for_request(5)

        if response.status_code != 200:
            status_code = response.status_code
            text = response.text
            title = re.search(r'<title>(.+?)</title>', text)
            message = title.group(1) if title else text
            raise ConnpassException(status_code, message)

        return response

    def __convert_to_groups(self, json: dict):
        groups = []

        for item in json:
            groups.append(
                Group(
                    id=item["id"],
                    key=item["subdomain"],
                    title=item["title"],
                    sub_title=item["sub_title"],
                    url=item["url"],
                    description=item["description"],
                    owner_text=item["owner_text"],
                    image_url=item["image_url"],
                    website_url=item["website_url"],
                    x_username=item["twitter_username"],
                    facebook_url=item["facebook_url"],
                    member_users_count=item["member_users_count"]
                )
            )
        return groups

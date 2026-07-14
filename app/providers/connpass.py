import requests
import re
import time
from datetime import datetime, timezone
from ..models import Event, Group


class ConnpassException(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


class ConnpassEventRequest:
    # Fixed so get_events() and get_events_page() always request the same
    # (subdomain, start, count) params, sharing cache entries between them.
    PAGE_SIZE = 100

    def __init__(self, event_id=None, prefecture=None, subdomain=None,
                 ym=None, ymd=None, keyword=None, cache=None,
                 api_key=None, user_agent=None, cache_ttl=3600,
                 skip_cache=False):
        self.url = "https://connpass.com/api/v2/events/"
        self.api_key = api_key
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
        self.api_key = api_key
        self.user_agent = user_agent
        self.cache_ttl = cache_ttl
        self.skip_cache = skip_cache
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)
        self.total_available = None

    def get_event(self):
        events = self.get_events()
        if len(events) == 0:
            return None
        return events[0]

    def get_events(self):
        events = []
        chunk = 0
        while True:
            chunk_events, results_returned = self.__fetch_chunk(chunk)
            events += chunk_events
            if results_returned < self.PAGE_SIZE:
                break
            chunk += 1

        if len(self.prefecture) > 0:
            events = list(filter(self.__is_in_pref, events))

        return events

    def get_events_page(self, item_start: int, item_count: int, order: str = "desc"):
        """Return events [item_start, item_start + item_count) (1-indexed),
        fetching only the PAGE_SIZE-aligned chunks that cover it.
        order="desc" is connpass's native order; "asc" mirrors the range
        onto it (needs the total count first) and reverses the result."""
        if order == "asc":
            self.__fetch_chunk(0)
            total = self.total_available or 0
            if item_start > total:
                return []
            desc_start = max(total - item_start - item_count + 2, 1)
            desc_count = min(item_count, total - item_start + 1)
            events = self.__fetch_range(desc_start, desc_count)
            events.reverse()
            return events

        return self.__fetch_range(item_start, item_count)

    def __fetch_range(self, item_start: int, item_count: int):
        item_end = item_start + item_count - 1
        first_chunk = (item_start - 1) // self.PAGE_SIZE
        last_chunk = (item_end - 1) // self.PAGE_SIZE

        events = []
        chunk = first_chunk
        while chunk <= last_chunk:
            chunk_events, results_returned = self.__fetch_chunk(chunk)
            events += chunk_events
            if results_returned < self.PAGE_SIZE:
                break
            chunk += 1

        if len(self.prefecture) > 0:
            events = list(filter(self.__is_in_pref, events))

        offset = item_start - 1 - first_chunk * self.PAGE_SIZE
        return events[offset:offset + item_count]

    def __fetch_chunk(self, chunk_index: int):
        """Fetch one PAGE_SIZE-aligned chunk; returns (events, results_returned)."""
        params = self.__query_params()
        params["count"] = self.PAGE_SIZE
        params["order"] = 2
        params["start"] = chunk_index * self.PAGE_SIZE + 1

        json = self.__fetch_json(params)
        self.total_available = json.get('results_available')
        return self.__convert_to_events(json['events']), json['results_returned']

    def get_last_modified(self):
        return self.last_modified

    def get_total_available(self):
        """Total results matching the query's filters; set after get_events()/get_events_page()."""
        return self.total_available

    def __query_params(self):
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
        return params

    def __fetch_json(self, params):
        json = None
        last_modified = None
        if self.cache is not None and not self.skip_cache:
            response = self.cache.get(params)
            if response is not None:
                json = response["json"]
                last_modified = response["last_modified"]
        if json is None:
            # peek() is read regardless of skip_cache: last_modified
            # should reflect when the data actually last changed, not
            # merely when it was last checked, so even a forced refresh
            # still needs the previous value to compare against.
            # skip_cache only bypasses using the cache to serve a
            # response, not this comparison.
            previous = self.cache.peek(params) if self.cache is not None else None
            try:
                response = self.__get(params)
            except ConnpassException as e:
                raise e

            json = response.json()
            last_modified = self.__resolve_last_modified(previous, json)
            if self.cache is not None:
                self.cache.set(params, json, last_modified=last_modified,
                               ex=self.cache_ttl)

        if last_modified is not None:
            self.last_modified = max(self.last_modified, last_modified)

        return json

    def __resolve_last_modified(self, previous, json):
        """Reuse the previously cached last_modified for this page if the
        freshly fetched content is identical to it, rather than always
        stamping "now" -- otherwise every periodic refetch would look
        modified even when nothing actually changed upstream."""
        if previous is not None and previous["last_modified"] is not None \
                and previous["json"] == json:
            return previous["last_modified"]
        return datetime.now(timezone.utc)

    def __get(self, params):
        if self.cache is not None:
            while True:
                wait_sec = self.cache.get_wait_for_request()
                if wait_sec == 0:
                    break
                time.sleep(wait_sec)
            self.cache.set_wait_for_request(1)

        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent
        if self.api_key is not None:
            headers["X-API-Key"] = self.api_key

        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        print({"params": params, "url": self.url, "date": date_str})
        response = requests.get(self.url, headers=headers, params=params)

        if self.cache is not None:
            self.cache.set_wait_for_request(1)

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
            event_id = item["id"]
            uid = f"event_{event_id}@connpass.com"
            group_subdomain = None
            group_title = None
            group_url = None
            if item["group"] is not None:
                group_subdomain = item["group"]["subdomain"]
                group_title = item["group"]["title"]
                group_url = item["group"]["url"]

            events.append(
                Event(
                    uid=uid,
                    event_id=event_id,
                    title=item["title"],
                    catch=item["catch"],
                    hash_tag=item["hash_tag"],
                    event_url=item["url"],
                    started_at=item["started_at"],
                    ended_at=item["ended_at"],
                    updated_at=item["updated_at"],
                    open_status=item["open_status"],
                    limit=item["limit"],
                    accepted=item["accepted"],
                    waiting=item["waiting"],
                    owner_name=item["owner_display_name"],
                    place=item["place"],
                    address=item["address"],
                    group_key=group_subdomain,
                    group_name=group_title,
                    group_url=group_url,
                    description=item["description"],
                    lat=item["lat"],
                    lon=item["lon"]
                )
            )
        return events


class ConnpassGroupRequest:
    def __init__(self, subdomain=None, cache=None, api_key=None,
                 user_agent=None):
        self.url = "https://connpass.com/api/v2/groups/"
        self.subdomain = subdomain
        self.cache = cache
        self.api_key = api_key
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
                    json = response["json"]
                    last_modified = response["last_modified"]
            if json is None:
                previous = self.cache.peek(params) if self.cache is not None else None
                try:
                    response = self.__get(params)
                except ConnpassException as e:
                    raise e

                json = response.json()
                last_modified = self.__resolve_last_modified(previous, json)
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

    def __resolve_last_modified(self, previous, json):
        """Reuse the previously cached last_modified for this page if the
        freshly fetched content is identical to it, rather than always
        stamping "now" -- otherwise every periodic refetch would look
        modified even when nothing actually changed upstream."""
        if previous is not None and previous["last_modified"] is not None \
                and previous["json"] == json:
            return previous["last_modified"]
        return datetime.now(timezone.utc)

    def __get(self, params):
        if self.cache is not None:
            while True:
                wait_sec = self.cache.get_wait_for_request()
                if wait_sec == 0:
                    break
                time.sleep(wait_sec)
            self.cache.set_wait_for_request(1)

        headers = {}
        if self.user_agent is not None:
            headers["User-Agent"] = self.user_agent
        if self.api_key is not None:
            headers["X-API-Key"] = self.api_key

        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        print({"params": params, "url": self.url, "date": date_str})
        response = requests.get(self.url, headers=headers, params=params)

        if self.cache is not None:
            self.cache.set_wait_for_request(1)

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
                    member_users_count=item["member_users_count"],
                    ical_url=None
                )
            )
        return groups

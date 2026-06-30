import requests
from datetime import datetime, timezone
from .models import EventDetail, Group


class ArchiveException(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


class ArchiveIndexRequest:
    def __init__(self, url, ym=None, ymd=None, cache=None):
        self.url = url
        self.ym = [] if ym is None else ym
        self.ymd = [] if ymd is None else ymd
        self.cache = cache
        self.last_modified = datetime.fromtimestamp(0, timezone.utc)

    def get_events(self):
        try:
            json = self.__get_json_from_cache()
            if json is None:
                json = self.__get_json()
                last_modified = datetime.now(timezone.utc)
                self.__set_json_to_cache(json, last_modified)

            events = EventDetail.from_json(json.get("events", []))
            return self.__find_by_ym_ymd(events)

        except requests.RequestException as e:
            raise ArchiveException(500, str(e))

        except ArchiveException as e:
            raise e

        except Exception as e:
            raise ArchiveException(500, str(e))

    def get_groups(self):
        try:
            json = self.__get_json_from_cache()
            if json is None:
                json = self.__get_json()
                last_modified = datetime.now(timezone.utc)
                self.__set_json_to_cache(json, last_modified)

            source = json.get("source", {})
            archive_source = source.get("name")
            archive_url = source.get("url")
            communities = []
            for community in json.get("communities", []):
                item = community.copy()
                item["archive_source"] = item.get("archive_source",
                                                  archive_source)
                item["archive_url"] = item.get("archive_url", archive_url)
                communities.append(item)

            return Group.from_json(communities)

        except requests.RequestException as e:
            raise ArchiveException(500, str(e))

        except ArchiveException as e:
            raise e

        except Exception as e:
            raise ArchiveException(500, str(e))

    def get_last_modified(self):
        return self.last_modified

    def preload(self):
        try:
            json = self.__get_json_from_cache()
            if json is None:
                json = self.__get_json()
                last_modified = datetime.now(timezone.utc)
                self.__set_json_to_cache(json, last_modified)

        except requests.RequestException as e:
            raise ArchiveException(500, str(e))

        except ArchiveException as e:
            raise e

        except Exception as e:
            raise ArchiveException(500, str(e))

    def __find_by_ym_ymd(self, events):
        if len(self.ym) == 0 and len(self.ymd) == 0:
            return events

        selected = []
        for event in events:
            event_date = event.started_at[:10].replace("-", "")
            if event_date[:6] in self.ym or event_date in self.ymd:
                selected.append(event)
        return selected

    def __get_json_from_cache(self):
        if self.cache is None:
            return None
        cache_content = self.cache.get(self.__cache_key())
        if cache_content is None:
            return None

        self.last_modified = cache_content["last_modified"]
        return cache_content["json"]

    def __set_json_to_cache(self, json, last_modified):
        if self.cache is None:
            return
        self.cache.set(self.__cache_key(), json, last_modified=last_modified,
                       ex=None)

    def __get_json(self):
        print(f"Fetching archive index from {self.url}")
        response = requests.get(self.url)
        status_code = response.status_code
        if status_code != 200:
            raise ArchiveException(status_code, "Failed to fetch archive index")

        self.last_modified = datetime.now(timezone.utc)
        return response.json()

    def __cache_key(self):
        return {"archive_index_url": self.url}

from redis import Redis
from typing import Tuple
import hashlib
import json
import datetime


class EventRequestCache:

    def __init__(self, url="redis://localhost:6379", prefix="event-request:"):
        self._redis = Redis.from_url(url=url)
        self._prefix = prefix

    def get(self, request_params) -> dict:
        return self.get_with_last_modified(request_params)[0]

    def get_with_last_modified(self, request_params) -> Tuple[dict, str]:
        key = self.generate_key(request_params)
        message = self._redis.get(key)
        if message is None:
            return None, None

        key_last_modified = key + ":last_modified"
        last_modified = self._redis.get(key_last_modified)
        if last_modified is not None and isinstance(last_modified, bytes):
            last_modified = last_modified.decode()
        return json.loads(message), last_modified

    def set(self, request_params, response_json, ex=3600):
        key = self.generate_key(request_params)
        message = json.dumps(response_json, sort_keys=True)
        self._redis.set(key, message, ex)

        key_last_modified = key + ":last_modified"
        now = datetime.datetime.now(datetime.timezone.utc)
        last_modified = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        self._redis.set(key_last_modified, last_modified, ex)

    def generate_key(self, params) -> str:
        json_text = json.dumps(params, sort_keys=True)
        key_sha256 = hashlib.sha256(json_text.encode())
        key = self._prefix + key_sha256.hexdigest()
        return key

    def get_wait_for_request(self) -> int:
        key = "request_wait_sec"
        ttl = self._redis.ttl(key)
        if ttl == -2:
            return 0
        return ttl

    def set_wait_for_request(self, wait_sec: int):
        key = "request_wait_sec"
        date = datetime.datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        self._redis.set(key, date_str, ex=wait_sec)

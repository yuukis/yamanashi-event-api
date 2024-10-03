from redis import Redis
import hashlib
import json
from datetime import datetime, timezone


class EventRequestCache:

    def __init__(self, url="redis://localhost:6379", prefix="event-request:"):
        self._redis = Redis.from_url(url=url)
        self._prefix = prefix

    def get(self, request_params) -> dict:
        key = self.generate_key(request_params)
        key_content = key + ":content"
        content = self._redis.get(key_content)
        if content is None:
            return None

        key_last_modified = key + ":last_modified"
        last_modified = None
        ts = self._redis.get(key_last_modified)
        if ts is not None:
            last_modified = datetime.fromtimestamp(int(ts), tz=timezone.utc)

        return {
            "content": json.loads(content),
            "last_modified": last_modified
        }

    def set(self, request_params, response_json, last_modified=None, ex=3600):
        key = self.generate_key(request_params)
        content = json.dumps(response_json, sort_keys=True)

        key_content = key + ":content"
        self._redis.set(key_content, content, ex)

        if last_modified is not None:
            key_last_modified = key + ":last_modified"
            ts = int(last_modified.timestamp())
            self._redis.set(key_last_modified, ts, ex)

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
        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        self._redis.set(key, date_str, ex=wait_sec)

from redis import Redis
import hashlib
import json
import datetime


class EventRequestCache:

    def __init__(self, url="redis://localhost:6379", prefix="event-request:"):
        self._redis = Redis.from_url(url=url)
        self._prefix = prefix

    def get(self, request_params) -> dict:
        key = self.generate_key(request_params)
        message = self._redis.get(key)
        if message is None:
            return None

        return json.loads(message)

    def set(self, request_params, response_json, ex=3600):
        key = self.generate_key(request_params)
        message = json.dumps(response_json, sort_keys=True)
        self._redis.set(key, message, ex)

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

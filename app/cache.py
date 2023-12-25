from redis import Redis
import hashlib
import json


class EventRequestCache:

    def __init__(self, url="redis://localhost:6379", prefix="request_"):
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

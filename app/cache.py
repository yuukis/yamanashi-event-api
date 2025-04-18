import hashlib
import json
import math
from datetime import datetime, timezone


class EventRequestCache:

    def __init__(self, prefix="event-request:"):
        self._prefix = prefix
        self._store = {}
        self._expiry = {}

    def get(self, key_data) -> dict | None:
        key = self.generate_key(key_data)
        key_content = key + ":content"
        key_last_modified = key + ":last_modified"

        if not self._is_valid(key_content):
            return None

        content = self._store.get(key_content)
        last_modified = self._store.get(key_last_modified)

        if content is None:
            return None

        last_modified_dt = None
        if last_modified is not None:
            last_modified_dt = datetime.fromtimestamp(int(last_modified),
                                                      timezone.utc)

        json_data = None
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            pass

        return {
            "content": content,
            "json": json_data,
            "last_modified": last_modified_dt
        }

    def set(self, key_data, response_data, last_modified=None, ex=3600):
        key = self.generate_key(key_data)
        if isinstance(response_data, dict) or isinstance(response_data, list):
            content = json.dumps(response_data, sort_keys=True)
        elif isinstance(response_data, str):
            content = response_data
        else:
            raise ValueError("Invalid data type for cache content")

        key_content = key + ":content"
        key_last_modified = key + ":last_modified"

        self._store[key_content] = content
        self._expiry[key_content] = datetime.now(timezone.utc).timestamp() + ex

        if last_modified is not None:
            ts = int(last_modified.timestamp())
            self._store[key_last_modified] = ts
            expiry = datetime.now(timezone.utc).timestamp() + ex
            self._expiry[key_last_modified] = expiry

    def generate_key(self, data) -> str:
        if isinstance(data, dict):
            text = json.dumps(data, sort_keys=True)
        elif isinstance(data, str):
            text = data
        else:
            raise ValueError("Invalid data type for key generation")

        key_sha256 = hashlib.sha256(text.encode())
        key = self._prefix + key_sha256.hexdigest()
        return key

    def get_wait_for_request(self) -> int:
        key = "request_wait_sec"

        if not self._is_valid(key):
            return 0

        ttl = self._expiry.get(key, 0) - datetime.now(timezone.utc).timestamp()
        return max(0, math.ceil(ttl))

    def set_wait_for_request(self, wait_sec: int):
        key = "request_wait_sec"
        date = datetime.now()
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')

        self._store[key] = date_str
        self._expiry[key] = datetime.now(timezone.utc).timestamp() + wait_sec

    def _is_valid(self, key: str) -> bool:
        if key not in self._expiry:
            return False
        if datetime.now(timezone.utc).timestamp() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return True

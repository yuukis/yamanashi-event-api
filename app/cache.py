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

        if not self._is_valid(key_content):
            return None

        return self._read(key)

    def peek(self, key_data) -> dict | None:
        """Like get(), but ignores TTL expiry and returns whatever is
        currently stored (possibly stale), or None if nothing has ever been
        cached for this key. Used to compare a freshly fetched value
        against the last cached one, so last_modified can be preserved
        when the content hasn't actually changed."""
        key = self.generate_key(key_data)
        return self._read(key)

    def _read(self, key: str) -> dict | None:
        key_content = key + ":content"
        key_last_modified = key + ":last_modified"

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
        if ex is None:
            self._expiry[key_content] = None
        else:
            self._expiry[key_content] = datetime.now(timezone.utc).timestamp() + ex

        if last_modified is not None:
            ts = int(last_modified.timestamp())
            self._store[key_last_modified] = ts
            if ex is None:
                self._expiry[key_last_modified] = None
            else:
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
        if self._expiry[key] is None:
            return True
        # Deliberately doesn't delete the entry on expiry: peek() relies on
        # stale entries staying readable so a fresh fetch can be compared
        # against them. A future set() for the same key overwrites it.
        return datetime.now(timezone.utc).timestamp() <= self._expiry[key]

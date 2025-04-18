import unittest
from app.cache import EventRequestCache
from datetime import datetime, timezone


class TestEventRequestCache(unittest.TestCase):

    def setUp(self):
        self.cache = EventRequestCache(prefix="request_")

    def test_get_existing_key1(self):
        self.cache._store = {}
        self.cache._expiry = {}

        self.cache.set({"param": "value"}, {"key": "value"}, ex=3600)

        response = self.cache.get({"param": "value"})
        content = response["content"]
        json = response["json"]
        last_modified = response["last_modified"]

        self.assertEqual(content, '{"key": "value"}')
        self.assertEqual(json, {"key": "value"})
        self.assertIsNone(last_modified)

    def test_get_existing_key2(self):
        self.cache._store = {}
        self.cache._expiry = {}

        dt = datetime.fromtimestamp(123, timezone.utc)
        self.cache.set({"param": "value"}, {"key": "value"}, last_modified=dt,
                       ex=3600)
        
        response = self.cache.get({"param": "value"})
        content = response["content"]
        json = response["json"]
        last_modified = response["last_modified"]

        self.assertEqual(content, '{"key": "value"}')
        self.assertEqual(json, {"key": "value"})
        self.assertEqual(last_modified, dt)

    def test_get_non_existing_key(self):
        self.cache._store = {}
        self.cache._expiry = {}

        response = self.cache.get({"param": "value"})

        self.assertIsNone(response)

    def test_set(self):
        self.cache._store = {}
        self.cache._expiry = {}

        self.cache.set({"param": "value"}, {"key": "value"}, ex=3600)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"

        self.assertEqual(self.cache._store[expected_key], '{"key": "value"}')
        self.assertIn(expected_key, self.cache._expiry)

    def test_set_with_last_modified(self):
        self.cache._store = {}
        self.cache._expiry = {}

        dt = datetime.fromtimestamp(123, timezone.utc)

        self.cache.set({"param": "value"}, {"key": "value"}, last_modified=dt,
                       ex=3600)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"
        expected_last_modified = "request_5647d15eb1d32d1548f1504fcc64134946" \
                                 + "cd1c401c87bb9636b34606441b8ae6" \
                                 + ":last_modified"

        self.assertEqual(self.cache._store[expected_key], '{"key": "value"}')
        self.assertIn(expected_key, self.cache._expiry)
        self.assertEqual(self.cache._store[expected_last_modified], 123)
        self.assertIn(expected_last_modified, self.cache._expiry)

    def test_generate_key(self):
        params = {"param": "value"}

        key = self.cache.generate_key(params)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.assertEqual(key, expected_key)


if __name__ == '__main__':
    unittest.main()

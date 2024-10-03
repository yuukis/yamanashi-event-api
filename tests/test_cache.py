import unittest
from unittest.mock import MagicMock
from app.cache import EventRequestCache
from datetime import datetime


class TestEventRequestCache(unittest.TestCase):

    def setUp(self):
        self.cache = EventRequestCache(url="redis://localhost:6379",
                                       prefix="request_")

    def test_get_existing_key(self):
        # Mocking Redis.get method to return a response
        self.cache._redis.get = MagicMock(side_effect=['{"key": "value"}',
                                                       123])

        response = self.cache.get({"param": "value"})
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"
        content = response["content"]
        last_modified = response["last_modified"]

        self.assertEqual(content, {"key": "value"})
        self.cache._redis.get.assert_any_call(expected_key)

        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:last_modified"
        self.assertEqual(last_modified, datetime.fromtimestamp(123))
        self.cache._redis.get.assert_any_call(expected_key)

    def test_get_non_existing_key(self):
        # Mocking Redis.get method to return None
        self.cache._redis.get = MagicMock(return_value=None)

        response = self.cache.get({"param": "value"})
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"

        self.assertIsNone(response)
        self.cache._redis.get.assert_called_once_with(expected_key)

    def test_set(self):
        # Mocking Redis.set method
        self.cache._redis.set = MagicMock()

        self.cache.set({"param": "value"}, {"key": "value"}, ex=3600)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"

        self.cache._redis.set.assert_called_once_with(expected_key,
                                                      '{"key": "value"}', 3600)

    def test_set_with_last_modified(self):
        # Mocking Redis.set method
        self.cache._redis.set = MagicMock()

        dt = datetime.fromtimestamp(123)

        self.cache.set({"param": "value"}, {"key": "value"}, last_modified=dt,
                       ex=3600)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6:content"
        expected_last_modified = "request_5647d15eb1d32d1548f1504fcc64134946" \
                                 + "cd1c401c87bb9636b34606441b8ae6" \
                                 + ":last_modified"

        self.cache._redis.set.assert_any_call(expected_key, '{"key": "value"}',
                                              3600)
        self.cache._redis.set.assert_any_call(expected_last_modified, 123,
                                              3600)

    def test_generate_key(self):
        params = {"param": "value"}

        key = self.cache.generate_key(params)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.assertEqual(key, expected_key)


if __name__ == '__main__':
    unittest.main()

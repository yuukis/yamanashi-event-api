import unittest
from unittest.mock import MagicMock
from app.cache import EventRequestCache


class TestEventRequestCache(unittest.TestCase):

    def setUp(self):
        self.cache = EventRequestCache(url="redis://localhost:6379",
                                       prefix="request_")

    def test_get_existing_key(self):
        # Mocking Redis.get method to return a response
        self.cache._redis.get = MagicMock(return_value='{"key": "value"}')

        response = self.cache.get({"param": "value"})
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.assertEqual(response, {"key": "value"})
        self.cache._redis.get.assert_called_once_with(expected_key)

    def test_get_non_existing_key(self):
        # Mocking Redis.get method to return None
        self.cache._redis.get = MagicMock(return_value=None)

        response = self.cache.get({"param": "value"})
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.assertIsNone(response)
        self.cache._redis.get.assert_called_once_with(expected_key)

    def test_set(self):
        # Mocking Redis.set method
        self.cache._redis.set = MagicMock()

        self.cache.set({"param": "value"}, {"key": "value"}, ex=3600)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.cache._redis.set.assert_called_once_with(expected_key,
                                                      '{"key": "value"}', 3600)

    def test_generate_key(self):
        params = {"param": "value"}

        key = self.cache.generate_key(params)
        expected_key = "request_5647d15eb1d32d1548f1504fcc64134946cd1c401c87" \
                       + "bb9636b34606441b8ae6"

        self.assertEqual(key, expected_key)


if __name__ == '__main__':
    unittest.main()

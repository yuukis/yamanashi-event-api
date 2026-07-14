import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from app.cache import EventRequestCache
from app.providers.connpass import ConnpassEventRequest, ConnpassGroupRequest


class TestConnpassEventRequest(unittest.TestCase):

    def test_get_event(self):
        # Create a mock response with a single event
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [
                {
                    'id': 123,
                    'title': 'Test Event',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
                    'open_status': 'preopen',
                    'limit': 100,
                    'accepted': 50,
                    'waiting': 50,
                    'owner_id': 1234,
                    'owner_nickname': 'test',
                    'owner_display_name': 'Test',
                    'place': 'Yamanashi, Japan',
                    'address': 'Yamanashi, Japan',
                    'lat': 35.1234,
                    'lon': 138.1234,
                    'description': 'This is a test event',
                    'event_type': 'participation',
                    'group': {
                        'id': 1234,
                        'subdomain': 'test',
                        'title': 'Test group',
                        'url': 'https://test.connpass.com'
                    }
                }
            ],
            'results_returned': 1
        }

        # Create a mock cache object
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        # Create an instance of ConnpassEventRequest
        connpass_request = ConnpassEventRequest(cache=mock_cache)

        # Mock the __get method to return the mock response
        connpass_request._ConnpassEventRequest__get = MagicMock(
            return_value=mock_response)

        # Call the get_event method
        event = connpass_request.get_event()

        # Assert that the event is not None
        self.assertIsNotNone(event)

        # Assert that the event has the expected properties
        self.assertEqual(event.event_id, 123)
        self.assertEqual(event.title, 'Test Event')
        self.assertEqual(event.description, 'This is a test event')
        self.assertEqual(event.address, 'Yamanashi, Japan')

    def test_get_events(self):
        # Create a mock response with multiple events
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [
                {
                    'id': 123,
                    'title': 'Test Event 1',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
                    'open_status': 'preopen',
                    'limit': 100,
                    'accepted': 50,
                    'waiting': 50,
                    'owner_id': 1234,
                    'owner_nickname': 'test',
                    'owner_display_name': 'Test',
                    'place': 'Yamanashi, Japan',
                    'address': 'Yamanashi, Japan',
                    'lat': 35.1234,
                    'lon': 138.1234,
                    'description': 'This is test event 1',
                    'event_type': 'participation',
                    'group': {
                        'id': 1234,
                        'subdomain': 'test',
                        'title': 'Test group',
                        'url': 'https://test.connpass.com'
                    }
                },
                {
                    'id': 456,
                    'title': 'Test Event 2',
                    'catch': 'This is a test event',
                    'hash_tag': '',
                    'url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
                    'open_status': 'open',
                    'limit': None,
                    'accepted': 50,
                    'waiting': 50,
                    'owner_id': 5678,
                    'owner_nickname': 'test',
                    'owner_display_name': 'Test',
                    'place': None,
                    'address': None,
                    'lat': None,
                    'lon': None,
                    'description': 'This is test event 2',
                    'event_type': 'participation',
                    'group': None
                }
            ],
            'results_returned': 2
        }

        # Create a mock cache object
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        # Create an instance of ConnpassEventRequest
        connpass_request = ConnpassEventRequest(cache=mock_cache)

        # Mock the __get method to return the mock response
        connpass_request._ConnpassEventRequest__get = MagicMock(
            return_value=mock_response)

        # Call the get_events method
        events = connpass_request.get_events()

        # Assert that the events list is not empty
        self.assertNotEqual(len(events), 0)

        # Assert that the events list has the expected length
        self.assertEqual(len(events), 2)

        # Assert that the events have the expected properties
        self.assertEqual(events[0].event_id, 123)
        self.assertEqual(events[0].title, 'Test Event 1')
        self.assertEqual(events[0].description, 'This is test event 1')
        self.assertEqual(events[0].address, 'Yamanashi, Japan')

        self.assertEqual(events[1].event_id, 456)
        self.assertEqual(events[1].title, 'Test Event 2')
        self.assertEqual(events[1].description, 'This is test event 2')
        self.assertEqual(events[1].address, None)

    def test_get_events_skip_cache_bypasses_read_but_still_writes(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [],
            'results_returned': 0
        }

        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            'json': {'events': [], 'results_returned': 0},
            'last_modified': None
        }

        connpass_request = ConnpassEventRequest(cache=mock_cache, skip_cache=True)
        connpass_request._ConnpassEventRequest__get = MagicMock(
            return_value=mock_response)

        connpass_request.get_events()

        # skip_cache=True must never consult the cache for a read...
        mock_cache.get.assert_not_called()
        # ...but the freshly fetched result must still be written back.
        mock_cache.set.assert_called_once()

    def _make_page_response(self, num_events, results_returned, results_available):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [
                {
                    'id': i,
                    'title': f'Test Event {i}',
                    'catch': None,
                    'hash_tag': None,
                    'url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
                    'open_status': 'preopen',
                    'limit': 100,
                    'accepted': 50,
                    'waiting': 50,
                    'owner_id': 1234,
                    'owner_nickname': 'test',
                    'owner_display_name': 'Test',
                    'place': None,
                    'address': None,
                    'lat': None,
                    'lon': None,
                    'description': None,
                    'event_type': 'participation',
                    'group': None
                }
                for i in range(num_events)
            ],
            'results_returned': results_returned,
            'results_available': results_available
        }
        return mock_response

    def test_get_events_page_fetches_one_chunk_when_range_fits(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        connpass_request = ConnpassEventRequest(subdomain=['test'], cache=mock_cache)
        mock_get = MagicMock(
            return_value=self._make_page_response(100, 100, 250))
        connpass_request._ConnpassEventRequest__get = mock_get

        # Items 1-10 fit entirely within the first PAGE_SIZE=100 chunk.
        events = connpass_request.get_events_page(1, 10)

        self.assertEqual(len(events), 10)
        self.assertEqual(connpass_request.get_total_available(), 250)
        mock_get.assert_called_once()
        sent_params = mock_get.call_args[0][0]
        self.assertEqual(sent_params['start'], 1)
        self.assertEqual(sent_params['count'], ConnpassEventRequest.PAGE_SIZE)

    def test_get_events_page_fetches_only_chunks_the_range_spans(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        connpass_request = ConnpassEventRequest(subdomain=['test'], cache=mock_cache)
        responses = [
            self._make_page_response(100, 100, 250),  # chunk 0: items 1-100
            self._make_page_response(100, 100, 250),  # chunk 1: items 101-200
        ]
        seen_starts = []

        def fake_get(params):
            seen_starts.append(params['start'])
            return responses[len(seen_starts) - 1]

        mock_get = MagicMock(side_effect=fake_get)
        connpass_request._ConnpassEventRequest__get = mock_get

        # Items 95-114 span chunk 0 (1-100) and chunk 1 (101-200), but must
        # not reach chunk 2 (201-300).
        events = connpass_request.get_events_page(95, 20)

        self.assertEqual(len(events), 20)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(seen_starts, [1, 101])

    def test_get_events_page_shares_cache_keys_with_get_events(self):
        # The whole point of chunking to PAGE_SIZE boundaries is that a
        # small get_events_page() request and a full get_events() crawl
        # hit the exact same cache entries -- verify the params sent for
        # the first chunk are identical either way.
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get = MagicMock(
            return_value=self._make_page_response(1, 1, 1))

        crawl_request = ConnpassEventRequest(subdomain=['test'], cache=mock_cache)
        crawl_request._ConnpassEventRequest__get = mock_get
        crawl_request.get_events()
        crawl_params = mock_get.call_args[0][0]

        mock_get.reset_mock()
        page_request = ConnpassEventRequest(subdomain=['test'], cache=mock_cache)
        page_request._ConnpassEventRequest__get = mock_get
        page_request.get_events_page(1, 10)
        page_params = mock_get.call_args[0][0]

        self.assertEqual(crawl_params, page_params)

    def _make_event_response(self, event_id):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [
                {
                    'id': event_id,
                    'title': 'Test Event',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
                    'open_status': 'preopen',
                    'limit': 100,
                    'accepted': 50,
                    'waiting': 50,
                    'owner_id': 1234,
                    'owner_nickname': 'test',
                    'owner_display_name': 'Test',
                    'place': 'Yamanashi, Japan',
                    'address': 'Yamanashi, Japan',
                    'lat': 35.1234,
                    'lon': 138.1234,
                    'description': 'This is a test event',
                    'event_type': 'participation',
                    'group': None
                }
            ],
            'results_returned': 1
        }
        return mock_response

    def test_get_events_preserves_last_modified_when_content_unchanged(self):
        # cache_ttl=-1 means the inner cache entry is already expired by the
        # time the next call checks it, simulating the normal 60-minute
        # periodic refetch rather than an explicit force refresh.
        cache = EventRequestCache()
        params = {"count": 100, "order": 2, "start": 1}

        first = ConnpassEventRequest(cache=cache, cache_ttl=-1)
        first._ConnpassEventRequest__get = MagicMock(
            return_value=self._make_event_response(1))
        first.get_events()
        # The cache truncates last_modified to whole seconds, so compare
        # against what was actually stored rather than the in-memory,
        # pre-truncation value on `first`.
        stored_last_modified = cache.peek(params)["last_modified"]

        second = ConnpassEventRequest(cache=cache, cache_ttl=-1)
        second._ConnpassEventRequest__get = MagicMock(
            return_value=self._make_event_response(1))
        second.get_events()

        self.assertEqual(second.get_last_modified(), stored_last_modified)

    def test_get_events_updates_last_modified_when_content_changes(self):
        cache = EventRequestCache()

        first = ConnpassEventRequest(cache=cache, cache_ttl=-1)
        first._ConnpassEventRequest__get = MagicMock(
            return_value=self._make_event_response(1))
        first.get_events()
        first_last_modified = first.get_last_modified()

        second = ConnpassEventRequest(cache=cache, cache_ttl=-1)
        second._ConnpassEventRequest__get = MagicMock(
            return_value=self._make_event_response(2))
        second.get_events()
        second_last_modified = second.get_last_modified()

        self.assertNotEqual(first_last_modified, second_last_modified)


class TestConnpassGroupRequest(unittest.TestCase):

    def test_get_group(self):
        # Create a mock response with a single group
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'groups': [
                {
                    'id': 123,
                    'subdomain': 'test',
                    'title': 'Test Group',
                    'sub_title': 'This is a test group',
                    'url': 'https://test.connpass.com',
                    'description': 'This is a test group',
                    'owner_text': 'Test',
                    'image_url': 'https://test.connpass.com',
                    'website_url': 'https://test.connpass.com',
                    'twitter_username': 'test',
                    'facebook_url': 'https://test.connpass.com',
                    'member_users_count': 100
                }
            ],
            'results_returned': 1
        }

        # Create a mock cache object
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        # Create an instance of ConnpassGroupRequest
        connpass_request = ConnpassGroupRequest(cache=mock_cache)

        # Mock the __get method to return the mock response
        connpass_request._ConnpassGroupRequest__get = MagicMock(
            return_value=mock_response)

        # Call the get_group method
        group = connpass_request.get_group()

        # Assert that the group is not None
        self.assertIsNotNone(group)

        # Assert that the group has the expected properties
        self.assertEqual(group.id, 123)
        self.assertEqual(group.key, 'test')
        self.assertEqual(group.title, 'Test Group')
        self.assertEqual(group.description, 'This is a test group')
        self.assertEqual(group.image_url, 'https://test.connpass.com')
        self.assertEqual(group.website_url, 'https://test.connpass.com')
        self.assertEqual(group.x_username, 'test')
        self.assertEqual(group.facebook_url, 'https://test.connpass.com')
        self.assertEqual(group.member_users_count, 100)
    
    def test_get_groups(self):
        # Create a mock response with multiple groups
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'groups': [
                {
                    'id': 123,
                    'subdomain': 'test',
                    'title': 'Test Group 1',
                    'sub_title': 'This is a test group',
                    'url': 'https://test.connpass.com',
                    'description': 'This is a test group 1',
                    'owner_text': 'Test',
                    'image_url': 'https://test.connpass.com',
                    'website_url': 'https://test.connpass.com',
                    'twitter_username': 'test',
                    'facebook_url': 'https://test.connpass.com',
                    'member_users_count': 100
                },
                {
                    'id': 456,
                    'subdomain': 'test',
                    'title': 'Test Group 2',
                    'sub_title': 'This is a test group',
                    'url': 'https://test.connpass.com',
                    'description': 'This is a test group 2',
                    'owner_text': 'Test',
                    'image_url': 'https://test.connpass.com',
                    'website_url': 'https://test.connpass.com',
                    'twitter_username': 'test',
                    'facebook_url': 'https://test.connpass.com',
                    'member_users_count': 100
                }
            ],
            'results_returned': 2
        }

        # Create a mock cache object
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        # Create an instance of ConnpassGroupRequest
        connpass_request = ConnpassGroupRequest(cache=mock_cache)

        # Mock the __get method to return the mock response
        connpass_request._ConnpassGroupRequest__get = MagicMock(
            return_value=mock_response)

        # Call the get_groups method
        groups = connpass_request.get_groups()

        # Assert that the groups list is not empty
        self.assertNotEqual(len(groups), 0)

        # Assert that the groups list has the expected length
        self.assertEqual(len(groups), 2)

        # Assert that the groups have the expected properties
        self.assertEqual(groups[0].id, 123)
        self.assertEqual(groups[0].title, 'Test Group 1')
        self.assertEqual(groups[0].description, 'This is a test group 1')
        self.assertEqual(groups[0].image_url, 'https://test.connpass.com')
        self.assertEqual(groups[0].website_url, 'https://test.connpass.com')
        self.assertEqual(groups[0].x_username, 'test')
        self.assertEqual(groups[0].facebook_url, 'https://test.connpass.com')
        self.assertEqual(groups[0].member_users_count, 100)

        self.assertEqual(groups[1].id, 456)
        self.assertEqual(groups[1].title, 'Test Group 2')
        self.assertEqual(groups[1].description, 'This is a test group 2')
        self.assertEqual(groups[1].image_url, 'https://test.connpass.com')
        self.assertEqual(groups[1].website_url, 'https://test.connpass.com')
        self.assertEqual(groups[1].x_username, 'test')
        self.assertEqual(groups[1].facebook_url, 'https://test.connpass.com')
        self.assertEqual(groups[1].member_users_count, 100)

    def _make_group_response(self, member_count):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'groups': [
                {
                    'id': 123,
                    'subdomain': 'test',
                    'title': 'Test Group',
                    'sub_title': 'This is a test group',
                    'url': 'https://test.connpass.com',
                    'description': 'This is a test group',
                    'owner_text': 'Test',
                    'image_url': 'https://test.connpass.com',
                    'website_url': 'https://test.connpass.com',
                    'twitter_username': 'test',
                    'facebook_url': 'https://test.connpass.com',
                    'member_users_count': member_count
                }
            ],
            'results_returned': 1
        }
        return mock_response

    def test_get_groups_preserves_last_modified_when_content_unchanged(self):
        # ConnpassGroupRequest has no configurable TTL (unlike
        # ConnpassEventRequest), so the inner cache entry is force-expired
        # directly to simulate the normal periodic refetch.
        cache = EventRequestCache()

        params = {"count": 100, "start": 1}

        first = ConnpassGroupRequest(cache=cache)
        first._ConnpassGroupRequest__get = MagicMock(
            return_value=self._make_group_response(100))
        first.get_groups()
        # The cache truncates last_modified to whole seconds, so compare
        # against what was actually stored rather than the in-memory,
        # pre-truncation value on `first`.
        stored_last_modified = cache.peek(params)["last_modified"]

        key = cache.generate_key(params) + ":content"
        cache._expiry[key] = datetime.now(timezone.utc).timestamp() - 1

        second = ConnpassGroupRequest(cache=cache)
        second._ConnpassGroupRequest__get = MagicMock(
            return_value=self._make_group_response(100))
        second.get_groups()

        self.assertEqual(second.get_last_modified(), stored_last_modified)


if __name__ == '__main__':
    unittest.main()

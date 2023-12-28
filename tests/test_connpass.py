import unittest
from unittest.mock import MagicMock
from app.connpass import ConnpassEventRequest


class TestConnpassEventRequest(unittest.TestCase):

    def test_get_event(self):
        # Create a mock response with a single event
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'events': [
                {
                    'event_id': 123,
                    'title': 'Test Event',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'event_url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
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
                    'series': {
                        'id': 1234,
                        'title': 'Test Series',
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
                    'event_id': 123,
                    'title': 'Test Event 1',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'event_url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
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
                    'series': {
                        'id': 1234,
                        'title': 'Test Series',
                        'url': 'https://test.connpass.com'
                    }
                },
                {
                    'event_id': 456,
                    'title': 'Test Event 2',
                    'catch': 'This is a test event',
                    'hash_tag': '',
                    'event_url': 'https://test.connpass.com',
                    'started_at': '2020-01-01T00:00:00+09:00',
                    'ended_at': '2020-01-01T00:00:00+09:00',
                    'updated_at': '2020-01-01T00:00:00+09:00',
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
                    'series': None
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


if __name__ == '__main__':
    unittest.main()

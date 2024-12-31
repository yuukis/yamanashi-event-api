import unittest
from unittest.mock import MagicMock
from app.connpass import ConnpassEventRequest, ConnpassGroupRequest


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
                    'id': 123,
                    'title': 'Test Event 1',
                    'catch': 'This is a test event',
                    'hash_tag': 'test',
                    'url': 'https://test.connpass.com',
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
                    'id': 456,
                    'title': 'Test Event 2',
                    'catch': 'This is a test event',
                    'hash_tag': '',
                    'url': 'https://test.connpass.com',
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


if __name__ == '__main__':
    unittest.main()

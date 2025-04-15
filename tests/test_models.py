import unittest
from app.models import Event, EventDetail, Group


class TestEvent(unittest.TestCase):
    def test_distinct_by_id(self):
        # Create a list of events with duplicate event_ids
        events = [
            Event(uid="event_1@example.com",
                  event_id=1, title="Event 1", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  open_status="", owner_name="", place="", address="",
                  group_key="", group_name="", group_url=""),
            Event(uid="event_2@example.com",
                  event_id=2, title="Event 2", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  open_status="", owner_name="", place="", address="",
                  group_key="", group_name="", group_url=""),
            Event(uid="event_1@example.com",
                  event_id=1, title="Event 3", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  open_status="", owner_name="", place="", address="",
                  group_key="", group_name="", group_url=""),
            Event(uid="event_3@example.com",
                  event_id=3, title="Event 4", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  open_status="", owner_name="", place="", address="",
                  group_key="", group_name="", group_url=""),
            Event(uid="event_2@example.com",
                  event_id=2, title="Event 5", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  open_status="", owner_name="", place="", address="",
                  group_key="", group_name="", group_url=""),
        ]

        # Call the distinct_by_id method
        distinct_events = Event.distinct_by_id(events)

        # Check if the result contains unique events based on event_id
        self.assertEqual(len(distinct_events), 3)
        self.assertEqual(distinct_events[0].event_id, 1)
        self.assertEqual(distinct_events[1].event_id, 2)
        self.assertEqual(distinct_events[2].event_id, 3)

    def test_contains_keyword(self):
        # Create an event object
        event = EventDetail(uid="event_1@example.com",
                            event_id=1, title="Event 1", catch="Catch 1",
                            hash_tag="", event_url="",
                            started_at="", ended_at="", updated_at="",
                            limit=0, accepted=0, waiting=0,
                            open_status="preopen", owner_name="Owner 1",
                            place="Place", address="Address",
                            group_key="", group_name="", group_url="",
                            description="Description",
                            lat="", lon="")

        # Check if the event contains the keyword "Event"
        self.assertTrue(event.contains_keyword("Event"))

        # Check if the event contains the keyword "Catch"
        self.assertTrue(event.contains_keyword("Catch"))

        # Check if the event contains the keyword "Owner"
        self.assertTrue(event.contains_keyword("Owner"))

        # Check if the event contains the keyword "Place"
        self.assertTrue(event.contains_keyword("Place"))

        # Check if the event contains the keyword "Address"
        self.assertTrue(event.contains_keyword("Address"))

        # Check if the event contains the keyword "Description"
        self.assertTrue(event.contains_keyword("Description"))

        # Check if the event contains the keyword "Event" and "Catch"
        self.assertTrue(event.contains_keyword("Event,Catch"))

        # Check if the event contains the keyword "Dummy"
        self.assertFalse(event.contains_keyword("Dummy"))

        # Check if the event contains the keyword "Event" and "Dummy"
        self.assertFalse(event.contains_keyword("Event,Dummy"))

    def test_from_json_with_data(self):
        # Create a data object
        data = {
            "uid": "event_1@example.com",
            "event_id": 1,
            "title": "Event 1",
            "catch": "Catch 1",
            "hash_tag": "Hash Tag",
            "event_url": "Event URL",
            "started_at": "2022-01-01T00:00:00+09:00",
            "ended_at": "2022-01-01T00:00:00+09:00",
            "updated_at": "2022-01-01T00:00:00+09:00",
            "open_status": "preopen",
            "limit": 0,
            "accepted": 0,
            "waiting": 0,
            "owner_name": "Owner 1",
            "place": "Place",
            "address": "Address",
            "group_key": "Group Key",
            "group_name": "Group Name",
            "group_url": "Group URL",
            "description": "Description",
            "lat": "35.6895",
            "lon": "139.6917"
        }

        # Call the from_json method
        event = EventDetail.from_json(data)

        # Check if the event object is created
        self.assertIsNotNone(event)
        self.assertEqual(event.uid, "event_1@example.com")
        self.assertEqual(event.event_id, 1)
        self.assertEqual(event.title, "Event 1")
        self.assertEqual(event.catch, "Catch 1")
        self.assertEqual(event.hash_tag, "Hash Tag")
        self.assertEqual(event.event_url, "Event URL")
        self.assertEqual(event.started_at, "2022-01-01T00:00:00+09:00")
        self.assertEqual(event.ended_at, "2022-01-01T00:00:00+09:00")
        self.assertEqual(event.updated_at, "2022-01-01T00:00:00+09:00")
        self.assertEqual(event.open_status, "preopen")
        self.assertEqual(event.limit, 0)
        self.assertEqual(event.accepted, 0)
        self.assertEqual(event.waiting, 0)
        self.assertEqual(event.owner_name, "Owner 1")
        self.assertEqual(event.place, "Place")
        self.assertEqual(event.address, "Address")
        self.assertEqual(event.group_key, "Group Key")
        self.assertEqual(event.group_name, "Group Name")
        self.assertEqual(event.group_url, "Group URL")
        self.assertEqual(event.description, "Description")
        self.assertEqual(event.lat, "35.6895")
        self.assertEqual(event.lon, "139.6917")

    def test_to_json_with_list(self):
        # Create a list of event objects
        events = [
            EventDetail(uid="event_1@example.com",
                        event_id=1, title="Event 1", catch="Catch 1",
                        hash_tag="Hash Tag", event_url="Event URL",
                        started_at="2022-01-01T00:00:00+09:00",
                        ended_at="2022-01-01T00:00:00+09:00",
                        updated_at="2022-01-01T00:00:00+09:00",
                        limit=0, accepted=0, waiting=0,
                        open_status="preopen", owner_name="Owner 1",
                        place="Place", address="Address", group_key="Group Key",
                        group_name="Group Name", group_url="Group URL",
                        description="Description",
                        lat="35.6895", lon="139.6917"),
            EventDetail(uid="event_2@example.com",
                        event_id=2, title="Event 2", catch="Catch 2",
                        hash_tag="Hash Tag", event_url="Event URL",
                        started_at="2022-01-01T00:00:00+09:00",
                        ended_at="2022-01-01T00:00:00+09:00",
                        updated_at="2022-01-01T00:00:00+09:00",
                        limit=0, accepted=0, waiting=0,
                        open_status="open", owner_name="Owner 2",
                        place="Place", address="Address", group_key="Group Key",
                        group_name="Group Name", group_url="Group URL",
                        description="Description",
                        lat="35.6895", lon="139.6917")
        ]

        # Call the to_json method
        data = EventDetail.to_json(events)

        # Check if the data object is created
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["event_id"], 1)
        self.assertEqual(data[1]["event_id"], 2)


class TestGroup(unittest.TestCase):
    def test_from_json_with_data(self):
        # Create a data object
        data = {
            "id": 1,
            "key": "Key",
            "title": "Title",
            "sub_title": "Sub Title",
            "url": "URL",
            "description": "Description",
            "owner_text": "Owner Text",
            "image_url": "Image URL",
            "website_url": "Website URL",
            "x_username": "X Username",
            "facebook_url": "Facebook URL",
            "member_users_count": 100
        }

        # Call the from_json method
        group = Group.from_json(data)

        # Check if the group object is created
        self.assertIsNotNone(group)
        self.assertEqual(group.id, 1)
        self.assertEqual(group.key, "Key")
        self.assertEqual(group.title, "Title")
        self.assertEqual(group.sub_title, "Sub Title")
        self.assertEqual(group.url, "URL")
        self.assertEqual(group.description, "Description")
        self.assertEqual(group.owner_text, "Owner Text")
        self.assertEqual(group.image_url, "Image URL")
        self.assertEqual(group.website_url, "Website URL")
        self.assertEqual(group.x_username, "X Username")
        self.assertEqual(group.facebook_url, "Facebook URL")
        self.assertEqual(group.member_users_count, 100)

    def test_to_json_with_list(self):
        # Create a list of group objects
        groups = [
            Group(id=1, key="Key", title="Title", sub_title="Sub Title",
                  url="URL", description="Description", owner_text="Owner Text",
                  image_url="Image URL", website_url="Website URL",
                  x_username="X Username", facebook_url="Facebook URL",
                  member_users_count=100),
            Group(id=2, key="Key", title="Title", sub_title="Sub Title",
                  url="URL", description="Description", owner_text="Owner Text",
                  image_url="Image URL", website_url="Website URL",
                  x_username="X Username", facebook_url="Facebook URL",
                  member_users_count=100)
        ]

        # Call the to_json method
        data = Group.to_json(groups)

        # Check if the data object is created
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], 1)
        self.assertEqual(data[1]["id"], 2)


if __name__ == '__main__':
    unittest.main()

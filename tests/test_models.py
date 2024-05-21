import unittest
from app.models import Event, EventDetail


class TestEvent(unittest.TestCase):
    def test_distinct_by_id(self):
        # Create a list of events with duplicate event_ids
        events = [
            Event(event_id=1, title="Event 1", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  owner_name="", place="", address="",
                  group_name="", group_url=""),
            Event(event_id=2, title="Event 2", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  owner_name="", place="", address="",
                  group_name="", group_url=""),
            Event(event_id=1, title="Event 3", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  owner_name="", place="", address="",
                  group_name="", group_url=""),
            Event(event_id=3, title="Event 4", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  owner_name="", place="", address="",
                  group_name="", group_url=""),
            Event(event_id=2, title="Event 5", catch="", hash_tag="",
                  event_url="", started_at="", ended_at="", updated_at="",
                  owner_name="", place="", address="",
                  group_name="", group_url=""),
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
        event = EventDetail(event_id=1, title="Event 1", catch="Catch 1",
                            hash_tag="", event_url="",
                            started_at="", ended_at="", updated_at="",
                            limit=0, accepted=0, waiting=0,
                            owner_name="Owner 1",
                            place="Place", address="Address",
                            group_name="", group_url="",
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


if __name__ == '__main__':
    unittest.main()

import unittest
from app.models import Event


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


if __name__ == '__main__':
    unittest.main()

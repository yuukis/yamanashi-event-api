import unittest
from unittest.mock import MagicMock, patch
from app.icalendar import IcalEventRequest
from datetime import datetime


class TestIcalEventRequest(unittest.TestCase):
    def test_get_events(self):
        ical_content = b"""
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//JP
METHOD:PUBLISH
BEGIN:VEVENT
SUMMARY:EVENT 1
DTSTART:20240401T130000
DTEND:20240401T170000
DTSTAMP:20240401T000000Z
UID:event_1@example.com
URL;VALUE=URI:http://example.com/event_1
DESCRIPTION:DESCRIPTION 1
LAST-MODIFIED:20240401T000000Z
LOCATION:LOCATION 1
END:VEVENT
END:VCALENDAR
"""
        ical_request = IcalEventRequest(
            url="http://example.com",
            key="test_key",
            name="Test Group",
            image_url="http://example.com/image.png",
            group_url="http://example.com/group"
        )
        ical_request._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request.get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].uid, "event_1@example.com")
        self.assertEqual(events[0].title, "EVENT 1")
        self.assertEqual(events[0].event_url, "http://example.com/event_1")
        self.assertEqual(events[0].place, "LOCATION 1")
        self.assertEqual(events[0].description, "DESCRIPTION 1")
        self.assertEqual(events[0].group_key, "test_key")
        self.assertEqual(events[0].group_name, "Test Group")
        self.assertEqual(events[0].group_url, "http://example.com/group")

    @patch("app.icalendar.datetime")
    def test_get_events_open_status(self, mock_datetime):
        ical_content = b"""
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//JP
METHOD:PUBLISH
BEGIN:VEVENT
SUMMARY:EVENT 1
DTSTART:20240401T130000
DTEND:20240401T170000
DTSTAMP:20240401T000000Z
UID:event_1@example.com
URL;VALUE=URI:http://example.com/event_1
LAST-MODIFIED:20240401T000000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:EVENT 2
DTSTART:20240402T130000
DTEND:20240402T170000
DTSTAMP:20240401T000000Z
UID:event_2@example.com
URL;VALUE=URI:http://example.com/event_2
LAST-MODIFIED:20240401T000000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:EVENT 3
DTSTART:20240331T130000
DTEND:20240331T170000
DTSTAMP:20240331T000000Z
UID:event_3@example.com
URL;VALUE=URI:http://example.com/event_3
LAST-MODIFIED:20240401T000000Z
END:VEVENT
END:VCALENDAR
"""
        fixed_datetime = datetime(2024, 4, 1, 15, 0, 0)
        mock_datetime.now.return_value = fixed_datetime
        mock_datetime.side_effect = lambda *args, **kwargs: fixed_datetime

        ical_request = IcalEventRequest(
            url="http://example.com",
            key="test_key"
        )
        ical_request._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request.get_events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].open_status, "open")
        self.assertEqual(events[1].open_status, "preopen")
        self.assertEqual(events[2].open_status, "close")

    def test_get_events_by_ym(self):
        ical_content = b"""
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//JP
METHOD:PUBLISH
BEGIN:VEVENT
SUMMARY:EVENT 1
DTSTART:20240401T130000
DTEND:20240401T170000
DTSTAMP:20240401T000000Z
UID:event_1@example.com
URL;VALUE=URI:http://example.com/event_1
LAST-MODIFIED:20240401T000000Z
END:VEVENT
END:VCALENDAR
"""
        ical_request1 = IcalEventRequest(
            url="http://example.com",
            key="test_key",
            ym=["202404"]
        )
        ical_request1._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request1.get_events()
        self.assertEqual(len(events), 1)

        ical_request2 = IcalEventRequest(
            url="http://example.com",
            key="test_key",
            ym=["202403"]
        )
        ical_request2._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request2.get_events()
        self.assertEqual(len(events), 0)

    def test_get_events_by_ymd(self):
        ical_content = b"""
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//JP
METHOD:PUBLISH
BEGIN:VEVENT
SUMMARY:EVENT 1
DTSTART:20240401T130000
DTEND:20240401T170000
DTSTAMP:20240401T000000Z
UID:event_1@example.com
URL;VALUE=URI:http://example.com/event_1
LAST-MODIFIED:20240401T000000Z
END:VEVENT
END:VCALENDAR
"""
        ical_request1 = IcalEventRequest(
            url="http://example.com",
            key="test_key",
            ymd=["20240401"]
        )
        ical_request1._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request1.get_events()
        self.assertEqual(len(events), 1)

        ical_request2 = IcalEventRequest(
            url="http://example.com",
            key="test_key",
            ymd=["20240402"]
        )
        ical_request2._IcalEventRequest__get_content = MagicMock(
            return_value=ical_content)
        events = ical_request2.get_events()
        self.assertEqual(len(events), 0)

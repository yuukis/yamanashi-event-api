import unittest
from unittest.mock import MagicMock, patch
from app.archive import ArchiveIndexRequest, ArchiveException


class TestArchiveIndexRequest(unittest.TestCase):
    def test_get_events(self):
        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json"
        )
        archive_request._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index()
        )

        events = archive_request.get_events()

        self.assertEqual(len(events), 2)
        self.assertEqual(
            events[0].uid,
            "yamanashi-web-2012-05-19-001@yamanashi-it-event-archive"
        )
        self.assertEqual(events[0].event_id, None)
        self.assertEqual(events[0].group_key, "yamanashi-web")

    def test_get_events_by_ym(self):
        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json",
            ym=["201205"]
        )
        archive_request._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index()
        )

        events = archive_request.get_events()

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].uid,
            "yamanashi-web-2012-05-19-001@yamanashi-it-event-archive"
        )

    def test_get_events_by_ymd(self):
        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json",
            ymd=["20140308"]
        )
        archive_request._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index()
        )

        events = archive_request.get_events()

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].uid,
            "houtoupm-2014-03-08-001@yamanashi-it-event-archive"
        )

    def test_get_groups(self):
        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json"
        )
        archive_request._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index()
        )

        groups = archive_request.get_groups()

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].key, "yamanashi-web")
        self.assertEqual(groups[0].title, "山梨Web勉強会")
        self.assertEqual(groups[0].url, "https://example.com/yamanashi-web")
        self.assertEqual(groups[0].ical_url, None)
        self.assertEqual(groups[0].archive_source,
                         "yamanashi-it-event-archive")
        self.assertEqual(
            groups[0].archive_url,
            "https://github.com/yuukis/yamanashi-it-event-archive"
        )

    @patch("app.archive.requests.get")
    def test_get_events_http_error(self, mock_get):
        response = MagicMock()
        response.status_code = 404
        mock_get.return_value = response

        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json"
        )

        with self.assertRaises(ArchiveException) as context:
            archive_request.get_events()

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.message, "Failed to fetch archive index")

    def __archive_index(self):
        return {
            "schema_version": "1.0",
            "generated_at": "2026-06-30T00:00:00+09:00",
            "source": {
                "type": "archive_index",
                "name": "yamanashi-it-event-archive",
                "url": "https://github.com/yuukis/yamanashi-it-event-archive",
                "ref": "main"
            },
            "communities": [
                {
                    "key": "yamanashi-web",
                    "title": "山梨Web勉強会",
                    "sub_title": "山梨県内のWeb制作者・開発者向け勉強会",
                    "url": "https://example.com/yamanashi-web",
                    "description": "山梨県内のWeb制作・Web開発勉強会です。",
                    "owner_text": None,
                    "image_url": None,
                    "website_url": "https://example.com/yamanashi-web",
                    "x_username": None,
                    "facebook_url": None,
                    "member_users_count": None,
                    "ical_url": None
                },
                {
                    "key": "houtoupm",
                    "title": "Houtou.pm",
                    "url": "https://example.com/houtoupm"
                }
            ],
            "events": [
                {
                    "uid": "yamanashi-web-2012-05-19-001"
                    "@yamanashi-it-event-archive",
                    "event_id": None,
                    "title": "山梨Web勉強会 第1回",
                    "catch": "山梨のWeb制作者・開発者が集まる勉強会",
                    "hash_tag": "yamanashiweb",
                    "event_url": "https://example.com/archive/yamanashi-web/"
                    "2012-05-19-001",
                    "started_at": "2012-05-19T14:00:00+09:00",
                    "ended_at": "2012-05-19T17:00:00+09:00",
                    "updated_at": "2026-06-30T00:00:00+09:00",
                    "open_status": "close",
                    "limit": None,
                    "accepted": None,
                    "waiting": None,
                    "owner_name": None,
                    "place": "山梨県立図書館",
                    "address": "山梨県甲府市北口2-8-1",
                    "group_key": "yamanashi-web",
                    "group_name": "山梨Web勉強会",
                    "group_url": "https://example.com/yamanashi-web",
                    "description": "山梨Web勉強会の初回イベント。",
                    "lat": None,
                    "lon": None
                },
                {
                    "uid": "houtoupm-2014-03-08-001"
                    "@yamanashi-it-event-archive",
                    "event_id": None,
                    "title": "Houtou.pm #1",
                    "event_url": "https://example.com/archive/houtoupm/"
                    "2014-03-08-001",
                    "started_at": "2014-03-08T14:00:00+09:00",
                    "ended_at": "2014-03-08T17:00:00+09:00",
                    "updated_at": "2026-06-30T00:00:00+09:00",
                    "open_status": "close",
                    "group_key": "houtoupm",
                    "group_name": "Houtou.pm",
                    "group_url": "https://example.com/houtoupm"
                }
            ]
        }


if __name__ == '__main__':
    unittest.main()

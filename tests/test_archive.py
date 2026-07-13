import unittest
from unittest.mock import MagicMock, patch
from app.providers.archive import ArchiveIndexRequest, ArchiveException
from app.cache import EventRequestCache


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
            "yamanashi-web-2012-05-19-001@yamanashi-event-archive"
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
            "yamanashi-web-2012-05-19-001@yamanashi-event-archive"
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
            "houtoupm-2014-03-08-001@yamanashi-event-archive"
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
                         "yamanashi-event-archive")
        self.assertEqual(
            groups[0].archive_url,
            "https://github.com/yuukis/yamanashi-event-archive"
        )

    @patch("app.providers.archive.requests.get")
    def test_preload_keeps_archive_index_in_cache(self, mock_get):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = self.__archive_index()
        mock_get.return_value = response

        cache = EventRequestCache(prefix="test_archive_")
        archive_request = ArchiveIndexRequest(
            url="https://example.com/archive/index.json",
            cache=cache
        )

        archive_request.preload()
        events = archive_request.get_events()
        groups = archive_request.get_groups()

        self.assertEqual(len(events), 2)
        self.assertEqual(len(groups), 2)
        self.assertEqual(mock_get.call_count, 1)

    @patch("app.providers.archive.requests.get")
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
        mock_get.assert_called_once_with(
            "https://example.com/archive/index.json",
            timeout=10
        )

    def test_get_events_preserves_last_modified_when_content_unchanged(self):
        # Archive caches never expire (ex=None), so the entry is
        # force-expired directly to simulate a refetch of the same index.
        cache = EventRequestCache(prefix="test_archive_preserve_")
        url = "https://example.com/archive/index.json"
        cache_key = {"archive_index_url": url}

        first = ArchiveIndexRequest(url=url, cache=cache)
        first._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index())
        first.get_events()
        # The cache truncates last_modified to whole seconds, so compare
        # against what was actually stored rather than the in-memory,
        # pre-truncation value on `first`.
        stored_last_modified = cache.peek(cache_key)["last_modified"]

        key = cache.generate_key(cache_key) + ":content"
        cache._expiry[key] = 0

        second = ArchiveIndexRequest(url=url, cache=cache)
        second._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index())
        second.get_events()

        self.assertEqual(second.get_last_modified(), stored_last_modified)

    def test_get_events_updates_last_modified_when_content_changes(self):
        cache = EventRequestCache(prefix="test_archive_update_")
        url = "https://example.com/archive/index.json"
        cache_key = {"archive_index_url": url}

        first = ArchiveIndexRequest(url=url, cache=cache)
        first._ArchiveIndexRequest__get_json = MagicMock(
            return_value=self.__archive_index())
        first.get_events()
        first_last_modified = first.get_last_modified()

        key = cache.generate_key(cache_key) + ":content"
        cache._expiry[key] = 0

        changed_index = self.__archive_index()
        changed_index["events"].append({
            "uid": "new-event@yamanashi-event-archive",
            "event_id": None,
            "title": "New Event",
            "event_url": "https://example.com/archive/new",
            "started_at": "2020-01-01T14:00:00+09:00",
            "ended_at": "2020-01-01T17:00:00+09:00",
            "updated_at": "2026-06-30T00:00:00+09:00",
            "open_status": "close",
            "group_key": "yamanashi-web",
            "group_name": "山梨Web勉強会",
            "group_url": "https://example.com/yamanashi-web"
        })

        second = ArchiveIndexRequest(url=url, cache=cache)
        second._ArchiveIndexRequest__get_json = MagicMock(
            return_value=changed_index)
        second.get_events()
        second_last_modified = second.get_last_modified()

        self.assertNotEqual(first_last_modified, second_last_modified)

    def __archive_index(self):
        return {
            "schema_version": "1.0",
            "generated_at": "2026-06-30T00:00:00+09:00",
            "source": {
                "type": "archive_index",
                "name": "yamanashi-event-archive",
                "url": "https://github.com/yuukis/yamanashi-event-archive",
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
                    "uid": "yamanashi-web-2012-05-19-001@yamanashi-event-archive",
                    "event_id": None,
                    "title": "山梨Web勉強会 第1回",
                    "catch": "山梨のWeb制作者・開発者が集まる勉強会",
                    "hash_tag": "yamanashiweb",
                    "event_url": "https://example.com/archive/yamanashi-web/2012-05-19-001",
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
                    "uid": "houtoupm-2014-03-08-001@yamanashi-event-archive",
                    "event_id": None,
                    "title": "Houtou.pm #1",
                    "event_url": "https://example.com/archive/houtoupm/2014-03-08-001",
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

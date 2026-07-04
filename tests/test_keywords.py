import unittest
from app.keywords import KeywordExtractor
from app.models import EventDetail


def make_event(title="", catch=None, hash_tag=None, description=None,
               group_key=None, group_name=None, keywords=None):
    return EventDetail(
        uid="event_1@example.com",
        event_id=1, title=title, catch=catch, hash_tag=hash_tag,
        event_url="https://example.com/event/1",
        started_at="2026-07-01T19:00:00+09:00",
        ended_at="2026-07-01T21:00:00+09:00",
        updated_at="2026-07-01T00:00:00+09:00",
        open_status="preopen", group_key=group_key, group_name=group_name,
        description=description, keywords=keywords
    )


class TestKeywordExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = KeywordExtractor()

    def test_extract_from_title(self):
        event = make_event(title="Python もくもく会 #10")
        keywords = self.extractor.extract(event)

        self.assertIn("Python", keywords)
        self.assertIn("もくもく会", keywords)

    def test_extract_normalizes_notation(self):
        # variant notations are normalized to the canonical keyword
        event = make_event(title="パイソン入門 ワードプレスではじめるWeb制作")
        keywords = self.extractor.extract(event)

        self.assertIn("Python", keywords)
        self.assertIn("WordPress", keywords)
        self.assertIn("初心者歓迎", keywords)

    def test_extract_is_case_insensitive(self):
        event = make_event(title="WORDPRESS meetup")
        keywords = self.extractor.extract(event)

        self.assertIn("WordPress", keywords)

    def test_extract_from_description(self):
        event = make_event(title="第10回 勉強会",
                           description="<p>AWSのハンズオンを行います。</p>")
        keywords = self.extractor.extract(event)

        self.assertIn("AWS", keywords)
        self.assertIn("ハンズオン", keywords)

    def test_extract_returns_at_most_five_keywords(self):
        event = make_event(
            title="Python JavaScript Ruby PHP Java Go入門もくもく会")
        keywords = self.extractor.extract(event)

        self.assertEqual(len(keywords), 5)

    def test_extract_prefers_title_over_description(self):
        event = make_event(
            title="Python Ruby PHP Java JavaScript入門もくもく会",
            description="Dockerも使います。")
        keywords = self.extractor.extract(event)

        self.assertNotIn("Docker", keywords)

    def test_extract_from_group_name(self):
        event = make_event(title="第10回 勉強会", group_name="shingen.py")
        keywords = self.extractor.extract(event)

        self.assertIn("Python", keywords)

    def test_extract_from_group_key(self):
        event = make_event(title="第10回 勉強会", group_key="coderdojokofu")
        keywords = self.extractor.extract(event)

        self.assertIn("子ども向け", keywords)
        self.assertIn("プログラミング教育", keywords)

    def test_extract_returns_empty_list_when_no_match(self):
        event = make_event(title="第10回 定例会")
        keywords = self.extractor.extract(event)

        self.assertEqual(keywords, [])

    def test_extract_does_not_match_partial_english_words(self):
        # "air" must not match the short keyword pattern for "AI"
        event = make_event(title="On the air")
        keywords = self.extractor.extract(event)

        self.assertNotIn("AI", keywords)

    def test_extract_matches_short_words_next_to_japanese(self):
        event = make_event(title="生成AIを学ぼう")
        keywords = self.extractor.extract(event)

        self.assertIn("AI", keywords)

    def test_extract_normalizes_generative_ai_to_ai(self):
        event = make_event(title="ChatGPT活用セミナー")
        keywords = self.extractor.extract(event)

        self.assertIn("AI", keywords)
        self.assertNotIn("生成AI", keywords)


class TestEventDetailKeywords(unittest.TestCase):
    def test_from_json_inherits_keywords(self):
        data = {
            "uid": "event_1@example.com",
            "title": "Event 1",
            "event_url": "https://example.com/event/1",
            "started_at": "2026-07-01T19:00:00+09:00",
            "ended_at": "2026-07-01T21:00:00+09:00",
            "updated_at": "2026-07-01T00:00:00+09:00",
            "open_status": "close",
            "keywords": ["Python", "初心者歓迎"]
        }

        event = EventDetail.from_json(data)

        self.assertEqual(event.keywords, ["Python", "初心者歓迎"])

    def test_from_json_without_keywords(self):
        data = {
            "uid": "event_1@example.com",
            "title": "Event 1",
            "event_url": "https://example.com/event/1",
            "started_at": "2026-07-01T19:00:00+09:00",
            "ended_at": "2026-07-01T21:00:00+09:00",
            "updated_at": "2026-07-01T00:00:00+09:00",
            "open_status": "close"
        }

        event = EventDetail.from_json(data)

        self.assertIsNone(event.keywords)

    def test_from_json_sanitizes_non_string_keywords(self):
        data = {
            "uid": "event_1@example.com",
            "title": "Event 1",
            "event_url": "https://example.com/event/1",
            "started_at": "2026-07-01T19:00:00+09:00",
            "ended_at": "2026-07-01T21:00:00+09:00",
            "updated_at": "2026-07-01T00:00:00+09:00",
            "open_status": "close",
            "keywords": [123, "Python", None]
        }

        event = EventDetail.from_json(data)

        self.assertEqual(event.keywords, ["Python"])

    def test_from_json_with_invalid_keywords(self):
        base = {
            "uid": "event_1@example.com",
            "title": "Event 1",
            "event_url": "https://example.com/event/1",
            "started_at": "2026-07-01T19:00:00+09:00",
            "ended_at": "2026-07-01T21:00:00+09:00",
            "updated_at": "2026-07-01T00:00:00+09:00",
            "open_status": "close"
        }

        # non-list and empty keywords fall back to extraction (None)
        for keywords in ["Python", 123, {}, [], [123, None]]:
            event = EventDetail.from_json({**base, "keywords": keywords})
            self.assertIsNone(event.keywords)

    def test_to_json_contains_keywords(self):
        event = make_event(title="Event 1", keywords=["Python"])

        data = EventDetail.to_json(event)

        self.assertEqual(data["keywords"], ["Python"])

    def test_contains_keyword_matches_keywords(self):
        event = make_event(title="Event 1", keywords=["Python", "初心者歓迎"])

        self.assertTrue(event.contains_keyword("Python"))
        self.assertTrue(event.contains_keyword("初心者歓迎"))
        self.assertFalse(event.contains_keyword("Ruby"))


if __name__ == "__main__":
    unittest.main()

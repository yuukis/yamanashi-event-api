# Archive Index

Archive indexes provide historical event data from a repository or static site
outside this API project. The API reads the generated JSON index and merges its
events with connpass and iCalendar events.

Archive index JSON files are loaded on application startup and kept in memory
without expiration while the application process is running. If startup preload
fails, the application keeps running and retries the archive fetch when an
archive-backed endpoint is requested.

## Configuration

Add `scope.archives` to `app/config.yaml`.

```yaml
scope:
  archives:
    - url:
        - https://yuukis.github.io/yamanashi-event-archive/index.json
```

Multiple archive indexes can be configured.

```yaml
scope:
  archives:
    - url:
        - https://yuukis.github.io/yamanashi-event-archive/index.json
        - https://example.github.io/another-tech-event-archive/index.json
```

## JSON Format

The top-level `events` array is converted to `EventDetail`. The top-level
`communities` array is converted to `Group`. The API adds `archive_source` and
`archive_url` to each archive community from `source.name` and `source.url`.

```json
{
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
      "description": "山梨県内でWeb制作・Web開発に関心のある人が集まっていた勉強会です。",
      "owner_text": null,
      "image_url": null,
      "website_url": "https://example.com/yamanashi-web",
      "x_username": null,
      "facebook_url": null,
      "member_users_count": null,
      "ical_url": null,
      "archive_source": "yamanashi-event-archive",
      "archive_url": "https://github.com/yuukis/yamanashi-event-archive"
    }
  ],
  "events": [
    {
      "uid": "yamanashi-web-2012-05-19-001@yamanashi-event-archive",
      "event_id": null,
      "title": "山梨Web勉強会 第1回",
      "catch": "山梨のWeb制作者・開発者が集まる勉強会",
      "hash_tag": "yamanashiweb",
      "event_url": "https://example.com/archive/yamanashi-web/2012-05-19-001",
      "started_at": "2012-05-19T14:00:00+09:00",
      "ended_at": "2012-05-19T17:00:00+09:00",
      "updated_at": "2026-06-30T00:00:00+09:00",
      "open_status": "close",
      "limit": null,
      "accepted": null,
      "waiting": null,
      "owner_name": null,
      "place": "山梨県立図書館",
      "address": "山梨県甲府市北口2-8-1",
      "group_key": "yamanashi-web",
      "group_name": "山梨Web勉強会",
      "group_url": "https://example.com/yamanashi-web",
      "description": "山梨Web勉強会の初回イベント。",
      "lat": null,
      "lon": null
    }
  ]
}
```

`uid` should follow the same shape as connpass events:

```text
{group_key}-{YYYY-MM-DD}-{serial}@{archive_source_key}
```

For example:

```text
yamanashi-web-2012-05-19-001@yamanashi-event-archive
```

The required event fields are:

- `uid`
- `title`
- `event_url`
- `started_at`
- `ended_at`
- `updated_at`
- `open_status`

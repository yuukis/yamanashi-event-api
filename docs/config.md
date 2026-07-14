# Configuration (`app/config.yaml`)

This file controls the API's metadata and which events/groups it serves.

```yaml
metadata:
  title: 'Yamanashi Tech Events API'
  description: 'This is an API for Tech events in Yamanashi prefecture.'
  version: '1.8.2'

api_client:
  user_agent: 'YamanashiTechEventAPI/{version} (+https://github.com/yuukis/yamanashi-event-api)'

recent_days: 120

scope:
  prefecture: [...]
  connpass: [...]
  icalendar: [...]
  archives: [...]
```

## metadata

Used as the FastAPI app's title, description and version (shown in the
OpenAPI docs at `/docs`).

- `title`, `description`, `version` are all required.

## api_client

- `user_agent`: sent as the `User-Agent` header on connpass API requests.
  `{version}` is replaced with `metadata.version`. Optional; connpass
  requests omit the header if unset.

## recent_days

Default number of days considered "recent" by the `/events` (and other
recent-events) endpoints when no explicit range is given. Optional, defaults
to 90.

## scope

Controls which events and groups this API serves. Every subsection is
optional; omit one entirely to not use that source.

### scope.prefecture

A list of address keywords. Any connpass event (from *any* connpass group,
not just the ones listed under `scope.connpass`) whose address contains one
of these strings is included. This is what picks up an event held locally
by a group this API doesn't otherwise track.

```yaml
scope:
  prefecture:
    - '山梨県'
```

### scope.connpass

The connpass groups (subdomains) this API pulls events from. Each entry is
either a plain entry or a chapter entry.

A plain entry includes every event from that group as-is, using connpass's
own group metadata for `/groups`. Only `subdomain` is required.

```yaml
scope:
  connpass:
    - subdomain: 'some-group'
```

A chapter entry scopes down to a single regional chapter inside a larger
shared group (e.g. one national group hosting per-prefecture chapters under
a single subdomain, where a plain entry would pull in every other chapter's
events too). Every event from `subdomain` is fetched, only the ones whose
*title* contains `title_keyword` are kept (checked locally, not sent to
connpass, since connpass's own keyword search also matches
description/address text and would pull in other chapters' events), then
re-labeled to `key`/`name`/`group_url` so they appear as their own community
rather than the shared group's.

```yaml
scope:
  connpass:
    - subdomain: 'some-shared-group'
      title_keyword: 'xxx'
      key: 'some-shared-group-xxx'
      name: 'Some Shared Group XXX'
      image_url: null
      group_url: https://example.com/
```

`subdomain`, `title_keyword`, `key` and `name` are required for a chapter
entry (no auto-generated fallback is provided for `key`/`name`: a good one
doesn't exist without either producing a low-quality name or re-fetching the
shared group's real name, which would defeat the purpose). `image_url` and
`group_url` are optional.

### scope.icalendar

Communities that publish an iCal feed instead of (or in addition to) a
connpass group.

```yaml
scope:
  icalendar:
    - key: 'some-group-ical'
      name: 'Some Group'
      image_url: null
      group_url: https://example.com/some-group/
      ical_url: https://example.com/some-group/events/ical/
```

- `key`, `name`, `ical_url` are required.
- `image_url`, `group_url` are optional.

### scope.archives

External, statically hosted archive index JSON files, typically for
historical events predating this API. See
[Archive Index](archive-index.md) for the JSON format.

```yaml
scope:
  archives:
    - url:
        - https://example.com/some-archive/index.json
```

`url` can be a single string or a list of strings.

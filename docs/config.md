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

The connpass groups (subdomains) this API pulls events from, including how
to scope down to a single chapter within a larger shared connpass group.
See [Connpass Group Scope](connpass-scope.md).

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

# Connpass Group Scope

`scope.connpass` in `app/config.yaml` lists the connpass groups (subdomains)
this API pulls events from. Each entry is either a plain entry or a chapter
entry.

## Plain Entry

Includes every event from that group as-is, using connpass's own group
metadata for `/groups`.

```yaml
scope:
  connpass:
    - subdomain: 'some-group'
```

Only `subdomain` is required.

## Chapter Entry

Some communities aren't their own connpass group, but a regional chapter
inside a larger shared group (e.g. one national group hosting per-prefecture
chapters under a single subdomain). Adding that subdomain as a plain entry
would pull in every other chapter's events too.

Add `title_keyword`, `key` and `name` to scope it down to just that chapter
instead: every event from `subdomain` is fetched, only the ones whose
*title* contains `title_keyword` are kept, and they're re-labeled to
`key`/`name`/`group_url` so they appear as their own community rather than
the shared group's.

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

`subdomain`, `title_keyword`, `key` and `name` are required. There's no
auto-generated fallback for `key`/`name`: a good one doesn't exist without
either producing a low-quality name (e.g. just the bare `title_keyword`) or
re-fetching the shared group's real name (e.g. "Some Shared Group"), which
would reproduce the very problem this is meant to solve. `image_url` and
`group_url` are optional.

Matching against `title_keyword` is done locally against the event title
only, and never sent to connpass as a `keyword` search parameter, since
connpass's own keyword search also matches description/address text and
would pull in other chapters' events that merely mention the word in
passing.

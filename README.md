[![Test](https://github.com/yuukis/yamanashi-event-api/actions/workflows/test.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-api/actions/workflows/test.yml)
[![DockerHub](https://github.com/yuukis/yamanashi-event-api/actions/workflows/dockerhub.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-api/actions/workflows/dockerhub.yml)
[![DeployToAWS](https://github.com/yuukis/yamanashi-event-api/actions/workflows/aws-deploy.yml/badge.svg?branch=main&event=push)](https://github.com/yuukis/yamanashi-event-api/actions/workflows/aws-deploy.yml)

# Yamanashi Tech Events API

<!-- ABOUT THE PROJECT -->
## About The Project

This is a simple API for Yamanashi Tech Events.
It retrieves event data from [Connpass](https://conpass.com) via API.

This API is available at the following URL.

https://api.event.yamanashi.dev

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* Python 3.10 or later

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/yuukis/yamanashi-events-api.git
    ```
2. Install Python packages
    ```sh
    pip install -r requirements.txt
    ```
3. Copy `.env.example` to `.env` and set environment variables
    ```ini
    CONNPASS_API_KEY=YOUR_CONNPASS_API_KEY
    ```
4. Run the app
    ```sh
    uvicorn app.main:app --reload
    ```
5. Access to http://localhost:8000

### Docker Compose Installation

If you have Docker and Docker Compose installed, you can use the following steps to get the project running:

1. Clone the repo
    ```sh
    git clone https://github.com/yuukis/yamanashi-events-api.git
    ```

2. Build and run the Docker services
    ```sh
    docker-compose up --build
    ```

3. Access to http://localhost:8000

<!-- USAGE EXAMPLES -->
## Usage

* Get recent events

    ```sh
    curl http://localhost:8000/events
    ```

* Get today's events

    ```sh
    curl http://localhost:8000/events/today
    ```

* Get events by year/month

    ```sh
    curl http://localhost:8000/events/in/2023/12
    ```

* Get events by date range

    ```sh
    curl http://localhost:8000/events/from/2023/12/to/2024/02
    ```

* Get events by keyword

    ```sh
    curl http://localhost:8000/events?keyword=Python
    ```

See [API document](https://yuukis.github.io/yamanashi-event-api) for more details.

## MCP Server

This API also exposes an [MCP](https://modelcontextprotocol.io) server at
`/mcp` (Streamable HTTP transport), so MCP-compatible clients (e.g. Claude,
Claude Code) can call it as tools instead of plain HTTP requests.

Add the hosted server directly, no local setup required:

```sh
claude mcp add --transport http yamanashi-event-api https://api.event.yamanashi.dev/mcp
```

Or, against a local instance:

```sh
claude mcp add --transport http yamanashi-event-api http://localhost:8000/mcp
```

Only the full-detail event operations (e.g. `list_events_full`,
`list_events_full_by_day`) and `list_groups` are exposed as MCP tools, so
that the `description` field is always present in tool results. The
compact `/events` endpoints remain REST-only.

You can try it out interactively with
[MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```sh
npx @modelcontextprotocol/inspector
```

Connect with Transport Type `Streamable HTTP` and URL
`http://localhost:8000/mcp`.

## Event Keywords

Each event in the response contains a `keywords` field with up to 5 normalized
keywords (e.g. `Python`, `AWS`, `もくもく会`, `初心者歓迎`), so that client
applications can filter events by keyword without worrying about notation
variations.

```json
{
  "title": "JAWS-UG山梨 【第12回】勉強会",
  "keywords": ["AWS", "LT会", "初心者歓迎", "オンライン"]
}
```

Keywords are extracted from the event title, catch, hash tag, description and
group key / group name using the dictionary defined in `app/keywords.yaml`.
The dictionary maps canonical keywords to notation patterns (regular
expressions), so no external API is used. Community naming conventions
(e.g. `*.py` Python communities, `JAWS-UG`, `CoderDojo`) are covered by
generic patterns matched against the group fields, so no per-community
configuration is needed. To add a new keyword, edit `app/keywords.yaml`.

Events loaded from an archive index inherit the `keywords` field of the
archive as is. If an archive event has no `keywords` field, keywords are
extracted with the dictionary in the same way as other events.

The `keyword` query parameter also matches the extracted keywords.

## Archive Index

Historical events can be loaded from external archive index JSON files. This is
intended for event data maintained outside this API repository, such as a
community or regional tech event archive.

Add archive index URLs to `app/config.yaml`.

```yaml
scope:
  archives:
    - url:
        - https://yuukis.github.io/yamanashi-event-archive/index.json
```

See [Archive Index](docs/archive-index.md) for the JSON format.

<!-- LICENSE -->
## License

Distributed under the Apache License, Version 2.0. See `LICENSE` for more information.

<!-- CONTACT -->
## Contact

Yuuki Shimizu - [@yuuki_maxio](https://x.com/yuuki_maxio) 

<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

* [shingen.py](https://shingenpy.connpass.com)
  - python user community in Yamanashi, Japan
* [Connpass](https://connpass.com)

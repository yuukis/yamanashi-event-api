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

* Python 3.9 or later
* Redis

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
    REDIS_URL=redis://localhost:6379
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
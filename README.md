# goalpost

A local-first planner that tracks your goals with real evidence. Plan weekly tasks and loose monthly or quarterly goals, then let connectors suggest what you’ve actually done.

## Quick start

```sh
cp .env.example .env        # set GOALPOST_TIMEZONE and GOALPOST_ENCRYPTION_KEY
docker compose up --build
```

Open <http://localhost:3000>. Both services bind to `127.0.0.1` only; never expose them to the internet.

For development without Docker, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Docs

- [Idea summary](docs/idea.md)
- [Data model](docs/data-model.md)
- [Connector SDK](docs/sdk.md)

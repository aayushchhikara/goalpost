# Contributing

## Dev setup

Requires [uv](https://docs.astral.sh/uv/), Node 24 with pnpm, and make.

```sh
cp .env.example .env   # fill in the required keys
make install
make dev               # backend on :8000, frontend on :3000
```

Other commands: `make test`, `make lint`, `make typecheck`, `make migrate`, `make gen-types`.
Run `make gen-types` after any API change; CI fails if the generated types are stale.
Install hooks with `uv run pre-commit install`.

## Adding a connector

Connectors live in the repo, one folder each under `connectors/`. They only fetch and normalize
events; the core handles scheduling, retries, secrets, validation, dedup and rules, and nothing is
ever marked done without you confirming it. `connectors/leetcode/` is the reference example: it's
the simplest, with no auth.

1. Copy `connectors/_template/` to `connectors/<id>/`, where `<id>` matches the manifest's `id`.
2. Fill in the manifest (config fields, `.env` secrets, event kinds with payload schemas and
   rule fields, sync hints) and implement `test_connection` and `fetch` from `goalpost.sdk`.
   Raise the SDK's typed errors on failure: `AuthError` pauses the connector, `RateLimited` and
   `TransientError` are retried, `PartialResult` keeps what was fetched.
3. Dry-run it against the real service. It prints normalized events with their local dates and
   saves nothing:

   ```sh
   uv run python -m goalpost.cli dry-run <id> --config key=value
   ```

4. Record responses into `fixtures/` (strip anything personal) and write `test_connector.py`
   against them. Tests never call the live service. `make test` runs every connector's tests.
5. Add a `README.md` covering what it tracks, how to get credentials, and known limits, then
   open a PR.

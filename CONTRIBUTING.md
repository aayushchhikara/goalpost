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

Copy `connectors/_template/` to `connectors/<name>/`, implement the connector base class from
`backend/goalpost/sdk/`, and declare a manifest. Connectors only suggest evidence; the user
confirms.
